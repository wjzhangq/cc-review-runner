from __future__ import annotations

import pytest

from cc_review_runner.review.review import Finding, Report, failure_gate
from cc_review_runner.rules import Severity


def _make_finding(severity: Severity) -> Finding:
    return Finding(
        file="x.py",
        line=1,
        severity=severity,
        title="test",
        detail="detail",
        suggestion="fix",
    )


def _report(*severities: Severity) -> Report:
    return Report(
        findings=[_make_finding(s) for s in severities],
        summary="",
    )


class TestFailureGate:
    def test_no_findings_pass(self) -> None:
        assert not failure_gate(_report(), Severity.CRITICAL)

    def test_critical_finding_fails_at_critical_threshold(self) -> None:
        assert failure_gate(_report(Severity.CRITICAL), Severity.CRITICAL)

    def test_high_finding_passes_at_critical_threshold(self) -> None:
        assert not failure_gate(_report(Severity.HIGH), Severity.CRITICAL)

    def test_blocker_fails_at_critical_threshold(self) -> None:
        assert failure_gate(_report(Severity.BLOCKER), Severity.CRITICAL)

    def test_medium_passes_at_critical_threshold(self) -> None:
        assert not failure_gate(_report(Severity.MEDIUM), Severity.CRITICAL)

    def test_threshold_blocker_only_fails_on_blocker(self) -> None:
        assert not failure_gate(_report(Severity.CRITICAL), Severity.BLOCKER)
        assert failure_gate(_report(Severity.BLOCKER), Severity.BLOCKER)

    def test_threshold_high(self) -> None:
        assert failure_gate(_report(Severity.HIGH), Severity.HIGH)
        assert not failure_gate(_report(Severity.MEDIUM), Severity.HIGH)

    def test_multiple_findings_any_above_threshold(self) -> None:
        assert failure_gate(
            _report(Severity.LOW, Severity.MEDIUM, Severity.CRITICAL),
            Severity.CRITICAL,
        )

    def test_all_below_threshold(self) -> None:
        assert not failure_gate(
            _report(Severity.LOW, Severity.INFO, Severity.MEDIUM),
            Severity.CRITICAL,
        )
