"""Negative evidence and CLI boundaries; all targets are temporary synthetic files."""
import json
from pathlib import Path
import pytest
from click.testing import CliRunner
from standalone_check import cli
from standalone_check.reporter import write_project_report
from standalone_check.scanner.config_files import scan_config_files
from standalone_check.scanner.python_ast import scan_python_file, scan_python_project
from standalone_check.scanner.ripgrep import scan_js_ts_project
from standalone_check.verdict import compute_verdict

PORTABLE = 'from openai import OpenAI\nclient = OpenAI(base_url=endpoint)\n'

def scan(root):
    cfg, _ = scan_config_files(root)
    return compute_verdict(root.name, scan_python_project(root) + scan_js_ts_project(root) + cfg)

def invoke(root, output, *args):
    return CliRunner().invoke(cli.main, [str(root), '-o', str(output), *args])

@pytest.mark.parametrize('payload', [b'def (', b'\xff', b'x = "\x00"'])
def test_invalid_source_never_green(tmp_path, payload):
    (tmp_path / 'good.py').write_text(PORTABLE)
    (tmp_path / 'bad.py').write_bytes(payload)
    report = scan(tmp_path)
    assert report.standalone_ready == 'not_assessed'
    assert report.assessment_errors

@pytest.mark.parametrize('code', ['pass\n', 'client = CustomModel()\n', 'import litellm\n'])
def test_unrecognised_client_is_not_assessed(tmp_path, code):
    (tmp_path / 'agent.py').write_text(code)
    report = scan(tmp_path)
    assert report.standalone_ready == 'not_assessed'
    assert report.model_access['endpoint_configurable'] is False

@pytest.mark.parametrize('value', ['None', '""', 'False'])
def test_empty_endpoint_is_not_configurable(tmp_path, value):
    path = tmp_path / 'agent.py'
    path.write_text(f'from openai import OpenAI\nc = OpenAI(base_url={value})\n')
    report = compute_verdict('p', scan_python_file(path))
    assert report.standalone_ready == 'partial'
    assert report.model_access['endpoint_configurable'] is False

def test_real_failure_remains_failure_when_other_file_is_broken(tmp_path):
    (tmp_path / 'bad.py').write_text('def (')
    (tmp_path / 'cloud.py').write_text('url = "https://api.openai.com/v1"')
    report = scan(tmp_path)
    assert report.standalone_ready == 'no'
    assert report.assessment_errors and report.blockers

@pytest.mark.parametrize('suffix', ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'])
def test_source_types_and_gitignored_files_are_in_scope(tmp_path, suffix):
    (tmp_path / '.gitignore').write_text('*')
    (tmp_path / ('hidden' + suffix)).write_text('const url = "https://api.openai.com/v1";')
    assert scan(tmp_path).standalone_ready == 'no'
    assert cli._discover_projects(tmp_path) == [tmp_path]

def test_root_source_is_not_lost_when_subdirectory_exists(tmp_path):
    (tmp_path / 'app.py').write_text('url = "https://api.openai.com/v1"')
    nested = tmp_path / 'package'
    nested.mkdir()
    (nested / 'agent.py').write_text(PORTABLE)
    output = tmp_path / 'reports'
    result = invoke(tmp_path, output)
    assert result.exit_code == 1, result.output
    assert json.loads((output / f'{tmp_path.name}.json').read_text())['standalone_ready'] == 'no'

def test_monorepo_projects_are_sorted_and_selected(tmp_path):
    for name in ['zeta', 'alpha']:
        sub = tmp_path / name
        sub.mkdir()
        (sub / 'agent.py').write_text(PORTABLE)
    assert [p.name for p in cli._discover_projects(tmp_path)] == ['alpha', 'zeta']
    result = invoke(tmp_path, tmp_path / 'reports', '-p', 'alpha')
    assert result.exit_code == 0, result.output
    assert not (tmp_path / 'reports/zeta.json').exists()

@pytest.mark.parametrize('kind', ['file', 'directory', 'root', 'parent'])
def test_symlink_input_not_assessed(tmp_path, kind):
    actual = tmp_path / 'actual'
    actual.mkdir()
    (actual / 'agent.py').write_text(PORTABLE)
    target = tmp_path / 'target'
    target.mkdir()
    if kind == 'file':
        (target / 'agent.py').symlink_to(actual / 'agent.py')
    elif kind == 'directory':
        (target / 'pkg').symlink_to(actual, target_is_directory=True)
    else:
        link = tmp_path / 'link'
        link.symlink_to(actual, target_is_directory=True)
        target = link
        if kind == 'parent':
            (actual / 'pkg').mkdir()
            (actual / 'pkg/agent.py').write_text(PORTABLE)
            target = link / 'pkg'
    result = invoke(target, tmp_path / 'reports')
    assert result.exit_code == 2, result.output
    assert scan(target).standalone_ready == 'not_assessed'

def test_unreadable_source_not_assessed(tmp_path, monkeypatch):
    path = tmp_path / 'agent.py'
    path.write_text(PORTABLE)
    original = Path.read_text
    def unreadable(self, *args, **kwargs):
        if self == path:
            raise PermissionError('private details')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', unreadable)
    report = scan(tmp_path)
    assert report.standalone_ready == 'not_assessed'
    assert 'private details' not in str(report)

@pytest.mark.parametrize('text', ['[project', '[project]\ndependencies = "openai"', '[project]\ndependencies = [42]'])
def test_invalid_toml_never_green(tmp_path, text):
    (tmp_path / 'agent.py').write_text(PORTABLE)
    (tmp_path / 'pyproject.toml').write_text(text)
    assert scan(tmp_path).standalone_ready == 'not_assessed'

def test_toml_array_dependencies_are_actually_scanned(tmp_path):
    (tmp_path / 'pyproject.toml').write_text('[project]\ndependencies = ["anthropic>=1"]\n')
    findings, paths = scan_config_files(tmp_path)
    assert len(paths) == 1
    assert any(f.extra.get('sdk') == 'anthropic' for f in findings)

@pytest.mark.parametrize('name', ['requirements.txt', '.env.example', 'settings.yaml'])
def test_invalid_config_encoding_never_green(tmp_path, name):
    (tmp_path / 'agent.py').write_text(PORTABLE)
    (tmp_path / name).write_bytes(b'\xff')
    assert scan(tmp_path).standalone_ready == 'not_assessed'

def test_cli_never_executes_target_or_calls_llm_by_default(tmp_path, monkeypatch):
    (tmp_path / 'agent.py').write_text(PORTABLE + 'raise RuntimeError("must never execute")\n')
    monkeypatch.setenv('STANDALONE_CHECK_BASE_URL', 'https://must-not-call.invalid')
    def reject(*args):
        raise AssertionError('LLM invoked without opt-in')
    monkeypatch.setattr(cli, 'run_llm_pass', reject)
    result = invoke(tmp_path, tmp_path / 'reports')
    assert result.exit_code == 0, result.output

def test_cli_unknown_and_empty_exit_two(tmp_path):
    output = tmp_path / 'reports'
    assert invoke(tmp_path, output).exit_code == 2
    (tmp_path / 'agent.py').write_text('pass')
    assert invoke(tmp_path, output).exit_code == 2
    data = json.loads((output / f'{tmp_path.name}.json').read_text())
    assert data['standalone_ready'] == 'not_assessed'
    assert data['assessment_errors']

def test_explicit_llm_is_advisory_mock_only(tmp_path, monkeypatch):
    (tmp_path / 'agent.py').write_text(PORTABLE)
    calls = []
    def note(*args):
        calls.append(args)
        return 'Mock advice; runtime untested'
    monkeypatch.setattr(cli, 'run_llm_pass', note)
    result = invoke(tmp_path, tmp_path / 'reports', '--llm')
    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0][1] == [PORTABLE]

