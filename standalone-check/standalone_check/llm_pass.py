"""
Optional LLM refinement pass — catches fuzzy cases the AST/grep missed
(e.g. custom provider wrappers, indirect client construction).

The checker's own LLM client is OpenAI-compatible with base_url read from
STANDALONE_CHECK_BASE_URL so that the tool passes its own conformance check.
Skippable via --no-llm (or by not setting STANDALONE_CHECK_BASE_URL).
"""
import json
import os
from typing import Optional

from .verdict import ProjectReport

_SYSTEM = (
    "You are a strict LLM-portability auditor. "
    "Respond with JSON only — no prose, no markdown fences."
)

_USER_TMPL = """\
Project: {project}

Static analysis findings:
{findings}

Code snippets (first ~500 chars each file):
{snippets}

Task: identify any additional lock-in signals that static analysis missed
(e.g. custom provider wrappers, indirect client construction, env vars that
resolve to cloud endpoints, hard-coded model names inside helper functions).

Respond as JSON:
{{
  "extra_blockers": [
    {{"type": "...", "severity": "high|medium|low", "location": "file:line", "fix": "..."}}
  ],
  "notes": "one sentence summary or empty string"
}}
"""


def run_llm_pass(
    project_name: str,
    source_snippets: list[str],
    current_report: ProjectReport,
) -> Optional[str]:
    """
    Returns additional notes (string) or None if the pass was skipped.
    Never raises — failures are returned as a note string.
    """
    base_url = os.getenv("STANDALONE_CHECK_BASE_URL")
    if not base_url:
        return None

    api_key = os.getenv("STANDALONE_CHECK_API_KEY", "dummy")
    model = os.getenv("STANDALONE_CHECK_MODEL", "llama3.2:3b")

    try:
        import openai  # imported late so Phase 1 --no-llm needs no openai
    except ImportError:
        return "LLM pass skipped: openai package not installed"

    client = openai.OpenAI(base_url=base_url, api_key=api_key)

    prompt = _USER_TMPL.format(
        project=project_name,
        findings=json.dumps(current_report.blockers, indent=2),
        snippets="\n---\n".join(source_snippets[:8]),
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=512,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        parsed = json.loads(raw)
        return parsed.get("notes", "")
    except Exception as exc:
        return f"LLM pass error: {exc}"
