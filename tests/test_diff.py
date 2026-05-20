from __future__ import annotations

import textwrap

import pytest

from cc_review_runner.diff import _filter_and_truncate, _matches_include_exclude
from cc_review_runner.rules import Rules


def _make_diff(files: dict[str, list[str]]) -> str:
    """Build a minimal unified diff string with the given files and +/- lines."""
    lines: list[str] = []
    for path, file_lines in files.items():
        lines.append(f"diff --git a/{path} b/{path}\n")
        lines.append(f"--- a/{path}\n")
        lines.append(f"+++ b/{path}\n")
        lines.append("@@ -1,1 +1,1 @@\n")
        for line in file_lines:
            lines.append(line + "\n")
    return "".join(lines)


class TestMatchesIncludeExclude:
    def test_include_all_by_default(self) -> None:
        assert _matches_include_exclude("src/foo.py", ["**/*"], [])

    def test_exclude_vendor(self) -> None:
        assert not _matches_include_exclude("vendor/lib.go", ["**/*"], ["vendor/**"])

    def test_include_only_py(self) -> None:
        assert _matches_include_exclude("src/main.py", ["**/*.py"], [])
        assert not _matches_include_exclude("src/main.go", ["**/*.py"], [])

    def test_exclude_test_files(self) -> None:
        assert not _matches_include_exclude("pkg/foo_test.go", ["**/*"], ["**/*_test.go"])

    def test_include_and_exclude_combined(self) -> None:
        assert not _matches_include_exclude(
            "vendor/foo.py", ["**/*.py"], ["vendor/**"]
        )


class TestFilterAndTruncate:
    def test_basic_filtering(self) -> None:
        raw = _make_diff({"src/main.py": ["+hello"], "vendor/lib.go": ["+world"]})
        r = Rules(include=["**/*.py"], exclude=["vendor/**"])
        text, stats = _filter_and_truncate(raw, r)
        assert "main.py" in text
        assert "vendor/lib.go" not in text
        assert stats.files_changed == 1

    def test_truncation(self) -> None:
        many_lines = [f"+line{i}" for i in range(200)]
        raw = _make_diff({"big.py": many_lines})
        r = Rules(include=["**/*"], exclude=[], max_diff_lines=50)
        text, stats = _filter_and_truncate(raw, r)
        assert stats.truncated
        assert "truncated" in text

    def test_no_truncation_when_within_limit(self) -> None:
        raw = _make_diff({"small.py": ["+a", "+b", "-c"]})
        r = Rules(include=["**/*"], exclude=[], max_diff_lines=3000)
        text, stats = _filter_and_truncate(raw, r)
        assert not stats.truncated
        assert stats.lines_added == 2
        assert stats.lines_removed == 1

    def test_empty_diff_after_filter(self) -> None:
        raw = _make_diff({"vendor/lib.go": ["+x"]})
        r = Rules(include=["**/*.py"], exclude=[])
        text, stats = _filter_and_truncate(raw, r)
        assert text == ""
        assert stats.files_changed == 0