def test_llm_is_not_called_on_incomplete_input(tmp_path, monkeypatch):
    (tmp_path / 'agent.py').write_text('def (')
    def reject(*args):
        raise AssertionError('Incomplete source must not be sent')
    monkeypatch.setattr(cli, 'run_llm_pass', reject)
    assert invoke(tmp_path, tmp_path / 'reports', '--llm').exit_code == 2

def test_report_preserves_incomplete_status(tmp_path):
    report = compute_verdict('empty', [])
    data = json.loads(write_project_report(report, tmp_path).read_text())
    assert data['standalone_ready'] == 'not_assessed'
    assert data['assessment_errors']

@pytest.mark.parametrize('name', ['a.js', 'z.js'])
def test_js_blocker_survives_another_unreadable_file(tmp_path, name):
    other = 'z.js' if name == 'a.js' else 'a.js'
    (tmp_path / name).write_text('const url = "https://api.openai.com/v1";')
    (tmp_path / other).write_bytes(b'\xff')
    output = tmp_path / 'reports'
    assert invoke(tmp_path, output).exit_code == 2
    report = json.loads((output / f'{tmp_path.name}.json').read_text())
    assert report['standalone_ready'] == 'no'
    assert any(b['severity'] == 'high' for b in report['blockers'])
    assert report['assessment_errors']

@pytest.mark.parametrize('value', ['"anthropic"', '["anthropic"]'])
def test_invalid_poetry_dependencies_never_green(tmp_path, value):
    (tmp_path / 'agent.py').write_text(PORTABLE)
    (tmp_path / 'pyproject.toml').write_text(f'[tool.poetry]\ndependencies = {value}')
    assert scan(tmp_path).standalone_ready == 'not_assessed'

def test_root_config_is_not_lost_in_src_layout(tmp_path):
    (tmp_path / '.env.example').write_text('BASE_URL=https://api.openai.com/v1')
    source = tmp_path / 'src'
    source.mkdir()
    (source / 'agent.py').write_text(PORTABLE)
    output = tmp_path / 'reports'
    assert invoke(tmp_path, output).exit_code == 1
    assert json.loads((output / f'{tmp_path.name}.json').read_text())['standalone_ready'] == 'no'

def test_missing_one_of_selected_projects_is_incomplete(tmp_path):
    source = tmp_path / 'available'
    source.mkdir()
    (source / 'agent.py').write_text(PORTABLE)
    assert invoke(tmp_path, tmp_path / 'reports', '-p', 'available', '-p', 'absent').exit_code == 2

def test_special_file_never_read_or_approved(tmp_path):
    import os
    if not hasattr(os, 'mkfifo'):
        pytest.skip('POSIX FIFO')
    (tmp_path / 'agent.py').write_text(PORTABLE)
    os.mkfifo(tmp_path / 'pipe.py')
    assert invoke(tmp_path, tmp_path / 'reports').exit_code == 2

def test_directory_walk_error_is_incomplete(tmp_path, monkeypatch):
    from standalone_check.scanner import files
    def broken(root, **kwargs):
        kwargs['onerror'](PermissionError('synthetic walk failure'))
        return iter(())
    monkeypatch.setattr(files.os, 'walk', broken)
    assert scan(tmp_path).standalone_ready == 'not_assessed'
