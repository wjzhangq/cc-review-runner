"""cc-review-runner CLI entry point.

GitLab Runner Custom Executor will fork/exec one of:
    cc-review-runner config
    cc-review-runner prepare
    cc-review-runner run <script_path> <stage>
    cc-review-runner cleanup

Each subcommand exits with one of:
    0                              — success
    $BUILD_FAILURE_EXIT_CODE       — user code / findings >= threshold
    $SYSTEM_FAILURE_EXIT_CODE      — driver / infra failure (job retried)
"""
from __future__ import annotations

import argparse
import sys

from cc_review_runner import logx
from cc_review_runner.stages import cleanup, config, prepare, run
from cc_review_runner.version import BUILD_VERSION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cc-review-runner", add_help=True)
    parser.add_argument("--version", action="version", version=BUILD_VERSION)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("config")
    sub.add_parser("prepare")
    p_run = sub.add_parser("run")
    p_run.add_argument("script_path")
    p_run.add_argument("stage")
    sub.add_parser("cleanup")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "config":
            return config.run()
        if args.cmd == "prepare":
            return prepare.run()
        if args.cmd == "run":
            return run.run(args.script_path, args.stage)
        if args.cmd == "cleanup":
            return cleanup.run()
    except SystemExit:
        raise
    except Exception as e:
        logx.error(f"unhandled exception: {e!r}")
        if args.cmd == "cleanup":
            return 0
        from cc_review_runner.jobctx import read_exit_codes

        return read_exit_codes().system_failure
    return 0


if __name__ == "__main__":
    sys.exit(main())
