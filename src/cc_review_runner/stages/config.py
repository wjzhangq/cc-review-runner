from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from cc_review_runner.version import BUILD_VERSION


def run() -> int:
    payload: dict = {
        "builds_dir_is_shared": False,
        "driver": {
            "name": "cc-review-runner",
            "version": BUILD_VERSION,
        },
        "job_env": {
            "CC_REVIEW_DRIVER_VERSION": BUILD_VERSION,
            "CC_REVIEW_STARTED_AT": datetime.now(timezone.utc).isoformat(),
        },
    }
    builds_dir = os.environ.get("CC_REVIEW_WORKSPACE_ROOT")
    if builds_dir:
        payload["builds_dir"] = builds_dir
    cache_dir = os.environ.get("CC_REVIEW_CACHE_ROOT")
    if cache_dir:
        payload["cache_dir"] = cache_dir
    json.dump(payload, sys.stdout)
    sys.stdout.flush()
    return 0
