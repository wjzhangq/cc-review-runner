from __future__ import annotations

import enum
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class Severity(enum.IntEnum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    BLOCKER = 5

    @classmethod
    def parse(cls, s: str) -> "Severity":
        return cls[s.strip().upper()]


@dataclass
class Rules:
    version: int = 1
    severity_threshold: Severity = Severity.CRITICAL
    include: list[str] = field(default_factory=lambda: ["**/*"])
    exclude: list[str] = field(default_factory=list)
    max_diff_lines: int = 3000
    focus: list[str] = field(default_factory=list)
    custom_prompt: str = ""
    skills: list[str] = field(default_factory=list)
    model: str = ""


def defaults() -> Rules:
    return Rules()


def load(repo_root: Path) -> Rules:
    r = defaults()
    cfg = repo_root / ".claude-review.yml"
    if cfg.exists():
        with cfg.open("r", encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        _merge_from_dict(r, data)

    _apply_env_overrides(r, os.environ)
    _enforce_security_floor(r)
    return r


def _merge_from_dict(r: Rules, data: dict[str, Any]) -> None:
    if "version" in data:
        r.version = int(data["version"])
    if "severity_threshold" in data:
        try:
            r.severity_threshold = Severity.parse(str(data["severity_threshold"]))
        except KeyError:
            pass
    if "include" in data and isinstance(data["include"], list):
        r.include = [str(x) for x in data["include"]]
    if "exclude" in data and isinstance(data["exclude"], list):
        r.exclude = [str(x) for x in data["exclude"]]
    if "max_diff_lines" in data:
        r.max_diff_lines = int(data["max_diff_lines"])
    if "focus" in data and isinstance(data["focus"], list):
        r.focus = [str(x) for x in data["focus"]]
    if "custom_prompt" in data:
        r.custom_prompt = str(data["custom_prompt"])
    if "skills" in data and isinstance(data["skills"], list):
        r.skills = [str(x) for x in data["skills"]]
    if "model" in data:
        r.model = str(data["model"])


def _apply_env_overrides(r: Rules, env: dict[str, str]) -> None:
    if v := env.get("CC_REVIEW_SEVERITY_THRESHOLD", "").strip():
        try:
            r.severity_threshold = Severity.parse(v)
        except KeyError:
            pass
    if v := env.get("CC_REVIEW_MAX_DIFF_LINES", "").strip():
        try:
            r.max_diff_lines = int(v)
        except ValueError:
            pass
    if v := env.get("CC_REVIEW_MODEL", "").strip():
        r.model = v
    if v := env.get("CC_REVIEW_CUSTOM_PROMPT", "").strip():
        r.custom_prompt = v


def _enforce_security_floor(r: Rules) -> None:
    if r.severity_threshold > Severity.BLOCKER:
        r.severity_threshold = Severity.BLOCKER
