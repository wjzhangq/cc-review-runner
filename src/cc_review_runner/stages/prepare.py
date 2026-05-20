from __future__ import annotations

import shutil
import subprocess

from cc_review_runner import logx
from cc_review_runner.jobctx import read_exit_codes


def run() -> int:
    codes = read_exit_codes()
    claude_bin = _resolve_claude_bin()
    if not claude_bin:
        print("[ERROR] claude CLI not found on runner host. Install Claude Code first.")
        return codes.system_failure

    try:
        r = subprocess.run(
            [claude_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        logx.error(f"claude --version failed: {e}")
        return codes.system_failure

    if r.returncode != 0:
        logx.error(f"claude --version returned {r.returncode}: {r.stderr.strip()}")
        return codes.system_failure

    logx.info(f"claude CLI: {r.stdout.strip()}")
    return 0


def _resolve_claude_bin() -> str | None:
    import os

    explicit = os.environ.get("CC_REVIEW_CLAUDE_BIN", "").strip()
    if explicit:
        return explicit if shutil.which(explicit) else None
    return shutil.which("claude")
