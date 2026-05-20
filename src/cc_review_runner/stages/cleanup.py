from __future__ import annotations

import shutil

from cc_review_runner import logx
from cc_review_runner.jobctx import JobContext


def run() -> int:
    try:
        jc = JobContext.load()
        _remove_quietly(jc.workdir)
    except Exception as e:
        logx.warn(f"cleanup ignored error: {e}")
    return 0


def _remove_quietly(path: object) -> None:
    from pathlib import Path

    p = Path(str(path))
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
        logx.info(f"cleaned up workdir: {p}")
