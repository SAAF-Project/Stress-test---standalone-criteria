"""
Streamlit web interface for standalone-check.

Launch with:  standalone-check-web
         or:  streamlit run standalone_check/web.py
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

from standalone_check.cli import _discover_projects
from standalone_check.llm_pass import run_llm_pass
from standalone_check.scanner.config_files import scan_config_files
from standalone_check.scanner.python_ast import Finding, scan_python_project
from standalone_check.scanner.ripgrep import scan_js_ts_project
from standalone_check.scanner.signals import (
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
    SIGNAL_PROVIDER_RESPONSE_PARSING,
    SIGNAL_TELEMETRY_CALLBACK,
)
from standalone_check.verdict import ProjectReport, compute_verdict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_VERDICT_ICON = {"yes": "✅", "partial": "⚠️", "no": "❌"}
_VERDICT_COLOR = {"yes": "green", "partial": "orange", "no": "red"}
_SEV_ICON = {"high": "🔴", "medium": "🟡", "low": "⚪"}
_VERDICT_ORDER = {"no": 0, "partial": 1, "yes": 2}

# Human-readable label for each signal type
_SIGNAL_LABEL: dict[str, str] = {
    "hardcoded_cloud_endpoint":   "Cloud URL hardcoded",
    "hardcoded_api_key":          "API key hardcoded in source",
    "cloud_only_api":             "Uses a cloud-only feature",
    "endpoint_not_configurable":  "Server address is not configurable",
    "hardcoded_model_name":       "Model name hardcoded",
    "cloud_sdk_import":              "Cloud-specific library detected",
    "openai_client_detected":        "OpenAI-compatible client found",
    "non_openai_compatible_sdk":             "SDK cannot target a local model",
    "provider_specific_request_feature":    "Provider-specific API feature used",
    "api_key_format_assumption":            "Assumes cloud API key format",
    "cloud_embeddings_dependency":          "Cloud embedding service hard-wired",
    "cloud_vector_store":                   "Cloud vector store / retrieval used",
    "multimodal_assumption":                "Vision or audio capability assumed",
    "provider_coupled_response_parsing":    "Reads provider-specific response format",
    "telemetry_callback":                   "Telemetry / tracing phones home",
    "cloud_iam_in_model_path":              "Cloud identity credentials required",
    "long_context_assumption":              "Large context window assumed",
}

# One sentence that explains why the signal is a problem
_SIGNAL_EXPLANATION: dict[str, str] = {
    "hardcoded_cloud_endpoint": (
        "The code contains a fixed URL pointing to a cloud provider's servers. "
        "A local model lives at a different address, so the agent can't reach it."
    ),
    "hardcoded_api_key": (
        "An API key is written directly in the source code. "
        "This is also a security risk — keys should always live in environment variables."
    ),
    "cloud_only_api": (
        "The code calls a feature (e.g. OpenAI Assistants, DALL-E image generation) "
        "that only exists in the cloud. There is no local equivalent."
    ),
    "endpoint_not_configurable": (
        "The AI client is created without a way to point it at a different server. "
        "Swapping to a local model would require editing the source code."
    ),
    "hardcoded_model_name": (
        "The model name is written directly in the code. "
        "Local models have different names, so this line would need to change."
    ),
    "cloud_sdk_import": (
        "The code imports a library built specifically for one cloud provider "
        "(e.g. the Anthropic or AWS Bedrock SDK). "
        "Local models typically use the OpenAI-compatible SDK instead."
    ),
    "non_openai_compatible_sdk": (
        "The SDK in use (e.g. Anthropic, Bedrock) speaks a different protocol — "
        "it cannot be pointed at a local model without replacing it. "
        "A LiteLLM proxy can act as a bridge, or the openai SDK can be used directly."
    ),
    "provider_specific_request_feature": (
        "The code uses an API parameter (e.g. strict JSON schema mode, parallel tool calls, "
        "log probabilities) that many local models don't support. "
        "The agent may break even after the endpoint is swapped."
    ),
    "api_key_format_assumption": (
        "The code checks that the API key starts with 'sk-'. "
        "Local endpoints accept any dummy key string, so this validation will crash at startup."
    ),
    "cloud_embeddings_dependency": (
        "Embeddings are fetched from a cloud service separately from the chat model. "
        "Swapping the chat endpoint to local doesn't fix this — the embedding calls "
        "still reach the cloud."
    ),
    "cloud_vector_store": (
        "The agent stores or retrieves data from a managed cloud vector store (e.g. Pinecone). "
        "This is a data-egress finding: documents leave the tenant even when the model is local."
    ),
    "multimodal_assumption": (
        "The code sends images or audio to the model. "
        "Most local models are text-only — the request will fail if the local model "
        "doesn't support the same modality."
    ),
    "provider_coupled_response_parsing": (
        "The code reads a provider-specific field from the response "
        "(e.g. Anthropic's .content[0].text instead of .choices[0].message.content). "
        "This breaks as soon as the provider changes."
    ),
    "telemetry_callback": (
        "A tracing or analytics callback (e.g. LangSmith) sends data to a cloud endpoint "
        "even when the model itself is local. "
        "This is an egress finding that matters for air-gapped or in-tenant deployments."
    ),
    "cloud_iam_in_model_path": (
        "Reaching the model requires AWS or Azure identity credentials. "
        "A local endpoint accepts a simple API key — the IAM dependency must be removed "
        "from the model-access path."
    ),
    "long_context_assumption": (
        "A large token limit is hardcoded. Many local models cap at 4k–8k tokens; "
        "requests exceeding the limit will be silently truncated or rejected."
    ),
    "openai_client_detected": (
        "The code uses the OpenAI SDK, which is compatible with local models "
        "when pointed at the right server address."
    ),
}

# One-sentence verdict summaries
_VERDICT_HEADLINE: dict[str, str] = {
    "yes":     "This project can run against a local model with no code changes.",
    "partial": "This project is almost there — one or two small changes needed.",
    "no":      "This project cannot run locally without code changes.",
}


# ---------------------------------------------------------------------------
# GitHub URL helpers
# ---------------------------------------------------------------------------

def _is_git_url(s: str) -> bool:
    s = s.strip()
    return (
        s.startswith("https://github.com")
        or s.startswith("http://github.com")
        or s.startswith("git@github.com")
        or s.endswith(".git")
    )


def _clone_repo(url: str, dest: Path) -> tuple[bool, str]:
    """Shallow-clone url into dest. Returns (success, error_message)."""
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or "git clone failed"
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "Clone timed out after 120 s"
    except FileNotFoundError:
        return False, "`git` not found — is Git installed?"
    except Exception as exc:
        return False, str(exc)


def _cleanup_prev_tmp() -> None:
    prev = st.session_state.pop("_tmp_dir", None)
    if prev and Path(prev).exists():
        shutil.rmtree(prev, ignore_errors=True)


def _badge(verdict: str) -> str:
    icon = _VERDICT_ICON.get(verdict, "?")
    color = _VERDICT_COLOR.get(verdict, "gray")
    return f":{color}[**{icon} {verdict}**]"


def _verdict_reason(report: ProjectReport) -> str:
    """Return a plain-English sentence explaining why this verdict was given."""
    v = report.standalone_ready
    blockers = report.blockers

    if v == "yes":
        client = report.model_access["client"]
        if client == "openai":
            return (
                "The agent uses the OpenAI-compatible SDK and reads the server "
                "address from an environment variable — just point it at your local model."
            )
        if not blockers:
            return "No LLM lock-in was detected in the scanned source files."
        return _VERDICT_HEADLINE["yes"]

    if v == "no":
        high = [b for b in blockers if b["severity"] == "high"]
        if not high:
            return _VERDICT_HEADLINE["no"]
        top = high[0]["type"]
        if top == "hardcoded_cloud_endpoint":
            return (
                "The code has a cloud URL written directly into it. "
                "A local model lives at a different address, so the agent would never reach it."
            )
        if top == "hardcoded_api_key":
            return (
                "An API key is hardcoded in the source. "
                "This needs to move to an environment variable before anything else can change."
            )
        if top == "cloud_only_api":
            feat = high[0].get("location", "an unknown location")
            return (
                f"The code calls a cloud-only feature at {feat} "
                "that has no local equivalent."
            )
        return _VERDICT_HEADLINE["no"]

    # partial
    medium = [b for b in blockers if b["severity"] == "medium"]
    if not medium:
        return _VERDICT_HEADLINE["partial"]
    top = medium[0]["type"]
    if top == "endpoint_not_configurable":
        return (
            "The AI client is created without a configurable server address. "
            "Adding one line — base_url=os.getenv('OPENAI_BASE_URL') — would fix this."
        )
    if top == "hardcoded_model_name":
        extra = medium[0].get("location", "")
        return (
            f"A cloud model name is hardcoded at {extra}. "
            "Moving it to an environment variable is the only change needed."
        )
    return _VERDICT_HEADLINE["partial"]


# ---------------------------------------------------------------------------
# Scan logic (runs in-process, Streamlit spinner covers it)
# ---------------------------------------------------------------------------

def _collect_py_files(proj_dir: Path) -> list[Path]:
    _skip = {".venv", "venv", "__pycache__", ".tox", "site-packages", "node_modules"}
    return sorted(p for p in proj_dir.rglob("*.py") if not (_skip & set(p.parts)))


def _run_scan(
    repo_root: Path,
    only: list[str],
    no_llm: bool,
) -> tuple[list[ProjectReport], dict[str, dict]]:
    """Returns (reports, meta) where meta[project_name] has coverage details."""
    all_projects = _discover_projects(repo_root)
    if only:
        all_projects = [p for p in all_projects if p.name in only]

    if not all_projects:
        return [], {}

    reports: list[ProjectReport] = []
    meta: dict[str, dict] = {}

    progress = st.progress(0, text="Starting…")
    status = st.empty()

    for i, proj_dir in enumerate(all_projects):
        pct = int((i + 1) / len(all_projects) * 100)
        progress.progress(pct, text=f"Scanning **{proj_dir.name}** ({i+1}/{len(all_projects)})")

        py_files = _collect_py_files(proj_dir)
        status.caption(f"Reading {len(py_files)} Python files in `{proj_dir.name}`…")

        py_findings = scan_python_project(proj_dir)
        js_findings = scan_js_ts_project(proj_dir)
        cfg_findings, cfg_files = scan_config_files(proj_dir)
        all_findings = py_findings + js_findings + cfg_findings

        notes = ""
        if not no_llm:
            snippets: list[str] = []
            for py in py_files[:8]:
                try:
                    snippets.append(py.read_text(encoding="utf-8", errors="replace")[:500])
                except OSError:
                    pass
            prelim = compute_verdict(proj_dir.name, all_findings)
            notes = run_llm_pass(proj_dir.name, snippets, prelim) or ""

        report = compute_verdict(proj_dir.name, all_findings, notes=notes)
        reports.append(report)

        # Build per-signal finding map for coverage display
        by_signal: dict[str, list[Finding]] = {}
        for f in all_findings:
            by_signal.setdefault(f.signal.name, []).append(f)

        meta[proj_dir.name] = {
            "py_files": py_files,
            "cfg_files": cfg_files,
            "findings": all_findings,
            "by_signal": by_signal,
        }

    progress.empty()
    status.empty()
    return reports, meta


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

def _render_summary_table(reports: list[ProjectReport]) -> None:
    hdr = st.columns([3, 1, 6])
    hdr[0].markdown("**Project**")
    hdr[1].markdown("**Result**")
    hdr[2].markdown("**Why**")
    st.divider()

    for r in sorted(reports, key=lambda x: (_VERDICT_ORDER[x.standalone_ready], x.project)):
        row = st.columns([3, 1, 6])
        row[0].markdown(f"`{r.project}`")
        row[1].markdown(_badge(r.standalone_ready))
        row[2].markdown(_verdict_reason(r))


_ALL_SIGNALS = [
    # ── Original 6 ─────────────────────────────────────────────────────────
    (SIGNAL_HARDCODED_ENDPOINT,        "Cloud server URL hardcoded",              "Strings like api.openai.com written directly into source"),
    (SIGNAL_HARDCODED_KEY,             "API key hardcoded in source",             "Patterns like sk-... found in string literals"),
    (SIGNAL_CLOUD_ONLY_API,            "Cloud-only feature used",                 "Assistants API, DALL-E, fine-tuning — no local equivalent"),
    (SIGNAL_ENDPOINT_NOT_CONFIGURABLE, "Server address not configurable",         "OpenAI() called with no base_url= argument"),
    (SIGNAL_HARDCODED_MODEL,           "Cloud model name hardcoded",              "gpt-4, claude-3, etc. as a literal string in model="),
    (SIGNAL_CLOUD_SDK,                 "Cloud-specific library detected",         "import anthropic / boto3 / google.generativeai etc."),
    # ── New 9 ───────────────────────────────────────────────────────────────
    (SIGNAL_PROVIDER_FEATURE,          "Provider-specific API feature",           "response_format=json_schema, parallel_tool_calls, strict=True, logprobs, seed"),
    (SIGNAL_API_KEY_ASSUMPTION,        "Assumes cloud key format (sk-...)",       "Code validates key prefix — crashes with a dummy local key"),
    (SIGNAL_CLOUD_EMBEDDINGS,          "Cloud embedding service hard-wired",      "embeddings.create() or Voyage/OpenAI embedding SDK"),
    (SIGNAL_CLOUD_VECTOR_STORE,        "Cloud vector store (data egress)",        "Pinecone, Weaviate Cloud, Zilliz — docs leave the tenant"),
    (SIGNAL_MULTIMODAL_ASSUMPTION,     "Vision or audio input assumed",           "image_url / input_audio content type in messages"),
    (SIGNAL_PROVIDER_RESPONSE_PARSING, "Reads provider-specific response",        ".content[0].text (Anthropic) instead of .choices[0].message.content"),
    (SIGNAL_TELEMETRY_CALLBACK,        "Telemetry phones home",                   "LangSmith, W&B, Arize — egress even when model is local"),
    (SIGNAL_CLOUD_IAM,                 "Cloud IAM credentials in model path",     "Azure identity / Google auth / AWS credentials to reach model"),
    (SIGNAL_LONG_CONTEXT,              "Large context window assumed",            "max_tokens > 16 000 — many local models cap lower"),
]


def _render_scan_coverage(report: ProjectReport, coverage: dict) -> None:
    py_files: list[Path] = coverage.get("py_files", [])
    cfg_files: list[Path] = coverage.get("cfg_files", [])
    by_signal: dict[str, list] = coverage.get("by_signal", {})
    all_findings: list = coverage.get("findings", [])

    has_llm_usage = any(
        sig.name in by_signal
        for sig, _, _ in _ALL_SIGNALS
    ) or SIGNAL_OPENAI_CLIENT.name in by_signal

    with st.expander("📋 What we scanned and how we decided", expanded=True):

        # --- Files scanned ---
        c1, c2 = st.columns(2)
        c1.markdown("**Files inspected**")
        c1.markdown(
            f"- {len(py_files)} Python file(s)\n"
            f"- {len(cfg_files)} config/dependency file(s)\n"
        )
        if py_files or cfg_files:
            all_scanned = py_files + cfg_files
            c2.markdown("**File names**")
            # Show relative paths, truncated if many
            shown = all_scanned[:12]
            c2.markdown(
                "\n".join(f"- `{p.name}`" for p in shown)
                + (f"\n- … and {len(all_scanned)-12} more" if len(all_scanned) > 12 else "")
            )

        st.divider()

        # --- Signal checklist ---
        st.markdown("**Criteria checked — what we looked for and what we found**")

        for signal, label, description in _ALL_SIGNALS:
            hits = by_signal.get(signal.name, [])
            sev_icon = _SEV_ICON.get(signal.severity, "")
            sev_label = {"high": "Must fix", "medium": "Should fix", "low": "Info"}.get(signal.severity, "")

            if hits:
                locations = ", ".join(
                    f"`{Path(h.file).name}:{h.line}`" for h in hits[:3]
                ) + ("…" if len(hits) > 3 else "")
                result_md = f"🚨 **Found** ({len(hits)}×) — {locations}"
            else:
                result_md = "✅ Clean — not found"

            with st.container(border=False):
                col_a, col_b = st.columns([5, 7])
                col_a.markdown(f"{sev_icon} **{label}**  \n<small>{description}</small>", unsafe_allow_html=True)
                col_b.markdown(result_md)

        st.divider()

        # --- Interpretation ---
        if not has_llm_usage:
            st.warning(
                "**No LLM-related code or packages were detected in this repository.**  \n"
                "This could mean:\n"
                "- This repo doesn't use an AI/LLM (in which case the ✅ result is correct)\n"
                "- The LLM calls are hidden inside a custom wrapper or helper we didn't recognise\n"
                "- The repo uses a framework (LangChain, LlamaIndex, AutoGen…) that we don't yet cover\n\n"
                "If you know this project uses an LLM, enable the LLM pass in the sidebar for deeper analysis.",
                icon="⚠️",
            )
        elif report.standalone_ready == "yes":
            st.success(
                "All checks passed. The LLM client is configurable via environment variables — "
                "no hardcoded cloud dependencies were found. "
                "Run Phase 2 (runtime harness) to confirm at runtime.",
                icon="✅",
            )


def _render_project_card(report: ProjectReport, coverage: dict | None = None) -> None:
    icon = _VERDICT_ICON.get(report.standalone_ready, "?")
    label = f"{icon} {report.project}"
    expanded = report.standalone_ready != "yes"

    with st.expander(label, expanded=expanded):

        # --- Verdict headline ---
        color = _VERDICT_COLOR.get(report.standalone_ready, "gray")
        st.markdown(f"**:{color}[{_VERDICT_HEADLINE[report.standalone_ready]}]**")
        st.caption(_verdict_reason(report))

        st.divider()

        # --- Scan coverage (always shown) ---
        if coverage:
            _render_scan_coverage(report, coverage)
            st.divider()

        # --- Quick facts row ---
        c1, c2, c3 = st.columns(3)
        c1.metric("AI library used", report.model_access["client"])
        c2.metric(
            "Server address configurable?",
            "Yes ✅" if report.model_access["endpoint_configurable"] else "No ❌",
        )
        c3.metric(
            "Issues found",
            f"{len(report.blockers)} blocker(s)" if report.blockers else "None ✅",
        )

        # --- Issues ---
        if report.blockers:
            st.markdown("#### What needs to change")
            for b in report.blockers:
                sev = b["severity"]
                sev_icon = _SEV_ICON.get(sev, "")
                label_text = _SIGNAL_LABEL.get(b["type"], b["type"])
                explanation = _SIGNAL_EXPLANATION.get(b["type"], "")

                sev_label = {"high": "Must fix", "medium": "Should fix", "low": "Nice to fix"}.get(sev, sev)

                with st.container(border=True):
                    st.markdown(f"{sev_icon} **{label_text}** &nbsp;·&nbsp; *{sev_label}*")
                    if explanation:
                        st.markdown(explanation)
                    st.markdown(f"📍 Found at: `{b['location']}`")
                    st.info(f"**How to fix:** {b['fix']}", icon="💡")
        else:
            st.success(
                "No issues detected. This project looks ready to run against a local model.",
                icon="✅",
            )

        # --- Evidence (code snippets) ---
        if report.model_access["evidence"]:
            with st.expander("Show code evidence", expanded=False):
                for ev in report.model_access["evidence"]:
                    st.caption(f"{ev['file']} — line {ev['line']}")
                    st.code(ev["snippet"], language="python")

        # --- Cloud-only features ---
        if report.cloud_only_features:
            st.markdown("#### Cloud-only features in use")
            st.warning(
                "The following features have no local equivalent and would need "
                "to be removed or replaced:\n\n"
                + "\n".join(f"- `{f}`" for f in report.cloud_only_features),
                icon="⚠️",
            )

        # --- LLM notes ---
        if report.notes:
            st.markdown("#### Additional analysis")
            st.info(report.notes)

        # --- Download ---
        payload = json.dumps(
            {
                "project": report.project,
                "standalone_ready": report.standalone_ready,
                "model_access": report.model_access,
                "blockers": report.blockers,
                "cloud_only_features": report.cloud_only_features,
                "notes": report.notes,
            },
            indent=2,
        )
        st.download_button(
            "⬇ Download JSON report",
            data=payload,
            file_name=f"{report.project}.json",
            mime="application/json",
            key=f"dl_{report.project}",
        )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def _page() -> None:
    st.set_page_config(
        page_title="Standalone Check",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.title("🔍 Standalone Check")
        st.caption("Audit agent projects for self-hosted LLM readiness")
        st.divider()

        repo_input = st.text_input(
            "Local path or GitHub URL",
            placeholder="https://github.com/owner/repo  or  /local/path",
            help="Paste a GitHub repo URL or an absolute local path",
        )

        repo_root: Path | None = None
        project_names: list[str] = []
        input_is_url = False

        if repo_input:
            repo_input = repo_input.strip()
            if _is_git_url(repo_input):
                input_is_url = True
                st.info("GitHub URL detected — repo will be cloned when you run the scan.")
            else:
                candidate = Path(repo_input)
                if candidate.exists():
                    repo_root = candidate.resolve()
                    try:
                        project_names = [d.name for d in _discover_projects(repo_root)]
                    except Exception:
                        pass
                else:
                    st.error("Local path not found")

        only: list[str] = st.multiselect(
            "Filter projects",
            options=project_names,
            help="Leave empty to scan all (not available for URLs until after cloning)",
        )

        st.divider()
        no_llm = st.checkbox(
            "Skip LLM pass",
            value=True,
            help="Runs entirely offline. Uncheck to enable fuzzy analysis via a local model.",
        )

        if not no_llm:
            st.text_input(
                "Base URL",
                placeholder="http://localhost:11434/v1",
                key="llm_base_url",
                help="STANDALONE_CHECK_BASE_URL",
            )
            st.text_input(
                "Model",
                value="llama3.2:3b",
                key="llm_model",
                help="STANDALONE_CHECK_MODEL",
            )

        st.divider()
        scan_btn = st.button(
            "🚀 Run Scan",
            disabled=(not repo_input),
            use_container_width=True,
            type="primary",
        )

        if project_names:
            st.caption(f"Found **{len(project_names)}** project(s)")

    # ── Trigger scan ─────────────────────────────────────────────────────────
    if scan_btn and repo_input:
        import os

        _cleanup_prev_tmp()  # remove previous clone if any

        # --- resolve repo_root (clone if URL) ---
        if input_is_url:
            tmp_dir = tempfile.mkdtemp(prefix="standalone-check-")
            st.session_state["_tmp_dir"] = tmp_dir
            with st.status(f"Cloning `{repo_input}`…", expanded=True) as clone_status:
                ok, err = _clone_repo(repo_input, Path(tmp_dir))
            if not ok:
                st.error(f"Clone failed: {err}")
                st.stop()
            clone_status.update(label="Clone complete ✅", state="complete")
            repo_root = Path(tmp_dir)

        if not no_llm:
            base_url = st.session_state.get("llm_base_url", "")
            model = st.session_state.get("llm_model", "llama3.2:3b")
            if base_url:
                os.environ["STANDALONE_CHECK_BASE_URL"] = base_url
            os.environ["STANDALONE_CHECK_MODEL"] = model

        with st.spinner("Scanning…"):
            reports, meta = _run_scan(repo_root, only, no_llm)

        display_path = repo_input if input_is_url else str(repo_root)
        st.session_state["reports"] = reports
        st.session_state["meta"] = meta
        st.session_state["scanned_path"] = display_path

    # ── Results ──────────────────────────────────────────────────────────────
    reports: list[ProjectReport] = st.session_state.get("reports", [])
    meta: dict[str, dict] = st.session_state.get("meta", {})

    if not reports:
        st.markdown(
            """
            ## Welcome

            Enter the path to a monorepo in the sidebar and click **Run Scan**.

            The tool will inspect each subdirectory for LLM lock-in signals and
            report whether it can run against a self-hosted, OpenAI-compatible model.

            **15 criteria checked across 3 severity levels:**

            🔴 **Must fix** — agent cannot run locally without code changes
            | Criterion | What triggers it |
            |---|---|
            | Cloud server URL hardcoded | `api.openai.com`, `api.anthropic.com` etc. in source |
            | API key hardcoded | `sk-...` literal in source code |
            | Cloud-only feature used | Assistants API, DALL-E, fine-tuning — no local equivalent |
            | Cloud embedding service hard-wired | `embeddings.create()` / Voyage SDK while chat model is local |
            | Cloud vector store used | Pinecone, Weaviate Cloud — documents leave the tenant |
            | Cloud IAM credentials in model path | Azure AD / Google auth / AWS creds required to reach model |

            🟡 **Should fix** — agent may break after endpoint swap
            | Criterion | What triggers it |
            |---|---|
            | Server address not configurable | `OpenAI()` called with no `base_url=` |
            | Cloud model name hardcoded | `gpt-4`, `claude-3` etc. as a string literal |
            | Provider-specific API feature | `response_format=json_schema`, `parallel_tool_calls`, `strict=True`, `seed` |
            | Assumes cloud key format | Code calls `.startswith("sk-")` — fails with a dummy local key |
            | Vision or audio input assumed | `image_url` / `input_audio` content types — most local models are text-only |
            | Reads provider-specific response | `.content[0].text` (Anthropic) instead of `.choices[0].message.content` |
            | Telemetry phones home | LangSmith, W&B, Arize — egress even when model is local |

            ⚪ **Nice to fix** — informational, lower risk
            | Criterion | What triggers it |
            |---|---|
            | Cloud-specific SDK imported | `import anthropic` / `boto3` / `google.generativeai` |
            | Large context window assumed | `max_tokens > 16 000` — many local models cap lower |
            """
        )
        return

    scanned = st.session_state.get("scanned_path", "")
    st.success(f"Scanned **{len(reports)}** project(s) in `{scanned}`")

    # Metrics row
    counts = {"yes": 0, "partial": 0, "no": 0}
    for r in reports:
        counts[r.standalone_ready] += 1

    m1, m2, m3 = st.columns(3)
    m1.metric("✅ Standalone ready", counts["yes"])
    m2.metric("⚠️ Partial", counts["partial"])
    m3.metric("❌ Not ready", counts["no"])

    st.divider()
    st.subheader("Summary")
    _render_summary_table(reports)

    st.divider()
    st.subheader("Project details")

    # Sort: failures first, then partial, then yes; alpha within group
    sorted_reports = sorted(
        reports,
        key=lambda r: (_VERDICT_ORDER[r.standalone_ready], r.project),
    )
    for r in sorted_reports:
        _render_project_card(r, coverage=meta.get(r.project))

    # Download all
    st.divider()
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in reports:
            data = json.dumps(
                {
                    "project": r.project,
                    "standalone_ready": r.standalone_ready,
                    "model_access": r.model_access,
                    "blockers": r.blockers,
                    "cloud_only_features": r.cloud_only_features,
                    "notes": r.notes,
                },
                indent=2,
            )
            zf.writestr(f"{r.project}.json", data)

    st.download_button(
        "⬇ Download all reports (.zip)",
        data=zip_buf.getvalue(),
        file_name="standalone-check-reports.zip",
        mime="application/zip",
    )


# Streamlit re-executes this file on every interaction; guard so importing
# the module for the launch() console script doesn't trigger the UI code.
if __name__ == "__main__":
    _page()


# ---------------------------------------------------------------------------
# Console script launcher
# ---------------------------------------------------------------------------

def launch() -> None:
    """Launches the Streamlit web UI (registered as `standalone-check-web`)."""
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", __file__, "--server.headless", "false"],
        check=False,
    )
