"""Tests for the AST-based Python scanner."""
import textwrap
from pathlib import Path

import pytest

from standalone_check.scanner.python_ast import scan_python_file, scan_python_project
from standalone_check.scanner.signals import (
    SIGNAL_CLOUD_ONLY_API,
    SIGNAL_CLOUD_SDK,
    SIGNAL_ENDPOINT_NOT_CONFIGURABLE,
    SIGNAL_HARDCODED_ENDPOINT,
    SIGNAL_HARDCODED_KEY,
    SIGNAL_HARDCODED_MODEL,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _signals(path: Path) -> list[str]:
    return [f.signal.name for f in scan_python_file(path)]


# ---------------------------------------------------------------------------
# proj_hardcoded — HIGH: hardcoded endpoint + key + cloud model
# ---------------------------------------------------------------------------

class TestHardcoded:
    path = FIXTURES / "proj_hardcoded" / "agent.py"

    def test_detects_hardcoded_endpoint(self):
        names = _signals(self.path)
        assert SIGNAL_HARDCODED_ENDPOINT.name in names

    def test_detects_hardcoded_key(self):
        names = _signals(self.path)
        assert SIGNAL_HARDCODED_KEY.name in names

    def test_detects_hardcoded_model(self):
        names = _signals(self.path)
        assert SIGNAL_HARDCODED_MODEL.name in names

    def test_no_endpoint_configurable_signal(self):
        # base_url IS provided (even though it's a cloud URL), so
        # SIGNAL_ENDPOINT_NOT_CONFIGURABLE should NOT fire — the cloud URL
        # is caught by SIGNAL_HARDCODED_ENDPOINT instead.
        names = _signals(self.path)
        assert SIGNAL_ENDPOINT_NOT_CONFIGURABLE.name not in names


# ---------------------------------------------------------------------------
# proj_env_driven — no HIGH/MEDIUM signals
# ---------------------------------------------------------------------------

class TestEnvDriven:
    path = FIXTURES / "proj_env_driven" / "agent.py"

    def test_no_hardcoded_endpoint(self):
        names = _signals(self.path)
        assert SIGNAL_HARDCODED_ENDPOINT.name not in names

    def test_no_hardcoded_key(self):
        names = _signals(self.path)
        assert SIGNAL_HARDCODED_KEY.name not in names

    def test_no_endpoint_not_configurable(self):
        names = _signals(self.path)
        assert SIGNAL_ENDPOINT_NOT_CONFIGURABLE.name not in names

    def test_no_hardcoded_model(self):
        names = _signals(self.path)
        assert SIGNAL_HARDCODED_MODEL.name not in names


# ---------------------------------------------------------------------------
# proj_partial — MEDIUM: hardcoded cloud model name
# ---------------------------------------------------------------------------

class TestPartial:
    path = FIXTURES / "proj_partial" / "agent.py"

    def test_detects_hardcoded_model(self):
        names = _signals(self.path)
        assert SIGNAL_HARDCODED_MODEL.name in names

    def test_no_hardcoded_endpoint(self):
        names = _signals(self.path)
        assert SIGNAL_HARDCODED_ENDPOINT.name not in names


# ---------------------------------------------------------------------------
# proj_anthropic — LOW: cloud SDK import
# ---------------------------------------------------------------------------

class TestAnthropic:
    path = FIXTURES / "proj_anthropic" / "agent.py"

    def test_detects_sdk_import(self):
        names = _signals(self.path)
        assert SIGNAL_CLOUD_SDK.name in names

    def test_sdk_client_is_anthropic(self):
        findings = scan_python_file(self.path)
        sdk_findings = [f for f in findings if f.signal == SIGNAL_CLOUD_SDK]
        assert any("anthropic" in f.extra.get("sdk", "") for f in sdk_findings)


# ---------------------------------------------------------------------------
# proj_assistants — HIGH: cloud-only API
# ---------------------------------------------------------------------------

class TestAssistants:
    path = FIXTURES / "proj_assistants" / "agent.py"

    def test_detects_cloud_only_api(self):
        names = _signals(self.path)
        assert SIGNAL_CLOUD_ONLY_API.name in names

    def test_assistants_namespace_captured(self):
        findings = scan_python_file(self.path)
        co = [f for f in findings if f.signal == SIGNAL_CLOUD_ONLY_API]
        namespaces = [f.extra.get("namespace", "") for f in co]
        assert any("assistants" in ns for ns in namespaces)


# ---------------------------------------------------------------------------
# Inline snippet tests — edge cases
# ---------------------------------------------------------------------------

class TestInlineSnippets:
    def _scan_src(self, src: str, tmp_path: Path) -> list[str]:
        p = tmp_path / "agent.py"
        p.write_text(textwrap.dedent(src))
        return _signals(p)

    def test_env_var_base_url_not_flagged(self, tmp_path):
        src = """\
            import os, openai
            client = openai.OpenAI(base_url=os.getenv("OPENAI_BASE_URL"))
        """
        names = self._scan_src(src, tmp_path)
        assert SIGNAL_ENDPOINT_NOT_CONFIGURABLE.name not in names
        assert SIGNAL_HARDCODED_ENDPOINT.name not in names

    def test_no_base_url_flagged(self, tmp_path):
        src = """\
            import openai
            client = openai.OpenAI(api_key="sk-dummy-00000000000000000000")
        """
        names = self._scan_src(src, tmp_path)
        assert SIGNAL_ENDPOINT_NOT_CONFIGURABLE.name in names

    def test_syntax_error_skipped(self, tmp_path):
        p = tmp_path / "bad.py"
        p.write_text("def (")
        assert scan_python_file(p) == []

    def test_project_scan_skips_venv(self, tmp_path):
        venv = tmp_path / ".venv" / "lib" / "site.py"
        venv.parent.mkdir(parents=True)
        venv.write_text("import openai\nclient = openai.OpenAI()\n")
        assert scan_python_project(tmp_path) == []

    def test_hardcoded_key_in_string(self, tmp_path):
        src = 'KEY = "sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"\n'
        names = self._scan_src(src, tmp_path)
        assert SIGNAL_HARDCODED_KEY.name in names
