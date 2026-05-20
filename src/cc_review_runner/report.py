from __future__ import annotations

import os
import sys
from typing import TextIO

from cc_review_runner.diff import Stats
from cc_review_runner.review.review import Finding, Report
from cc_review_runner.rules import Rules, Severity

_SEV_ORDER = [Severity.BLOCKER, Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]

_ANSI = {
    Severity.BLOCKER: "\033[1;31m",
    Severity.CRITICAL: "\033[0;31m",
    Severity.HIGH: "\033[0;33m",
    Severity.MEDIUM: "\033[0;36m",
    Severity.LOW: "\033[0;37m",
    Severity.INFO: "\033[0;37m",
}
_RESET = "\033[0m"


def _use_color() -> bool:
    return os.environ.get("CI") == "true" and sys.stdout.isatty()


def _sev_str(sev: Severity, color: bool) -> str:
    name = sev.name
    if color:
        return f"{_ANSI[sev]}{name}{_RESET}"
    return name


def render(out: TextIO, report: Report, stats: Stats, rules: Rules) -> None:
    color = _use_color()
    W = 62
    sep = "═" * W
    thin = "─" * W

    counts: dict[Severity, int] = {s: 0 for s in _SEV_ORDER}
    for f in report.findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    model = report.model or rules.model or os.environ.get("CC_REVIEW_DEFAULT_MODEL", "claude-sonnet-4-5")

    print(sep, file=out)
    print("  Claude Code Review Report", file=out)
    print(sep, file=out)

    trunc_note = "  (truncated)" if stats.truncated else ""
    print(
        f"  Diff      : {stats.files_changed} files changed, "
        f"+{stats.lines_added} / -{stats.lines_removed} lines{trunc_note}",
        file=out,
    )
    rules_src = ".claude-review.yml" if True else "defaults"
    print(
        f"  Rules     : {rules_src} (severity_threshold={rules.severity_threshold.name.lower()})",
        file=out,
    )
    print(f"  Model     : {model}", file=out)

    parts = "  ".join(
        f"{s.name.lower()}:{counts[s]}" for s in _SEV_ORDER
    )
    print(f"  Findings  : {len(report.findings)}  ({parts})", file=out)
    print(thin, file=out)

    for f in report.findings:
        sev_label = _sev_str(f.severity, color)
        print(f"\n[{sev_label}] {f.file}:{f.line}", file=out)
        print(f"  Title : {f.title}", file=out)
        print(f"  Detail: {f.detail}", file=out)
        print(f"  Fix   : {f.suggestion}", file=out)

    print(f"\n{thin}", file=out)
    if report.summary:
        print(f"  Summary: {report.summary}", file=out)
    else:
        print("  Summary: (none provided by model)", file=out)
    print(sep, file=out)


def render_failure(out: TextIO, threshold: Severity, count: int) -> None:
    print(
        f"\n❌ Job failed: {count} finding(s) at or above severity threshold "
        f'"{threshold.name.lower()}".',
        file=out,
    )


def render_pass(out: TextIO) -> None:
    print("\n✅ No findings at or above the severity threshold.", file=out)
