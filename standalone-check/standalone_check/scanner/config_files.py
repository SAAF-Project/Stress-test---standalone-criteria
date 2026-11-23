"""
Scan non-Python config and dependency files for LLM lock-in signals.

Covers:
  - requirements*.txt, pyproject.toml, setup.cfg  (dependency lists)
  - .env, .env.example                            (hardcoded env values)
  - *.yaml, *.yml                                 (LLM config blocks)
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .python_ast import Finding, scan_error
from .files import project_files, read_source
from .signals import (
    CLOUD_ENDPOINTS,
    CLOUD_SDK_IMPORTS,
    SIGNAL_CLOUD_SDK,
    SIGNAL_HARDCODED_ENDPOINT,
    SIGNAL_HARDCODED_KEY,
    Signal,
)

_SKIP_PARTS: frozenset[str] = frozenset(
    {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox"}
)

# LLM packages we recognise in dependency lists
_LLM_PACKAGES: dict[str, str] = {
    "anthropic":               "Anthropic SDK",
    "boto3":                   "AWS SDK (likely Bedrock)",
    "botocore":                "AWS SDK (likely Bedrock)",
    "google-generativeai":     "Google AI (Gemini) SDK",
    "google-cloud-aiplatform": "Vertex AI SDK",
    "vertexai":                "Vertex AI SDK",
    "cohere":                  "Cohere SDK",
    "mistralai":               "Mistral SDK",
    "together":                "Together AI SDK",
    "groq":                    "Groq SDK",
    "replicate":               "Replicate SDK",
    "openai":                  "OpenAI SDK",
    "litellm":                 "LiteLLM proxy SDK",
    "langchain":               "LangChain framework",
    "langchain-openai":        "LangChain OpenAI integration",
    "langchain-anthropic":     "LangChain Anthropic integration",
    "langchain-google-genai":  "LangChain Google integration",
    "llama-index":             "LlamaIndex framework",
    "llama_index":             "LlamaIndex framework",
    "llama-cpp-python":        "llama.cpp Python binding",
    "autogen":                 "AutoGen framework",
    "crewai":                  "CrewAI framework",
    "pydantic-ai":             "PydanticAI framework",
    "smolagents":              "SmolAgents (HuggingFace)",
}

# Normalise package names for matching (lowercase, hyphens == underscores)
_LLM_PKG_NORM: dict[str, str] = {
    k.lower().replace("-", "_"): v for k, v in _LLM_PACKAGES.items()
}

_API_KEY_RE = re.compile(r"(?:sk-[A-Za-z0-9\-_]{20,}|sk-ant-[A-Za-z0-9\-_]{20,})")
_DEP_LINE_RE = re.compile(r"^\s*([A-Za-z0-9_\-]+)", re.MULTILINE)


def _norm(name: str) -> str:
    return name.lower().replace("-", "_")


# ---------------------------------------------------------------------------
# Internal scanners
# ---------------------------------------------------------------------------

def _scan_requirements(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = read_source(path)
    except (OSError, UnicodeError) as error:
        return [scan_error(path, error)]
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _DEP_LINE_RE.match(line)
        if not m:
            continue
        pkg = _norm(m.group(1))
        if pkg in _LLM_PKG_NORM:
            findings.append(Finding(
                signal=SIGNAL_CLOUD_SDK,
                file=str(path),
                line=lineno,
                snippet=line,
                extra={"sdk": m.group(1), "reason": _LLM_PKG_NORM[pkg], "source": "requirements"},
            ))
    return findings


def _scan_toml(path: Path) -> list[Finding]:
    try:
        document = tomllib.loads(read_source(path))
        project = document.get("project", {})
        dependencies = project.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise ValueError("Dependencies must be an array")
        dependencies = list(dependencies)
        for group in project.get("optional-dependencies", {}).values():
            if not isinstance(group, list):
                raise ValueError("Optional dependencies must be arrays")
            dependencies.extend(group)
        poetry = document.get("tool", {}).get("poetry", {}).get("dependencies", {})
        if not isinstance(poetry, dict):
            raise ValueError("Poetry dependencies must be a table")
        dependencies.extend(poetry)
        if not all(isinstance(item, str) for item in dependencies):
            raise ValueError("Invalid dependency entry")
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError) as error:
        return [scan_error(path, error)]
    findings = []
    for dep in dependencies:
        match = _DEP_LINE_RE.match(dep)
        if match and _norm(match.group(1)) in _LLM_PKG_NORM:
            package = match.group(1)
            findings.append(Finding(
                SIGNAL_CLOUD_SDK, str(path), 0, package,
                {"sdk": package, "source": "pyproject.toml",
                 "reason": _LLM_PKG_NORM[_norm(package)]},
            ))
    return findings


def _scan_env_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = read_source(path)
    except (OSError, UnicodeError) as error:
        return [scan_error(path, error)]
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Hardcoded cloud endpoint in env var value
        for ep in CLOUD_ENDPOINTS:
            if ep in line:
                findings.append(Finding(
                    signal=SIGNAL_HARDCODED_ENDPOINT,
                    file=str(path),
                    line=lineno,
                    snippet=line,
                    extra={"endpoint": ep, "source": "env_file"},
                ))
                break
        # Hardcoded API key value
        if _API_KEY_RE.search(line):
            findings.append(Finding(
                signal=SIGNAL_HARDCODED_KEY,
                file=str(path),
                line=lineno,
                snippet="<redacted key>",
                extra={"source": "env_file"},
            ))
    return findings


def _scan_yaml(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = read_source(path)
    except (OSError, UnicodeError) as error:
        return [scan_error(path, error)]
    for lineno, line in enumerate(text.splitlines(), 1):
        for ep in CLOUD_ENDPOINTS:
            if ep in line:
                findings.append(Finding(
                    signal=SIGNAL_HARDCODED_ENDPOINT,
                    file=str(path),
                    line=lineno,
                    snippet=line.strip()[:200],
                    extra={"endpoint": ep, "source": "yaml"},
                ))
                break
    return findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_config_files(project_root: Path) -> tuple[list[Finding], list[Path]]:
    """
    Returns (findings, files_scanned).
    files_scanned is every config file we looked at (whether or not it had findings).
    """
    findings: list[Finding] = []
    scanned: list[Path] = []

    try:
        paths = project_files(project_root)
    except OSError as error:
        return [scan_error(project_root, error)], []
    for path in paths:
        scanner = None
        if path.match("requirements*.txt") or path.name == "setup.cfg":
            scanner = _scan_requirements
        elif path.name == "pyproject.toml":
            scanner = _scan_toml
        elif path.name.startswith(".env"):
            scanner = _scan_env_file
        elif path.suffix in {".yaml", ".yml"}:
            scanner = _scan_yaml
        if scanner:
            scanned.append(path)
            findings.extend(scanner(path))
    return findings, scanned
