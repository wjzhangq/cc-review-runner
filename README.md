# cc-review-runner

A GitLab Runner Custom Executor driver that automatically runs Claude Code review on every push. When Claude finds `critical` or `blocker` severity issues, the CI job fails.

## Requirements

- Python ≥ 3.11
- [`uv`](https://docs.astral.sh/uv/) ≥ 0.5.0
- `claude` CLI (Claude Code) installed on the runner host
- `git`

## Installation

Install on a runner host via `uv tool`:

```bash
sudo bash scripts/install-on-runner.sh 1.0.0
```

Or manually:

```bash
uv tool install cc-review-runner==1.0.0
```

After installation, the shim is available at `~/.local/bin/cc-review-runner`.

## How it works

The driver implements the [GitLab Runner Custom Executor](https://docs.gitlab.com/runner/executors/custom/) protocol with four subcommands:

| Subcommand | Stage | What it does |
|---|---|---|
| `config` | Config | Emits JSON workspace config to stdout |
| `prepare` | Prepare | Validates that `claude` CLI is installed and reachable |
| `run <script> <stage>` | Run | Executes runner scripts normally for all stages except `step_script`, which triggers the review |
| `cleanup` | Cleanup | Removes the build directory |

On `step_script`, the driver:
1. Computes `git diff $CI_COMMIT_BEFORE_SHA..$CI_COMMIT_SHA`
2. Filters the diff by `include`/`exclude` globs from `.claude-review.yml`
3. Calls `claude -p "<prompt>" --output-format json` with the diff on stdin
4. Parses the JSON findings and prints them to the job log
5. Fails the job if any finding is at or above the configured `severity_threshold`

## Configuration

### Runner host (`config.toml`)

See [`deploy/config.toml.example`](deploy/config.toml.example) for the full runner configuration.

Key environment variables (set in `config.toml` `environment = [...]`):

| Variable | Default | Description |
|---|---|---|
| `CC_REVIEW_DEFAULT_MODEL` | `claude-sonnet-4-5` | Claude model to use when repo doesn't specify one |
| `CC_REVIEW_TIMEOUT_SECONDS` | `600` | Hard timeout for the `claude` CLI call |
| `CC_REVIEW_CLAUDE_BIN` | _(PATH lookup)_ | Absolute path to `claude` binary |
| `CC_REVIEW_SKILLS_ROOT` | `/etc/cc-review/skills` | Directory containing available skills |
| `CC_REVIEW_SKILLS_ALLOWED` | _(all)_ | Comma-separated whitelist of skill names |
| `ANTHROPIC_API_KEY` | — | API key passed through to `claude` |

### Repository (`.claude-review.yml`)

Place this file at the repo root to control review behaviour:

```yaml
version: 1

# Fail the job on findings at or above this severity (blocker > critical > high > medium > low > info)
severity_threshold: critical

# Diff filtering
include:
  - "**/*.py"
  - "**/*.go"
exclude:
  - "vendor/**"
  - "**/*_test.go"

# Max diff lines sent to Claude (prevents context overflow)
max_diff_lines: 3000

# Review focus areas
focus:
  - security
  - error-handling
  - resource-leak

# Extra instructions appended to the default prompt
custom_prompt: |
  This service handles PII — flag any logging of personal data.

# Skills to enable (must be installed on the runner host)
skills:
  - secret-scanning

# Override the model for this repo
model: claude-sonnet-4-5
```

### GitLab CI (`.gitlab-ci.yml`)

#### Custom Executor（推荐）

Runner 配置为 `executor = "custom"` 时使用。`step_script` 阶段由 cc-review-runner 接管，`script` 字段仅为占位：

```yaml
review:
  tags: [cc-review]
  script: [":"]  # placeholder — Custom Executor ignores this during step_script
  rules:
    - if: $CI_PIPELINE_SOURCE == "push"
  artifacts:
    when: always
    paths: [cc-review-report.json]
    expire_in: 30 days
```

#### Shell Executor

Runner 配置为 `executor = "shell"` 时使用。需要在 `script` 中显式调用 cc-review-runner：

```yaml
review:
  tags: [cc-review]
  variables:
    GIT_DEPTH: 0
  script:
    - cc-review-runner prepare
    - cc-review-runner run /dev/null step_script
  artifacts:
    when: always
    paths: [cc-review-report.json]
    expire_in: 30 days
  rules:
    - if: $CI_PIPELINE_SOURCE == "push"
```

> Shell Executor 模式下，runner 主机需要确保 `cc-review-runner` 在 PATH 中，且 `ANTHROPIC_API_KEY` 等环境变量已设置（通过 `config.toml` 的 `environment` 或 GitLab CI/CD Variables）。

### 自定义提示词（Custom Prompt）

通过 `.claude-review.yml` 的 `custom_prompt` 字段，可以向 review 提示词追加自定义指令：

```yaml
version: 1

custom_prompt: |
  This service handles PII — flag any logging of personal data.
  All database queries must use parameterized statements.
  Prefer returning early over deeply nested if-else.
```

`custom_prompt` 会被原样追加到内置提示词末尾（diff 之前），适合补充项目特有的规范或关注点。

也可以通过环境变量 `CC_REVIEW_CUSTOM_PROMPT` 覆盖（优先级高于配置文件）。

#### focus 字段

`focus` 是一个列表，用于告诉 Claude 重点关注哪些方面。不设置时默认关注 "general code quality"：

```yaml
focus:
  - security
  - error-handling
  - resource-leak
  - concurrency
  - sql-injection
```

### Skills

Skills 是安装在 runner 主机上的可复用 review 规则包，通过 `--skill` 参数传递给 `claude` CLI。

#### 创建 Skill

每个 skill 是一个目录，包含一个 `SKILL.md` 文件：

```
/etc/cc-review/skills/
├── secret-scanning/
│   └── SKILL.md
├── sql-injection-hunter/
│   └── SKILL.md
└── go-review/
    └── SKILL.md
```

`SKILL.md` 示例（`secret-scanning`）：

```markdown
# Secret Scanning

Detect hardcoded secrets, API keys, tokens, and credentials in the diff.

## Rules

- Flag any string matching common secret patterns (AWS keys, GitHub tokens, JWTs, private keys)
- Flag environment variable values that appear to be real secrets rather than placeholders
- Severity: blocker for production credentials, high for test/dev credentials
- Ignore: example values like "sk-ant-...", "REPLACE_ME", "xxx"
```

Skill 名称必须匹配 `[a-z0-9][a-z0-9_-]*`。

#### 在 runner 主机上安装 Skill

```bash
sudo mkdir -p /etc/cc-review/skills/secret-scanning
sudo tee /etc/cc-review/skills/secret-scanning/SKILL.md <<'EOF'
# Secret Scanning
...
EOF
```

#### 配置 runner 允许的 Skills

在 `config.toml` 的 `environment` 中设置白名单（不设置则允许所有已安装的 skill）：

```toml
environment = [
  "CC_REVIEW_SKILLS_ROOT=/etc/cc-review/skills",
  "CC_REVIEW_SKILLS_ALLOWED=secret-scanning,sql-injection-hunter,go-review",
]
```

| 变量 | 说明 |
|---|---|
| `CC_REVIEW_SKILLS_ROOT` | Skill 目录根路径，默认 `/etc/cc-review/skills` |
| `CC_REVIEW_SKILLS_ALLOWED` | 逗号分隔的白名单，为空表示允许所有 |

#### 在仓库中启用 Skills

在 `.claude-review.yml` 中声明要使用的 skill：

```yaml
skills:
  - secret-scanning
  - sql-injection-hunter
```

只有同时满足以下条件的 skill 才会生效：
1. runner 主机上 `CC_REVIEW_SKILLS_ROOT` 目录下存在对应目录且包含 `SKILL.md`
2. skill 名称在 `CC_REVIEW_SKILLS_ALLOWED` 白名单中（或白名单为空）

## 快速上手：从零部署到第一次 Review

### 第一步：在 runner 主机上准备依赖

```bash
# 1. 安装 uv（如果还没有）
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # 或重新登录，让 ~/.local/bin 进 PATH

# 2. 安装 Claude Code CLI
npm install -g @anthropic-ai/claude-code   # 或按官方文档操作
claude --version   # 确认可用

# 3. 设置 Anthropic API Key
export ANTHROPIC_API_KEY=sk-ant-...
echo "ANTHROPIC_API_KEY=sk-ant-..." | sudo tee /etc/gitlab-runner/cc-review.env
```

### 第二步：安装 cc-review-runner

```bash
# 从源码目录安装（开发/自托管场景）
cd /path/to/cc-review-runner
sudo -u gitlab-runner uv tool install --editable .

# 或者从发布版本安装
sudo bash scripts/install-on-runner.sh 1.0.0

# 验证
sudo -u gitlab-runner cc-review-runner --version
# 输出: 1.0.0
```

### 第三步：注册 GitLab Runner

```bash
sudo gitlab-runner register \
  --non-interactive \
  --url "https://gitlab.example.com/" \
  --registration-token "YOUR_TOKEN" \
  --executor "custom" \
  --description "cc-review-01" \
  --tag-list "cc-review"
```

然后把 `deploy/config.toml.example` 中的 `[runners.custom]` 段合并到 `/etc/gitlab-runner/config.toml`，并把其中的路径替换为实际 shim 路径：

```bash
# 查看 shim 实际路径
sudo -u gitlab-runner which cc-review-runner
# 通常输出: /var/lib/gitlab-runner/.local/bin/cc-review-runner
```

```bash
sudo systemctl restart gitlab-runner
sudo gitlab-runner verify   # 应该显示 runner 处于 alive 状态
```

### 第四步：在目标仓库里激活

在仓库根目录添加两个文件：

**`.gitlab-ci.yml`**（Shell Executor）：

```yaml
review:
  tags: [cc-review]          # 必须与 runner 的 tag 匹配
  variables:
    GIT_DEPTH: 0
  script:
    - cc-review-runner prepare
    - cc-review-runner run /dev/null step_script
  artifacts:
    when: always
    paths: [cc-review-report.json]
    expire_in: 30 days
  rules:
    - if: $CI_PIPELINE_SOURCE == "push"
```

> 如果 runner 使用 Custom Executor，将 `script` 替换为 `script: [":"]` 即可。

**`.claude-review.yml`**（可选，不存在则用默认值）：

```yaml
version: 1
severity_threshold: critical
include:
  - "**/*.py"
  - "**/*.go"
exclude:
  - "vendor/**"
```

提交并 push，流水线即自动触发 review。

### 第五步：验证 review 正常运行

```bash
# 手动模拟各阶段（无需真实 GitLab 环境）
export CI_COMMIT_SHA=$(git rev-parse HEAD)
export CI_COMMIT_BEFORE_SHA=$(git rev-parse HEAD~1)
export CI_PROJECT_DIR=$(pwd)
export BUILD_FAILURE_EXIT_CODE=1
export SYSTEM_FAILURE_EXIT_CODE=2

cc-review-runner config          # 应输出 JSON
cc-review-runner prepare         # 应输出 "claude CLI: ..." 到 stderr
cc-review-runner run /dev/null step_script   # 触发真实 review

# 或者跑内置冒烟测试（使用 mock claude，不消耗 API）
make smoke
```

---

## Development

```bash
# Set up dev environment
make install        # uv sync --all-extras

# Run tests
make test           # uv run pytest

# Lint + format check
make lint

# Type check
make typecheck

# Build wheel
make build

# Full CI check
make ci

# End-to-end smoke test (uses a mock claude CLI)
make smoke
```

## Project structure

```
src/cc_review_runner/
├── cli.py          # Subcommand dispatch (argparse)
├── jobctx.py       # CI environment / exit code parsing
├── logx.py         # Stderr logger
├── diff.py         # Git diff computation and filtering
├── rules.py        # .claude-review.yml loading + Severity enum
├── report.py       # Job log rendering + JSON artifact
├── version.py      # Version from package metadata
├── stages/         # config / prepare / run / cleanup handlers
└── review/         # Claude CLI invocation, prompt, skills, output parsing
```

## Security notes

- The `script:` field in `.gitlab-ci.yml` is **ignored** during `step_script` — the review flow cannot be bypassed by repository owners.
- `severity_threshold` cannot be set below `blocker` (i.e. there is no "never fail" option).
- All `CUSTOM_ENV_*` variables are stripped from the environment before calling `claude`.
- Skill names are validated against `[a-z0-9_-]` and an optional allowlist before use.
- YAML config is parsed with `yaml.safe_load` only.
