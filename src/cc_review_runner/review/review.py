from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cc_review_runner import logx
from cc_review_runner.rules import Rules, Severity
from cc_review_runner.review.prompt import build_prompt
from cc_review_runner.review.skills import resolve_skills

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


@dataclass
class Finding:
    file: str
    line: int
    severity: Severity
    title: str
    detail: str
    suggestion: str

    def to_dict(self) -> dict[str, object]:
        return {
            "file": self.file,
            "line": self.line,
            "severity": self.severity.name.lower(),
            "title": self.title,
            "detail": self.detail,
            "suggestion": self.suggestion,
        }


@dataclass
class Report:
    findings: list[Finding]
    summary: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "summary": self.summary,
                "findings": [f.to_dict() for f in self.findings],
            },
            ensure_ascii=False,
            indent=2,
        )


def run(r: Rules, diff: str) -> Report:
    """Invoke the local `claude` CLI in headless mode and parse its JSON output."""
    claude_bin = _resolve_claude_bin()
    if not claude_bin:
        raise RuntimeError("claude CLI not found; install Claude Code on this runner host")

    skill_paths: list[Path] = []
    if r.skills:
        skill_paths = resolve_skills(r.skills)

    prompt = build_prompt(r, skill_paths)

    model = r.model or os.environ.get("CC_REVIEW_DEFAULT_MODEL", "MinMax-M2.7")
    timeout = int(os.environ.get("CC_REVIEW_TIMEOUT_SECONDS", "600"))

    cmd = [claude_bin, "-p", prompt, "--output-format", "json"]
    if model:
        cmd += ["--model", model]
    for sp in skill_paths:
        cmd += ["--skill", str(sp)]

    debug_path = os.environ.get("CC_REVIEW_DEBUG_DUMP_PATH", "").strip()

    logx.info(f"invoking claude CLI (model={model}, timeout={timeout}s)")

    result = subprocess.run(
        cmd,
        input=diff,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_sanitized_env(),
        check=False,
    )

    if debug_path:
        try:
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(result.stdout)
        except OSError as e:
            logx.warn(f"failed to write debug dump: {e}")

    if result.returncode != 0:
        logx.error(f"claude CLI exited with {result.returncode}")
        if result.stderr.strip():
            logx.error(f"stderr: {result.stderr.strip()}")
        if result.stdout.strip():
            logx.error(f"stdout: {result.stdout[:2000]}")
        raise RuntimeError(f"claude CLI failed with exit code {result.returncode}")

    try:
        data = parse_report(result.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        logx.error(f"failed to parse claude output: {e}")
        logx.error(f"raw output: {result.stdout[:2000]}")
        raise RuntimeError(f"claude output parse error: {e}") from e

    return _build_report(data)


def parse_report(raw: str) -> dict[str, object]:
    try:
        return json.loads(raw)  # type: ignore[return-value]
    except json.JSONDecodeError:
        pass
    stripped = _FENCE_RE.sub("", raw).strip()
    return json.loads(stripped)  # type: ignore[return-value]


def _build_report(data: dict[str, object]) -> Report:
    summary = str(data.get("summary", ""))
    raw_findings = data.get("findings", [])
    if not isinstance(raw_findings, list):
        raw_findings = []

    findings: list[Finding] = []
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        try:
            sev = Severity.parse(str(item.get("severity", "info")))
        except KeyError:
            sev = Severity.INFO
        findings.append(
            Finding(
                file=str(item.get("file", "")),
                line=int(item.get("line", 0)),
                severity=sev,
                title=str(item.get("title", "")),
                detail=str(item.get("detail", "")),
                suggestion=str(item.get("suggestion", "")),
            )
        )
    return Report(findings=findings, summary=summary)


def failure_gate(report: Report, threshold: Severity) -> bool:
    return any(f.severity >= threshold for f in report.findings)


def _resolve_claude_bin() -> str | None:
    explicit = os.environ.get("CC_REVIEW_CLAUDE_BIN", "").strip()
    if explicit:
        return explicit if shutil.which(explicit) else None
    return shutil.which("claude")


def _sanitized_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("CUSTOM_ENV_")}
