"""
Text-pattern scanner for JS/TS and cross-language patterns the AST can't reach.

Uses a deterministic Python reader, independent of ripgrep and .gitignore.
The historical module name is retained for import compatibility.
"""
import re
from pathlib import Path
from typing import Optional

from .signals import (
    CLOUD_ENDPOINTS,
    CLOUD_MODEL_PATTERNS,
    PROVIDER_RESPONSE_PATTERNS,
    SIGNAL_HARDCODED_ENDPOINT,
    SIGNAL_HARDCODED_MODEL,
    SIGNAL_PROVIDER_RESPONSE_PARSING,
    SIGNAL_PROVIDER_FEATURE,
    SIGNAL_TELEMETRY_CALLBACK,
    Signal,
    SIGNAL_SCAN_ERROR,
)
from .python_ast import Finding, scan_error
from .files import project_files, read_source

_ENDPOINT_PATTERN = "|".join(re.escape(ep) for ep in CLOUD_ENDPOINTS)
_MODEL_PATTERN = "|".join(CLOUD_MODEL_PATTERNS)
_RESPONSE_PARSING_PATTERN = "|".join(PROVIDER_RESPONSE_PATTERNS)

# strict:true / strict: True in tool schemas (JSON lowercase, Python Title-case)
_STRICT_TOOL_PATTERN = r'"strict"\s*:\s*[Tt]rue|strict=True'
# Telemetry env vars set / referenced in JS/TS
_TELEMETRY_ENV_PATTERN = r"LANGCHAIN_TRACING|LANGSMITH_API_KEY|LANGSMITH_ENDPOINT|LANGCHAIN_API_KEY"

_ALL_GLOBS = [
    "-g", "*.ts", "-g", "*.tsx", "-g", "*.js", "-g", "*.jsx",
    "-g", "*.mjs", "-g", "*.cjs",
    "-g", "*.py",   # catch patterns AST doesn't reach (e.g. multiline strings)
]
_JS_GLOBS = ["-g", "*.ts", "-g", "*.tsx", "-g", "*.js", "-g", "*.jsx",
             "-g", "*.mjs", "-g", "*.cjs"]

def _glob_exts(extra_args: list[str]) -> list[str]:
    """Extract file extensions from -g glob args like ['-g', '*.py', '-g', '*.ts']."""
    exts: list[str] = []
    i = 0
    while i < len(extra_args):
        if extra_args[i] == "-g" and i + 1 < len(extra_args):
            pat = extra_args[i + 1]
            if pat.startswith("*."):
                exts.append(pat[1:])  # ".py", ".ts", etc.
        i += 1
    return exts


def _python_grep(pattern: str, path: Path, extra_args: list[str]) -> list[dict]:
    """Read files and apply regex — fallback when rg is not installed."""
    ignore_case = "-i" in extra_args
    exts = _glob_exts(extra_args)
    if not exts:
        return []
    rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)

    results: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for fpath in project_files(path):
        if fpath.suffix not in exts:
            continue
        try:
            lines = read_source(fpath).splitlines()
        except (OSError, UnicodeError) as error:
            results.append({"type": "scan_error", "file": str(fpath),
                            "reason": type(error).__name__})
            continue
        for lineno, line in enumerate(lines, 1):
            if rx.search(line):
                key = (str(fpath), lineno)
                if key not in seen:
                    seen.add(key)
                    results.append({
                        "type": "match",
                        "data": {"path": {"text": str(fpath)}, "line_number": lineno,
                                 "lines": {"text": line}},
                    })
    return results


# ---------------------------------------------------------------------------
# Core search (rg if available, Python fallback otherwise)
# ---------------------------------------------------------------------------

def _rg_json(
    pattern: str,
    path: Path,
    extra_args: Optional[list[str]] = None,
) -> list[dict]:
    # One reader for all environments: gitignore, rg availability and subprocess
    # errors must never change coverage. Keep this helper name for API compatibility.
    return _python_grep(pattern, path, extra_args or [])


def _to_finding(
    match: dict, signal: Signal, project_root: Path
) -> Optional[Finding]:
    if match.get("type") == "scan_error":
        return Finding(SIGNAL_SCAN_ERROR, match["file"], 0, "",
                       {"reason": match["reason"]})
    try:
        data = match["data"]
        raw_path = Path(data["path"]["text"])
        line = data["line_number"]
        text = data["lines"]["text"].strip()[:200]
        try:
            rel = str(raw_path.relative_to(project_root))
        except ValueError:
            rel = str(raw_path)
        return Finding(signal=signal, file=rel, line=line, snippet=text)
    except (KeyError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _scan_js_ts_project(project_root: Path) -> list[Finding]:
    findings: list[Finding] = []

    # Hardcoded cloud endpoints (JS/TS only — Python handled by AST)
    for match in _rg_json(_ENDPOINT_PATTERN, project_root, _JS_GLOBS):
        f = _to_finding(match, SIGNAL_HARDCODED_ENDPOINT, project_root)
        if f:
            findings.append(f)

    # Cloud model names in JS/TS (Python is covered by AST visit_Assign + visit_Call)
    for match in _rg_json(_MODEL_PATTERN, project_root, _JS_GLOBS + ["-i"]):
        f = _to_finding(match, SIGNAL_HARDCODED_MODEL, project_root)
        if f:
            findings.append(f)

    # Provider-coupled response parsing (all languages — AST misses chained subscript access)
    if _RESPONSE_PARSING_PATTERN:
        for match in _rg_json(_RESPONSE_PARSING_PATTERN, project_root, _ALL_GLOBS):
            f = _to_finding(match, SIGNAL_PROVIDER_RESPONSE_PARSING, project_root)
            if f:
                findings.append(f)

    # Strict tool schema (all languages)
    for match in _rg_json(_STRICT_TOOL_PATTERN, project_root, _ALL_GLOBS):
        f = _to_finding(match, SIGNAL_PROVIDER_FEATURE, project_root)
        if f:
            f.extra["feature"] = "strict=True in tool/function schema"
            findings.append(f)

    # Telemetry env vars referenced in JS/TS (Python covered by AST os.getenv detection)
    for match in _rg_json(_TELEMETRY_ENV_PATTERN, project_root, _JS_GLOBS):
        f = _to_finding(match, SIGNAL_TELEMETRY_CALLBACK, project_root)
        if f:
            findings.append(f)

    return findings


def scan_js_ts_project(project_root: Path) -> list[Finding]:
    try:
        return _scan_js_ts_project(project_root)
    except (OSError, UnicodeError, re.error) as error:
        return [scan_error(project_root, error)]
