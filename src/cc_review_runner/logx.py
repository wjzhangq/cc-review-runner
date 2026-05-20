from __future__ import annotations

import sys
import time


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def info(msg: str) -> None:
    print(f"[{_ts()}] [INFO]  {msg}", file=sys.stderr, flush=True)


def warn(msg: str) -> None:
    print(f"[{_ts()}] [WARN]  {msg}", file=sys.stderr, flush=True)


def error(msg: str) -> None:
    print(f"[{_ts()}] [ERROR] {msg}", file=sys.stderr, flush=True)
