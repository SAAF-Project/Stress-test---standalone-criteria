"""
AST-based scanner for Python files.

Uses ast.NodeVisitor — never regex on Python source — to find:
  - Client instantiations and whether they have a configurable base_url
  - Cloud-only API namespace access
  - Hardcoded endpoint strings and API keys in string constants
  - Cloud SDK imports
  - Hardcoded model names in model= keyword args
  - Provider-specific request features (response_format, parallel_tool_calls, …)
  - API-key format assumptions (startswith("sk-") checks)
  - Cloud embedding API calls
  - Cloud vector store / telemetry / cloud IAM imports
  - Multimodal content types in message construction
  - Large max_tokens values (long-context assumptions)
"""
import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .signals import (
    CLOUD_EMBEDDING_IMPORTS,
    CLOUD_EMBEDDING_NAMESPACES,
    CLOUD_ENDPOINTS,
    CLOUD_IAM_IMPORTS,
    CLOUD_MODEL_PATTERNS,
    CLOUD_ONLY_NAMESPACES,
    CLOUD_SDK_IMPORTS,
    CLOUD_VECTOR_STORE_IMPORTS,
    CONFIGURABLE_KWARGS,
    LITELLM_IMPORTS,
    LONG_CONTEXT_TOKEN_THRESHOLD,
    MULTIMODAL_CONTENT_TYPES,
    PROVIDER_SPECIFIC_KWARGS,
    TELEMETRY_ENV_VARS,
    TELEMETRY_IMPORTS,
    SIGNAL_API_KEY_ASSUMPTION,
    SIGNAL_CLOUD_EMBEDDINGS,
    SIGNAL_CLOUD_IAM,
    SIGNAL_CLOUD_ONLY_API,
    SIGNAL_CLOUD_SDK,
    SIGNAL_CLOUD_VECTOR_STORE,
    SIGNAL_ENDPOINT_NOT_CONFIGURABLE,
    SIGNAL_HARDCODED_ENDPOINT,
    SIGNAL_HARDCODED_KEY,
    SIGNAL_HARDCODED_MODEL,
    SIGNAL_LONG_CONTEXT,
    SIGNAL_MULTIMODAL_ASSUMPTION,
    SIGNAL_OPENAI_CLIENT,
    SIGNAL_PROVIDER_FEATURE,
    SIGNAL_TELEMETRY_CALLBACK,
    Signal,
)

_API_KEY_RE = re.compile(
    r"(?:sk-[A-Za-z0-9\-_]{20,}|sk-ant-[A-Za-z0-9\-_]{20,})"
)
_MODEL_RES = [re.compile(p, re.IGNORECASE) for p in CLOUD_MODEL_PATTERNS]

# OpenAI client constructor names we recognise
_OPENAI_CLIENT_NAMES: set[str] = {
    "openai.OpenAI", "openai.AsyncOpenAI",
    "openai.AzureOpenAI", "openai.AsyncAzureOpenAI",
    "OpenAI", "AsyncOpenAI", "AzureOpenAI", "AsyncAzureOpenAI",
}


