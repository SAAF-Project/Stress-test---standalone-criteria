"""
Scan non-Python config and dependency files for LLM lock-in signals.

Covers:
  - requirements*.txt, pyproject.toml, setup.cfg  (dependency lists)
  - .env, .env.example                            (hardcoded env values)
  - *.yaml, *.yml                                 (LLM config blocks)
"""
from __future__ import annotations

import re
from pathlib import Path

from .python_ast import Finding
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
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
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
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = _DEP_LINE_RE.match(line)
        if not m:
            continue
        pkg = _norm(m.group(1))
        if pkg in _LLM_PKG_NORM:
            findings.append(Finding(
                signal=SIGNAL_CLOUD_SDK,
                file=str(path),
                line=lineno,
                snippet=line.strip(),
                extra={"sdk": m.group(1), "reason": _LLM_PKG_NORM[pkg], "source": "pyproject.toml"},
            ))
    return findings


def _scan_env_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
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
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
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

    for req in sorted(project_root.rglob("requirements*.txt")):
        if _SKIP_PARTS & set(req.parts):
            continue
        scanned.append(req)
        findings.extend(_scan_requirements(req))

    for toml in sorted(project_root.rglob("pyproject.toml")):
        if _SKIP_PARTS & set(toml.parts):
            continue
        scanned.append(toml)
        findings.extend(_scan_toml(toml))

    for setup in sorted(project_root.rglob("setup.cfg")):
        if _SKIP_PARTS & set(setup.parts):
            continue
        scanned.append(setup)
        findings.extend(_scan_requirements(setup))

    for env in sorted(project_root.rglob(".env*")):
        if not env.is_file() or _SKIP_PARTS & set(env.parts):
            continue
        scanned.append(env)
        findings.extend(_scan_env_file(env))

    for yml in sorted(list(project_root.rglob("*.yaml")) + list(project_root.rglob("*.yml"))):
        if _SKIP_PARTS & set(yml.parts):
            continue
        scanned.append(yml)
        findings.extend(_scan_yaml(yml))

    return findings, scanned
