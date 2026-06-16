"""Tests for JSON and markdown report output."""
import json
from pathlib import Path

import pytest

from standalone_check.reporter import write_project_report, write_summary
from standalone_check.verdict import ProjectReport

_REQUIRED_JSON_KEYS = {
    "project", "standalone_ready", "model_access",
    "blockers", "cloud_only_features", "notes",
}


def _make_report(name: str, verdict: str, blockers=None) -> ProjectReport:
    return ProjectReport(
        project=name,
        standalone_ready=verdict,  # type: ignore[arg-type]
        model_access={"client": "openai", "endpoint_configurable": True, "evidence": []},
        blockers=blockers or [],
        cloud_only_features=[],
        notes="",
    )


class TestProjectReport:
    def test_json_schema(self, tmp_path):
        report = _make_report("alpha", "yes")
        out = write_project_report(report, tmp_path)
        data = json.loads(out.read_text())
        assert _REQUIRED_JSON_KEYS == set(data.keys())

    def test_json_values(self, tmp_path):
        report = _make_report("beta", "no", blockers=[{
            "type": "hardcoded_cloud_endpoint",
            "severity": "high",
            "location": "agent.py:3",
            "fix": "move to env",
        }])
        out = write_project_report(report, tmp_path)
        data = json.loads(out.read_text())
        assert data["standalone_ready"] == "no"
        assert len(data["blockers"]) == 1
        assert data["blockers"][0]["severity"] == "high"

    def test_output_filename(self, tmp_path):
        report = _make_report("my-agent", "partial")
        out = write_project_report(report, tmp_path)
        assert out.name == "my-agent.json"


class TestSummary:
    def test_creates_summary_md(self, tmp_path):
        reports = [
            _make_report("alpha", "yes"),
            _make_report("beta", "partial"),
            _make_report("gamma", "no"),
        ]
        out = write_summary(reports, tmp_path)
        assert out.name == "summary.md"

    def test_all_projects_present(self, tmp_path):
        reports = [_make_report("alpha", "yes"), _make_report("beta", "no")]
        out = write_summary(reports, tmp_path)
        content = out.read_text()
        assert "alpha" in content
        assert "beta" in content

    def test_verdict_icons_present(self, tmp_path):
        reports = [
            _make_report("a", "yes"),
            _make_report("b", "partial"),
            _make_report("c", "no"),
        ]
        content = write_summary(reports, tmp_path).read_text()
        assert "✅" in content
        assert "⚠️" in content
        assert "❌" in content

    def test_sorted_alphabetically(self, tmp_path):
        reports = [_make_report("zoo", "yes"), _make_report("ant", "no")]
        content = write_summary(reports, tmp_path).read_text()
        assert content.index("ant") < content.index("zoo")
