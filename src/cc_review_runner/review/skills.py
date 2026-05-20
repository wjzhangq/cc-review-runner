from __future__ import annotations

import os
import re
from pathlib import Path

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def resolve_skills(names: list[str]) -> list[Path]:
    """Validate names from rules and return absolute paths to each skill dir."""
    root = Path(os.environ.get("CC_REVIEW_SKILLS_ROOT", "/etc/cc-review/skills"))
    allowed = _allowed_set()

    paths: list[Path] = []
    for name in names:
        if not _NAME_RE.match(name):
            raise ValueError(f"invalid skill name: {name!r}")
        if allowed is not None and name not in allowed:
            raise ValueError(f"skill not in CC_REVIEW_SKILLS_ALLOWED: {name!r}")
        p = root / name
        if not (p / "SKILL.md").is_file():
            raise ValueError(f"skill not installed on runner host: {name!r}")
        paths.append(p.resolve())
    return paths


def _allowed_set() -> set[str] | None:
    raw = os.environ.get("CC_REVIEW_SKILLS_ALLOWED", "").strip()
    if not raw:
        return None
    return {s.strip() for s in raw.split(",") if s.strip()}
