from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from cc_review_runner.rules import Rules, Severity, _enforce_security_floor, _merge_from_dict, load


class TestSeverityParse:
    def test_uppercase(self) -> None:
        assert Severity.parse("CRITICAL") == Severity.CRITICAL

    def test_lowercase(self) -> None:
        assert Severity.parse("blocker") == Severity.BLOCKER

    def test_mixed_case(self) -> None:
        assert Severity.parse("High") == Severity.HIGH

    def test_invalid_raises(self) -> None:
        with pytest.raises(KeyError):
            Severity.parse("EXTREME")


class TestSeverityOrdering:
    def test_ordering(self) -> None:
        assert Severity.BLOCKER > Severity.CRITICAL
        assert Severity.CRITICAL > Severity.HIGH
        assert Severity.HIGH > Severity.MEDIUM
        assert Severity.MEDIUM > Severity.LOW
        assert Severity.LOW > Severity.INFO


class TestMergeFromDict:
    def test_merge_severity(self) -> None:
        r = Rules()
        _merge_from_dict(r, {"severity_threshold": "high"})
        assert r.severity_threshold == Severity.HIGH

    def test_merge_lists(self) -> None:
        r = Rules()
        _merge_from_dict(r, {"include": ["**/*.go"], "exclude": ["vendor/**"]})
        assert r.include == ["**/*.go"]
        assert r.exclude == ["vendor/**"]

    def test_merge_model(self) -> None:
        r = Rules()
        _merge_from_dict(r, {"model": "claude-opus-4-7"})
        assert r.model == "claude-opus-4-7"

    def test_unknown_keys_ignored(self) -> None:
        r = Rules()
        _merge_from_dict(r, {"nonexistent_key": "value"})  # should not raise


class TestEnforceSecurityFloor:
    def test_floor_does_not_change_blocker(self) -> None:
        r = Rules()
        r.severity_threshold = Severity.BLOCKER
        _enforce_security_floor(r)
        assert r.severity_threshold == Severity.BLOCKER

    def test_valid_threshold_unchanged(self) -> None:
        r = Rules()
        r.severity_threshold = Severity.CRITICAL
        _enforce_security_floor(r)
        assert r.severity_threshold == Severity.CRITICAL

    def test_all_valid_thresholds_pass(self) -> None:
        for sev in Severity:
            r = Rules()
            r.severity_threshold = sev
            _enforce_security_floor(r)
            assert r.severity_threshold <= Severity.BLOCKER


class TestLoadFromFile:
    def test_load_valid_file(self, tmp_path: Path) -> None:
        cfg = tmp_path / ".claude-review.yml"
        cfg.write_text(
            textwrap.dedent("""\
            version: 1
            severity_threshold: high
            include:
              - "**/*.py"
            exclude:
              - "vendor/**"
            max_diff_lines: 1000
            """),
            encoding="utf-8",
        )
        r = load(tmp_path)
        assert r.severity_threshold == Severity.HIGH
        assert r.include == ["**/*.py"]
        assert r.exclude == ["vendor/**"]
        assert r.max_diff_lines == 1000

    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        r = load(tmp_path)
        assert r.severity_threshold == Severity.CRITICAL
        assert r.max_diff_lines == 3000

    def test_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CC_REVIEW_MAX_DIFF_LINES", "500")
        monkeypatch.setenv("CC_REVIEW_SEVERITY_THRESHOLD", "blocker")
        r = load(tmp_path)
        assert r.max_diff_lines == 500
        assert r.severity_threshold == Severity.BLOCKER
