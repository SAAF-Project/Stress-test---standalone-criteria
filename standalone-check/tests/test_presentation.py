"""UI logic with a stub: this does not launch or validate a Streamlit server."""
import importlib
import sys
from types import SimpleNamespace

from standalone_check.verdict import compute_verdict

class UIStub:
    def __init__(self):
        self.text = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def __getattr__(self, name):
        if name == 'columns':
            return lambda count: [self] * (count if isinstance(count, int) else len(count))
        def record(*args, **kwargs):
            self.text.extend(str(arg) for arg in args)
            return self
        return record

def load_web(monkeypatch):
    ui = UIStub()
    monkeypatch.setitem(sys.modules, 'streamlit', ui)
    monkeypatch.delitem(sys.modules, 'standalone_check.web', raising=False)
    return importlib.import_module('standalone_check.web'), ui

def test_unknown_has_own_headline_and_neutral_coverage(monkeypatch):
    web, ui = load_web(monkeypatch)
    report = compute_verdict('empty', [])
    assert 'incomplete' in web._verdict_reason(report)
    web._render_project_card(report, {'findings': [], 'by_signal': {}})
    text = '\n'.join(ui.text)
    assert 'Not assessed' in text
    assert 'Clean' not in text
    assert 'All checks passed' not in text

def test_ui_uses_same_incomplete_report(monkeypatch, tmp_path):
    web, _ = load_web(monkeypatch)
    (tmp_path / 'agent.py').write_text('def (')
    reports, meta = web._run_scan(tmp_path, [], True)
    assert reports[0].standalone_ready == 'not_assessed'
    assert reports[0].assessment_errors
    assert 'scan_incomplete' in meta[tmp_path.name]['by_signal']

def test_ui_static_candidate_never_claims_runtime_proof(monkeypatch, tmp_path):
    web, ui = load_web(monkeypatch)
    (tmp_path / 'agent.py').write_text('from openai import OpenAI\nc = OpenAI(base_url=endpoint)')
    reports, meta = web._run_scan(tmp_path, [], True)
    assert reports[0].standalone_ready == 'yes'
    assert 'Runtime remains untested' in web._verdict_reason(reports[0])
    web._render_project_card(reports[0], meta[tmp_path.name])
    assert 'All checks passed' not in '\n'.join(ui.text)
