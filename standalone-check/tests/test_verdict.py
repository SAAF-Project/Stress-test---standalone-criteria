"""Tests for verdict computation rules."""
from pathlib import Path

import pytest

from standalone_check.scanner.python_ast import scan_python_file
from standalone_check.verdict import compute_verdict

FIXTURES = Path(__file__).parent / "fixtures"


def _verdict(proj: str) -> str:
    path = FIXTURES / proj / "agent.py"
    findings = scan_python_file(path)
    return compute_verdict(proj, findings).standalone_ready


class TestVerdictRules:
    def test_hardcoded_is_no(self):
        assert _verdict("proj_hardcoded") == "no"

    def test_env_driven_is_yes(self):
        assert _verdict("proj_env_driven") == "yes"

    def test_partial_model_is_partial(self):
        assert _verdict("proj_partial") == "partial"

    def test_assistants_is_no(self):
        assert _verdict("proj_assistants") == "no"

    def test_empty_findings_is_yes(self):
        report = compute_verdict("empty", [])
        assert report.standalone_ready == "yes"
        assert report.blockers == []
        assert report.cloud_only_features == []

    def test_client_detection_anthropic(self):
        findings = scan_python_file(FIXTURES / "proj_anthropic" / "agent.py")
        report = compute_verdict("proj_anthropic", findings)
        assert report.model_access["client"] == "anthropic"

    def test_client_detection_openai(self):
        findings = scan_python_file(FIXTURES / "proj_env_driven" / "agent.py")
        report = compute_verdict("proj_env_driven", findings)
        assert report.model_access["client"] == "openai"

    def test_endpoint_configurable_true_for_env_driven(self):
        findings = scan_python_file(FIXTURES / "proj_env_driven" / "agent.py")
        report = compute_verdict("proj_env_driven", findings)
        assert report.model_access["endpoint_configurable"] is True

    def test_endpoint_configurable_false_for_hardcoded(self):
        findings = scan_python_file(FIXTURES / "proj_hardcoded" / "agent.py")
        report = compute_verdict("proj_hardcoded", findings)
        assert report.model_access["endpoint_configurable"] is False

    def test_blockers_only_contain_high_and_medium(self):
        findings = scan_python_file(FIXTURES / "proj_hardcoded" / "agent.py")
        report = compute_verdict("proj_hardcoded", findings)
        for b in report.blockers:
            assert b["severity"] in ("high", "medium")

    def test_notes_passed_through(self):
        report = compute_verdict("x", [], notes="extra info")
        assert report.notes == "extra info"
