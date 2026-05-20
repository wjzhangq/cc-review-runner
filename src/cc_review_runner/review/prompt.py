from __future__ import annotations

from pathlib import Path

from cc_review_runner.rules import Rules

_BASE_PROMPT = """\
You are a senior software engineer performing a code review.

You will be given a unified diff of code changes. Review the diff carefully and identify any issues.

OUTPUT FORMAT:
You MUST respond with valid JSON only. No prose, no markdown fences. The JSON must match this schema:

{{
  "summary": "<brief overall assessment>",
  "findings": [
    {{
      "file": "<relative file path>",
      "line": <line number or 0 if N/A>,
      "severity": "<blocker|critical|high|medium|low|info>",
      "title": "<short title>",
      "detail": "<detailed explanation>",
      "suggestion": "<how to fix>"
    }}
  ]
}}

SEVERITY LEVELS (highest to lowest):
  blocker  — must be fixed before merge (security vulnerability, data loss risk)
  critical — serious issue that should block merge
  high     — significant issue
  medium   — moderate issue
  low      — minor issue
  info     — informational note

FOCUS AREAS:
{focus_section}

{skills_section}

{custom_prompt_section}

DIFF TO REVIEW:
"""


def build_prompt(r: Rules, skill_paths: list[Path]) -> str:
    focus_section = (
        "\n".join(f"  - {f}" for f in r.focus) if r.focus else "  - general code quality"
    )

    if skill_paths:
        skill_names = ", ".join(p.name for p in skill_paths)
        skills_section = f"ACTIVE SKILLS: {skill_names}\nApply the guidance from these skills during review."
    else:
        skills_section = ""

    custom_prompt_section = r.custom_prompt.strip() if r.custom_prompt else ""

    return _BASE_PROMPT.format(
        focus_section=focus_section,
        skills_section=skills_section,
        custom_prompt_section=custom_prompt_section,
    )
