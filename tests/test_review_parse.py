from __future__ import annotations

import json

import pytest

from cc_review_runner.review.review import parse_report, _build_report
from cc_review_runner.rules import Severity


_VALID_JSON = {
    "summary": "Found 2 issues.",
    "findings": [
        {
            "file": "src/auth.py",
            "line": 42,
            "severity": "critical",
            "title": "SQL injection",
            "detail": "User input not escaped.",
            "suggestion": "Use parameterized queries.",
        },
        {
            "file": "src/utils.py",
            "line": 10,
            "severity": "low",
            "title": "Unused variable",
            "detail": "x is never used.",
            "suggestion": "Remove the variable.",
        },
    ],
}


class TestParseReport:
    def test_plain_json(self) -> None:
        raw = json.dumps(_VALID_JSON)
        data = parse_report(raw)
        assert data["summary"] == "Found 2 issues."

    def test_json_fence(self) -> None:
        raw = "```json\n" + json.dumps(_VALID_JSON) + "\n```"
        data = parse_report(raw)
        assert len(data["findings"]) == 2  # type: ignore[arg-type]

    def test_plain_fence(self) -> None:
        raw = "```\n" + json.dumps(_VALID_JSON) + "\n```"
        data = parse_report(raw)
        assert data["summary"] == "Found 2 issues."

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            parse_report("not json at all {{{{")


class TestBuildReport:
    def test_findings_parsed(self) -> None:
        report = _build_report(_VALID_JSON)  # type: ignore[arg-type]
        assert len(report.findings) == 2
        assert report.findings[0].severity == Severity.CRITICAL
        assert report.findings[1].severity == Severity.LOW

    def test_summary(self) -> None:
        report = _build_report(_VALID_JSON)  # type: ignore[arg-type]
        assert report.summary == "Found 2 issues."

    def test_empty_findings(self) -> None:
        report = _build_report({"summary": "All good.", "findings": []})  # type: ignore[arg-type]
        assert report.findings == []

    def test_unknown_severity_defaults_to_info(self) -> None:
        data = {
            "summary": "",
            "findings": [
                {
                    "file": "x.py",
                    "line": 1,
                    "severity": "UNKNOWN_SEVERITY",
                    "title": "",
                    "detail": "",
                    "suggestion": "",
                }
            ],
        }
        report = _build_report(data)  # type: ignore[arg-type]
        assert report.findings[0].severity == Severity.INFO

    def test_missing_fields_use_defaults(self) -> None:
        data = {"findings": [{"severity": "high"}]}
        report = _build_report(data)  # type: ignore[arg-type]
        f = report.findings[0]
        assert f.severity == Severity.HIGH
        assert f.file == ""
        assert f.line == 0
