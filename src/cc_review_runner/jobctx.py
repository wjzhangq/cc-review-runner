from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExitCodes:
    build_failure: int
    system_failure: int


def read_exit_codes() -> ExitCodes:
    return ExitCodes(
        build_failure=int(os.environ.get("BUILD_FAILURE_EXIT_CODE", "1")),
        system_failure=int(os.environ.get("SYSTEM_FAILURE_EXIT_CODE", "2")),
    )


@dataclass
class JobContext:
    _env: dict[str, str]

    @classmethod
    def load(cls) -> "JobContext":
        env = dict(os.environ)
        job_response_file = env.get("JOB_RESPONSE_FILE", "")
        if job_response_file:
            try:
                with open(job_response_file, encoding="utf-8") as f:
                    data = json.load(f)
                # Merge job response variables; they take precedence
                for k, v in data.get("variables", {}).items():
                    env.setdefault(k, v)
            except (OSError, json.JSONDecodeError):
                pass
        return cls(_env=env)

    def env(self, key: str, default: str = "") -> str:
        return self._env.get(key, default)

    @property
    def workdir(self) -> Path:
        d = self._env.get("CI_PROJECT_DIR", "")
        if d:
            return Path(d)
        builds_dir = self._env.get(
            "CC_REVIEW_WORKSPACE_ROOT", "/var/lib/gitlab-runner/cc-review-work"
        )
        job_id = self._env.get("CI_JOB_ID", "unknown")
        return Path(builds_dir) / job_id
