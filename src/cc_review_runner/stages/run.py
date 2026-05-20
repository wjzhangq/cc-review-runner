from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from cc_review_runner import diff, logx, rules
from cc_review_runner.jobctx import ExitCodes, JobContext, read_exit_codes
from cc_review_runner.report import render, render_failure, render_pass
from cc_review_runner.review import review


def run(script_path: str, stage: str) -> int:
    codes = read_exit_codes()
    jc = JobContext.load()

    if stage == "step_script":
        return _run_review(jc, codes)

    # All other stages: execute the runner-generated script normally
    result = subprocess.run(["bash", script_path], check=False)
    if result.returncode != 0:
        return codes.build_failure
    return 0


def _write_empty_report(project_dir: Path, summary: str) -> None:
    try:
        (project_dir / "cc-review-report.json").write_text(
            f'{{"summary": {json.dumps(summary)}, "findings": []}}', encoding="utf-8"
        )
    except OSError:
        pass


def _run_review(jc: JobContext, codes: ExitCodes) -> int:
    project_dir_str = jc.env("CI_PROJECT_DIR")
    if not project_dir_str:
        logx.error("CI_PROJECT_DIR is not set; cannot run review")
        return codes.system_failure

    project_dir = Path(project_dir_str)
    os.chdir(project_dir)

    rules_obj = rules.load(project_dir)

    try:
        diff_text, stats = diff.compute(jc, rules_obj)
    except Exception as e:
        logx.error(f"diff failed: {e}")
        _write_empty_report(project_dir, f"Diff failed: {e}")
        return codes.system_failure

    if not diff_text.strip():
        logx.info("No reviewable changes in this push (after include/exclude filtering).")
        _write_empty_report(project_dir, "No reviewable changes.")
        return 0

    try:
        report = review.run(rules_obj, diff_text)
    except Exception as e:
        logx.error(f"claude review failed: {e}")
        _write_empty_report(project_dir, f"Review failed: {e}")
        return codes.system_failure

    try:
        (project_dir / "cc-review-report.json").write_text(report.to_json(), encoding="utf-8")
    except OSError as e:
        logx.warn(f"failed to write artifact: {e}")

    render(sys.stdout, report=report, stats=stats, rules=rules_obj)

    blocking = [f for f in report.findings if f.severity >= rules_obj.severity_threshold]
    if review.failure_gate(report, rules_obj.severity_threshold):
        render_failure(sys.stdout, rules_obj.severity_threshold, len(blocking))
        return codes.build_failure

    render_pass(sys.stdout)
    return 0
