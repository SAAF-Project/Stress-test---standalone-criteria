"""
Compute the standalone-readiness verdict from a list of findings.

Rules (applied in order):
  "no"      — any HIGH-severity blocker
  "partial" — no HIGH, but MEDIUM exists OR endpoint not configurable
  "yes"     — no HIGH or MEDIUM, endpoint is configurable (Phase 2 still needed)
"""
from dataclasses import dataclass, field
from typing import Literal

from .scanner.python_ast import Finding
from .scanner.signals import (
    CLOUD_SDK_IMPORTS,
    SIGNAL_CLOUD_ONLY_API,
    SIGNAL_CLOUD_SDK,
    SIGNAL_ENDPOINT_NOT_CONFIGURABLE,
    SIGNAL_HARDCODED_ENDPOINT,
    SIGNAL_HARDCODED_KEY,
    SIGNAL_HARDCODED_MODEL,
    SIGNAL_OPENAI_CLIENT,
    Signal,
)

# Injected medium blocker when a non-OpenAI-compat SDK is the sole LLM client
_SIGNAL_NON_COMPAT_SDK = Signal(
    name="non_openai_compatible_sdk",
    severity="medium",
    fix=(
        "Replace the vendor SDK with the openai package and point base_url at a "
        "LiteLLM proxy, or use litellm.completion() which wraps both."
    ),
)

Verdict = Literal["yes", "partial", "no"]


@dataclass
class ProjectReport:
    project: str
    standalone_ready: Verdict
    model_access: dict
    blockers: list[dict]
    cloud_only_features: list[str]
    notes: str


def _detect_client(findings: list[Finding]) -> str:
    for f in findings:
        if f.signal == SIGNAL_CLOUD_SDK:
            sdk = f.extra.get("sdk", "")
            if "anthropic" in sdk:
                return "anthropic"
            if "boto3" in sdk or "botocore" in sdk:
                return "bedrock"
            if "google" in sdk or "vertexai" in sdk:
                return "google"
            if "azure" in sdk.lower():
                return "azure"
            if "litellm" in sdk:
                return "litellm"
    # OpenAI client constructor detected (even when endpoint is clean)
    for f in findings:
        if f.signal == SIGNAL_OPENAI_CLIENT:
            return "openai"
    return "unknown"


def compute_verdict(
    project_name: str,
    findings: list[Finding],
    notes: str = "",
) -> ProjectReport:
    high = [f for f in findings if f.signal.severity == "high"]
    medium = [f for f in findings if f.signal.severity == "medium"]

    endpoint_configurable = not any(
        f.signal in (SIGNAL_ENDPOINT_NOT_CONFIGURABLE, SIGNAL_HARDCODED_ENDPOINT)
        for f in findings
    )

    client = _detect_client(findings)

    # Non-OpenAI-compatible SDKs (anthropic, bedrock, google) cannot be pointed
    # at a local model without code changes — treat as not configurable when
    # no OpenAI client is also present.
    _NON_COMPAT = {"anthropic", "bedrock", "google"}
    has_openai_client = any(f.signal == SIGNAL_OPENAI_CLIENT for f in findings)
    if client in _NON_COMPAT and not has_openai_client:
        endpoint_configurable = False

    evidence = [
        {"file": f.file, "line": f.line, "snippet": f.snippet}
        for f in findings
        if f.signal in (SIGNAL_HARDCODED_ENDPOINT, SIGNAL_ENDPOINT_NOT_CONFIGURABLE)
    ]

    blockers = [
        {
            "type": f.signal.name,
            "severity": f.signal.severity,
            "location": f"{f.file}:{f.line}",
            "fix": f.signal.fix,
        }
        for f in findings
        if f.signal.severity in ("high", "medium")
    ]

    # Inject a synthetic medium blocker for non-OpenAI-compatible SDKs
    if client in _NON_COMPAT and not has_openai_client and not high:
        sdk_finding = next(
            (f for f in findings if f.signal == SIGNAL_CLOUD_SDK and client in f.extra.get("sdk", "")),
            None,
        )
        loc = f"{sdk_finding.file}:{sdk_finding.line}" if sdk_finding else "unknown"
        blockers.insert(0, {
            "type": _SIGNAL_NON_COMPAT_SDK.name,
            "severity": "medium",
            "location": loc,
            "fix": _SIGNAL_NON_COMPAT_SDK.fix,
        })

    cloud_only = list({
        f.extra.get("namespace", f.snippet)
        for f in findings
        if f.signal == SIGNAL_CLOUD_ONLY_API
    })

    if high:
        verdict: Verdict = "no"
    elif medium or not endpoint_configurable:
        verdict = "partial"
    else:
        verdict = "yes"

    return ProjectReport(
        project=project_name,
        standalone_ready=verdict,
        model_access={
            "client": client,
            "endpoint_configurable": endpoint_configurable,
            "evidence": evidence,
        },
        blockers=blockers,
        cloud_only_features=cloud_only,
        notes=notes,
    )