@dataclass
class Finding:
    signal: Signal
    file: str
    line: int
    snippet: str
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attr_chain(node: ast.expr) -> str:
    """Flatten a.b.c attribute chain to a dotted string (right-to-left)."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _string_value(node: ast.expr) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _line(node: ast.AST, lines: list[str]) -> str:
    ln = getattr(node, "lineno", 1) - 1
    return lines[ln].strip() if 0 <= ln < len(lines) else ""


# ---------------------------------------------------------------------------
# Visitor
# ---------------------------------------------------------------------------

class _PythonScanner(ast.NodeVisitor):
    def __init__(self, path: Path, source: str):
        self._path = path
        self._lines = source.splitlines()
        self.findings: list[Finding] = []

    def _finding(
        self, signal: Signal, node: ast.AST, extra: Optional[dict] = None
    ) -> Finding:
        return Finding(
            signal=signal,
            file=str(self._path),
            line=getattr(node, "lineno", 0),
            snippet=_line(node, self._lines),
            extra=extra or {},
        )

    # --- imports -----------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_import(alias.name, node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        self._check_import(mod, node)
        self.generic_visit(node)

    def _check_import(self, module: str, node: ast.AST) -> None:
        top = module.split(".")[0]
        two = ".".join(module.split(".")[:2])

        # Cloud SDK (existing)
        if top in CLOUD_SDK_IMPORTS:
            self.findings.append(self._finding(
                SIGNAL_CLOUD_SDK, node,
                {"sdk": module, "reason": CLOUD_SDK_IMPORTS[top]},
            ))
            return  # one finding per import is enough

        # Cloud embedding libraries
        for key, reason in CLOUD_EMBEDDING_IMPORTS.items():
            if module == key or top == key:
                self.findings.append(self._finding(
                    SIGNAL_CLOUD_EMBEDDINGS, node,
                    {"sdk": module, "reason": reason},
                ))
                return

        # Cloud vector stores
        for key, reason in CLOUD_VECTOR_STORE_IMPORTS.items():
            if module == key or top == key:
                self.findings.append(self._finding(
                    SIGNAL_CLOUD_VECTOR_STORE, node,
                    {"sdk": module, "reason": reason},
                ))
                return

        # Telemetry / callbacks
        for key, reason in TELEMETRY_IMPORTS.items():
            if module == key or top == key or module.startswith(key):
                self.findings.append(self._finding(
                    SIGNAL_TELEMETRY_CALLBACK, node,
                    {"sdk": module, "reason": reason},
                ))
                return

        # Cloud IAM
        for key, reason in CLOUD_IAM_IMPORTS.items():
            if module == key or module.startswith(key):
                self.findings.append(self._finding(
                    SIGNAL_CLOUD_IAM, node,
                    {"sdk": module, "reason": reason},
                ))
                return

    # --- string constants --------------------------------------------------

    def visit_Constant(self, node: ast.Constant) -> None:
        val = node.value

        if isinstance(val, str):
            # Hardcoded cloud endpoint
            for ep in CLOUD_ENDPOINTS:
                if ep in val:
                    self.findings.append(
                        self._finding(SIGNAL_HARDCODED_ENDPOINT, node, {"endpoint": ep})
                    )
                    break

            # Hardcoded API key
            m = _API_KEY_RE.search(val)
            if m:
                self.findings.append(self._finding(
                    SIGNAL_HARDCODED_KEY, node,
                    {"hint": f"key pattern at col {m.start()}"},
                ))

            # Multimodal content type marker
            if val in MULTIMODAL_CONTENT_TYPES:
                self.findings.append(self._finding(
                    SIGNAL_MULTIMODAL_ASSUMPTION, node,
                    {"content_type": val},
                ))

        elif isinstance(val, int):
            # Long-context assumption via large max_tokens literal
            # (caught in visit_Call for kwarg context; here we flag bare large ints
            #  only when they appear as a direct argument — handled in visit_Call)
            pass

        self.generic_visit(node)

    # --- assignments -------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        """Catch MODEL = "claude-opus-4-6" style assignments."""
        val = _string_value(node.value)
        if val:
            for rx in _MODEL_RES:
                if rx.search(val):
                    self.findings.append(
                        self._finding(SIGNAL_HARDCODED_MODEL, node, {"model": val})
                    )
                    break
        self.generic_visit(node)

    # --- calls -------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        func_str = _attr_chain(node.func)

        # OpenAI client instantiation
        if func_str in _OPENAI_CLIENT_NAMES:
            self.findings.append(self._finding(SIGNAL_OPENAI_CLIENT, node))
            if not self._has_configurable_endpoint(node):
                self.findings.append(
                    self._finding(SIGNAL_ENDPOINT_NOT_CONFIGURABLE, node)
                )

        # Cloud-only API namespaces
        for ns in CLOUD_ONLY_NAMESPACES:
            if ns in func_str:
                self.findings.append(
                    self._finding(SIGNAL_CLOUD_ONLY_API, node, {"namespace": ns})
                )
                break

        # Cloud embedding API calls
        for ns in CLOUD_EMBEDDING_NAMESPACES:
            if ns in func_str:
                self.findings.append(self._finding(
                    SIGNAL_CLOUD_EMBEDDINGS, node, {"call": func_str},
                ))
                break

        # API-key format assumption: something.startswith("sk-")
        if func_str.endswith(".startswith") or func_str == "startswith":
            if node.args:
                prefix = _string_value(node.args[0])
                if prefix and prefix.startswith("sk-"):
                    self.findings.append(self._finding(
                        SIGNAL_API_KEY_ASSUMPTION, node,
                        {"prefix": prefix},
                    ))

        # Scan keyword args for provider-specific features and long-context
        has_model_kwarg = any(kw.arg == "model" for kw in node.keywords)
        for kw in node.keywords:
            # Provider-specific request features (only in LLM calls that also have model=)
            if kw.arg in PROVIDER_SPECIFIC_KWARGS and has_model_kwarg:
                # Skip response_format={"type": "json_object"} — widely supported
                if kw.arg == "response_format":
                    val = kw.value
                    if isinstance(val, ast.Dict):
                        # Flag only json_schema (strict mode) not plain json_object
                        for k, v in zip(val.keys, val.values):
                            if _string_value(k) == "type" and _string_value(v) == "json_schema":
                                self.findings.append(self._finding(
                                    SIGNAL_PROVIDER_FEATURE, node,
                                    {"feature": "response_format=json_schema (strict structured output)"},
                                ))
                else:
                    self.findings.append(self._finding(
                        SIGNAL_PROVIDER_FEATURE, node,
                        {"feature": kw.arg},
                    ))

            # Long-context assumption: max_tokens > threshold
            if kw.arg == "max_tokens":
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
                    if kw.value.value > LONG_CONTEXT_TOKEN_THRESHOLD:
                        self.findings.append(self._finding(
                            SIGNAL_LONG_CONTEXT, node,
                            {"max_tokens": kw.value.value},
                        ))

        # Telemetry env var reads (os.getenv("LANGSMITH_API_KEY") etc.)
        if func_str in {"os.getenv", "os.environ.get", "environ.get"}:
            if node.args:
                v = _string_value(node.args[0])
                if v and v in TELEMETRY_ENV_VARS:
                    self.findings.append(self._finding(
                        SIGNAL_TELEMETRY_CALLBACK, node,
                        {"env_var": v, "reason": "Telemetry env var read"},
                    ))

        # Hardcoded model= kwarg
        for kw in node.keywords:
            if kw.arg == "model":
                val = _string_value(kw.value)
                if val:
                    for rx in _MODEL_RES:
                        if rx.search(val):
                            self.findings.append(
                                self._finding(
                                    SIGNAL_HARDCODED_MODEL, node, {"model": val}
                                )
                            )
                            break

        self.generic_visit(node)

    # --- helpers -----------------------------------------------------------

    def _has_configurable_endpoint(self, node: ast.Call) -> bool:
        """
        Return True if the client constructor has a base_url (or equivalent) kwarg present.
        Cloud-URL detection is handled separately by visit_Constant, so we only check
        for *presence* here — absence means "not configurable".
        """
        return any(kw.arg in CONFIGURABLE_KWARGS for kw in node.keywords)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_SKIP_PARTS: frozenset[str] = frozenset(
    {".venv", "venv", "__pycache__", ".tox", "site-packages", "node_modules"}
)


def scan_python_file(path: Path) -> list[Finding]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    scanner = _PythonScanner(path, source)
    scanner.visit(tree)
    return scanner.findings


def scan_python_project(project_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for py in sorted(project_root.rglob("*.py")):
        if _SKIP_PARTS & set(py.parts):
            continue
        findings.extend(scan_python_file(py))
    return findings
