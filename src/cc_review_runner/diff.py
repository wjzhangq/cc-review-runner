from __future__ import annotations

import subprocess
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath

from cc_review_runner import logx
from cc_review_runner.jobctx import JobContext
from cc_review_runner.rules import Rules

_ZERO_SHA = "0" * 40


class _MissingCommit(Exception):
    pass


@dataclass(frozen=True)
class Stats:
    files_changed: int
    lines_added: int
    lines_removed: int
    truncated: bool


def compute(jc: JobContext, r: Rules) -> tuple[str, Stats]:
    """Return the unified diff for the current push, filtered and truncated."""
    before = jc.env("CI_COMMIT_BEFORE_SHA", _ZERO_SHA)
    head = jc.env("CI_COMMIT_SHA")
    if not head:
        raise RuntimeError("CI_COMMIT_SHA is empty; cannot compute diff")

    if before == _ZERO_SHA:
        raw = _git_show(head)
    else:
        try:
            raw = _git_diff(before, head)
        except _MissingCommit:
            _git_unshallow_best_effort()
            try:
                raw = _git_diff(before, head)
            except _MissingCommit:
                raw = _git_show(head)

    return _filter_and_truncate(raw, r)


def _git_diff(before: str, head: str) -> str:
    result = subprocess.run(
        ["git", "diff", f"{before}..{head}"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        logx.warn(f"git diff stderr: {stderr}")
        if "unknown revision" in stderr or "bad object" in stderr:
            raise _MissingCommit(stderr)
        raise RuntimeError(f"git diff failed (rc={result.returncode}): {stderr}")
    return result.stdout


def _git_show(head: str) -> str:
    result = subprocess.run(
        ["git", "show", head],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        logx.warn(f"git show stderr: {stderr}")
        raise RuntimeError(f"git show failed (rc={result.returncode}): {stderr}")
    return result.stdout


def _git_unshallow_best_effort() -> None:
    logx.info("Attempting git fetch --unshallow to get full history...")
    result = subprocess.run(
        ["git", "fetch", "--unshallow"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        logx.warn(f"git fetch --unshallow failed (ignored): {result.stderr.strip()}")


def _matches_include_exclude(path: str, include: list[str], exclude: list[str]) -> bool:
    p = PurePosixPath(path)
    included = any(_glob_match(p, pat) for pat in include)
    if not included:
        return False
    excluded = any(_glob_match(p, pat) for pat in exclude)
    return not excluded


def _glob_match(p: PurePosixPath, pattern: str) -> bool:
    """Match a path against a glob pattern, supporting ** for recursive matching."""
    path_str = str(p)
    # Normalize pattern: **/* and **/ prefixes should match anything
    if pattern in ("**/*", "**"):
        return True
    if pattern.startswith("**/"):
        suffix = pattern[3:]  # e.g. "*.py" from "**/*.py"
        return fnmatch(p.name, suffix) or fnmatch(path_str, suffix)
    if pattern.endswith("/**"):
        prefix = pattern[:-3]  # e.g. "vendor" from "vendor/**"
        return path_str.startswith(prefix + "/") or path_str == prefix
    if "/**" in pattern:
        # e.g. "vendor/**" — already handled above; also handle "a/**/b"
        pass
    # PurePosixPath.match for simple patterns
    try:
        if p.match(pattern):
            return True
    except (ValueError, TypeError):
        pass
    return fnmatch(path_str, pattern) or fnmatch(p.name, pattern)


def _filter_and_truncate(raw: str, r: Rules) -> tuple[str, Stats]:
    lines = raw.splitlines(keepends=True)

    # Parse diff headers to filter by file
    filtered_lines: list[str] = []
    current_file: str | None = None
    include_current = True
    files_seen: set[str] = set()
    added = 0
    removed = 0

    for line in lines:
        if line.startswith("diff --git "):
            # Extract filename from "diff --git a/path b/path"
            parts = line.split(" ")
            if len(parts) >= 4:
                # Take b/ side as the new filename
                b_part = parts[-1].strip()
                if b_part.startswith("b/"):
                    current_file = b_part[2:]
                else:
                    current_file = b_part
            else:
                current_file = None
            include_current = (
                current_file is not None
                and _matches_include_exclude(current_file, r.include, r.exclude)
            )
            if include_current and current_file:
                files_seen.add(current_file)
            if include_current:
                filtered_lines.append(line)
        elif include_current:
            filtered_lines.append(line)
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1

    truncated = False
    if len(filtered_lines) > r.max_diff_lines:
        filtered_lines = filtered_lines[: r.max_diff_lines]
        filtered_lines.append("\n...(diff truncated due to max_diff_lines limit)...\n")
        truncated = True

    diff_text = "".join(filtered_lines)
    stats = Stats(
        files_changed=len(files_seen),
        lines_added=added,
        lines_removed=removed,
        truncated=truncated,
    )
    return diff_text, stats
