"""
EU AI Act Compliance Agent — Claude API logic
SAAF Hackathon

This module handles all interaction with the Claude API.
It is kept separate from the UI (chatbot.py) so the logic can be
tested independently.
"""

from pathlib import Path
import anthropic

# ── Constants ────────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

# Paths relative to this file's location (app/)
PROJECT_ROOT = Path(__file__).parent.parent
REGULATORY_DIR = PROJECT_ROOT / "regulatory"
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "system-instructions"

# Map display names (used in the Streamlit UI) to regulatory file names
REGULATORY_FILES = {
    "Current EU AI Act (2024/1689)": "eu-ai-act-current.md",
    "Digital Omnibus Proposal (2025/0836)": "eu-ai-act-omnibus.md",
}


# ── Functions ─────────────────────────────────────────────────────────────────

def load_regulatory_content(version: str) -> str:
    """
    Load the regulatory knowledge base for the selected version.

    Args:
        version: Display name of the regulatory version, e.g.
                 "Current EU AI Act (2024/1689)"

    Returns:
        The full text of the regulatory Markdown file as a string.
    """
    filename = REGULATORY_FILES.get(version)
    if not filename:
        raise ValueError(f"Unknown regulatory version: '{version}'. "
                         f"Valid options: {list(REGULATORY_FILES.keys())}")

    file_path = REGULATORY_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(
            f"Regulatory file not found: {file_path}\n"
            f"Make sure the file exists at {REGULATORY_DIR}"
        )

    return file_path.read_text(encoding="utf-8")


def build_system_prompt(version: str) -> str:
    """
    Build the full system prompt by loading the template and injecting
    the regulatory version name and content.

    Args:
        version: Display name of the regulatory version.

    Returns:
        The complete system prompt string ready to send to the API.
    """
    template_path = PROMPTS_DIR / "eu-ai-act-agent.md"
    if not template_path.exists():
        raise FileNotFoundError(
            f"System prompt template not found: {template_path}"
        )

    template = template_path.read_text(encoding="utf-8")
    regulatory_content = load_regulatory_content(version)

    # Replace placeholders in the template
    system_prompt = template.replace("[REGULATORY_VERSION]", version)
    system_prompt = system_prompt.replace("[REGULATORY_CONTENT]", regulatory_content)

    return system_prompt


def get_client(api_key: str) -> anthropic.Anthropic:
    """
    Create and return an Anthropic API client.

    Args:
        api_key: Your Anthropic API key (starts with sk-ant-...)

    Returns:
        An authenticated Anthropic client instance.
    """
    if not api_key or not api_key.strip():
        raise ValueError("API key is empty. Please provide a valid Anthropic API key.")
    return anthropic.Anthropic(api_key=api_key.strip())


def send_message(messages: list, system_prompt: str, client: anthropic.Anthropic) -> str:
    """
    Send the conversation history to Claude and return the response text.

    Args:
        messages: List of message dicts in Anthropic format:
                  [{"role": "user", "content": "..."}, ...]
                  Must start with a "user" role message.
        system_prompt: The full system prompt to use for this request.
        client: An authenticated Anthropic client (from get_client()).

    Returns:
        The assistant's response as a plain string.
    """
    if not messages:
        raise ValueError("Messages list is empty. At least one user message is required.")

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )

    # Extract the text content from the response
    return response.content[0].text
