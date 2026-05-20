#!/usr/bin/env bash
# smoke.sh — end-to-end smoke test using a mock claude CLI
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[smoke] setting up environment..."

# Temp workspace
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

# Create a fake git repo with a diff
GIT_REPO="${WORK_DIR}/repo"
mkdir -p "${GIT_REPO}"
cd "${GIT_REPO}"
git init -q
git config user.email "test@test.com"
git config user.name "Test"
echo "print('hello')" > main.py
git add .
git commit -q -m "initial"
BEFORE_SHA=$(git rev-parse HEAD)
echo "print('world')" >> main.py
git add .
git commit -q -m "add world"
HEAD_SHA=$(git rev-parse HEAD)

# Create a mock claude CLI that returns a valid JSON report
MOCK_CLAUDE="${WORK_DIR}/bin/claude"
mkdir -p "${WORK_DIR}/bin"
cat > "${MOCK_CLAUDE}" << 'EOF'
#!/usr/bin/env bash
# Mock claude CLI — always returns a clean review with no critical findings
cat << 'JSON'
{
  "summary": "No major issues found.",
  "findings": [
    {
      "file": "main.py",
      "line": 1,
      "severity": "info",
      "title": "Minor style note",
      "detail": "Consider adding a docstring.",
      "suggestion": "Add a module-level docstring."
    }
  ]
}
JSON
EOF
chmod +x "${MOCK_CLAUDE}"

# Script stubs for non-review stages
STUB_SCRIPT="${WORK_DIR}/stub.sh"
echo "#!/bin/bash" > "${STUB_SCRIPT}"
chmod +x "${STUB_SCRIPT}"

export PATH="${WORK_DIR}/bin:${PATH}"
export CC_REVIEW_CLAUDE_BIN="${MOCK_CLAUDE}"
export CC_REVIEW_WORKSPACE_ROOT="${WORK_DIR}/builds"
export CC_REVIEW_CACHE_ROOT="${WORK_DIR}/cache"
export CI_COMMIT_BEFORE_SHA="${BEFORE_SHA}"
export CI_COMMIT_SHA="${HEAD_SHA}"
export CI_PROJECT_DIR="${GIT_REPO}"
export CI_JOB_ID="smoke-test-001"
export BUILD_FAILURE_EXIT_CODE="1"
export SYSTEM_FAILURE_EXIT_CODE="2"

RUNNER="uv run --project '${ROOT}' cc-review-runner"

echo "[smoke] --- config stage ---"
eval "${RUNNER} config" | python3 -m json.tool > /dev/null
echo "[smoke] config OK"

echo "[smoke] --- prepare stage ---"
eval "${RUNNER} prepare"
echo "[smoke] prepare OK"

echo "[smoke] --- run/get_sources stage ---"
eval "${RUNNER} run '${STUB_SCRIPT}' get_sources"
echo "[smoke] run/get_sources OK"

echo "[smoke] --- run/step_script stage ---"
eval "${RUNNER} run '${STUB_SCRIPT}' step_script"
echo "[smoke] run/step_script OK"

echo "[smoke] --- cleanup stage ---"
eval "${RUNNER} cleanup"
echo "[smoke] cleanup OK"

echo ""
echo "[smoke] ALL STAGES PASSED ✅"
