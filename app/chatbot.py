"""
EU AI Act Compliance Chatbot — Streamlit Web App
SAAF Hackathon

Run with:
    streamlit run app/chatbot.py

This is the main entry point. It handles the web UI and conversation state.
The Claude API logic lives in agent.py.
"""

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Add the project root to the Python path so we can import agent.py
sys.path.insert(0, str(Path(__file__).parent))
from agent import build_system_prompt, get_client, send_message

# ── Load environment variables ────────────────────────────────────────────────
# Look for .env in the SAAF parent directory (where it already exists)
# or in the project root — whichever is found first.
_project_root = Path(__file__).parent.parent
for _env_path in [_project_root.parent / ".env", _project_root / ".env"]:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EU AI Act Compliance Assessment",
    page_icon="⚖️",
    layout="centered",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚖️ EU AI Act")
    st.caption("Compliance Assessment Tool")
    st.divider()

    # API Key
    st.subheader("🔑 API Key")
    env_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if env_api_key:
        st.success("API key loaded from environment")
        api_key = env_api_key
    else:
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            placeholder="sk-ant-...",
            help=(
                "Get your API key from console.anthropic.com. "
                "It starts with 'sk-ant-'. "
                "Alternatively, add ANTHROPIC_API_KEY to your .env file."
            ),
        )
        if api_key:
            st.success("API key entered")
        else:
            st.warning("Enter your API key to begin")

    st.divider()

    # Regulatory version toggle
    st.subheader("📋 Regulatory Version")
    regulatory_version = st.radio(
        "Assess against:",
        options=[
            "Current EU AI Act (2024/1689)",
            "Digital Omnibus Proposal (2025/0836)",
        ],
        index=0,
        help=(
            "Toggle between the current law and the proposed amendments. "
            "Switching will start a new assessment."
        ),
    )

    if "Current" in regulatory_version:
        st.info(
            "**Regulation (EU) 2024/1689**\n\n"
            "In force since August 2024. "
            "Full obligations apply in phases through 2027.",
            icon="ℹ️",
        )
    else:
        st.warning(
            "**COM/2025/0836 — Proposed**\n\n"
            "Not yet in force. "
            "Proposed amendments to reduce burden on SMEs and clarify definitions.",
            icon="⚠️",
        )

    st.divider()

    # New assessment button
    if st.button("🔄 Start New Assessment", use_container_width=True):
        st.session_state.messages = []
        st.session_state.last_regulatory_version = regulatory_version
        st.rerun()

    st.divider()
    st.caption(
        "SAAF Hackathon · Powered by Claude\n\n"
        "This tool provides preliminary compliance screening, "
        "not legal advice."
    )

# ── Session state initialisation ──────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_regulatory_version" not in st.session_state:
    st.session_state.last_regulatory_version = regulatory_version

# ── Handle regulatory version toggle mid-conversation ─────────────────────────
if regulatory_version != st.session_state.last_regulatory_version:
    st.session_state.messages = []
    st.session_state.last_regulatory_version = regulatory_version
    st.rerun()

# ── Main header ───────────────────────────────────────────────────────────────
st.title("EU AI Act Compliance Assessment")
st.caption(
    f"Assessing under: **{regulatory_version}** · "
    "Ask me about your AI system and I'll help determine its risk classification."
)

# ── Opening message (shown on first load, not sent to API) ─────────────────────
OPENING_MESSAGE = """\
Welcome! I'm your EU AI Act compliance assessment assistant.

I'll guide you through a structured assessment to determine the **risk classification** of your AI system and the **requirements** that apply to it under EU law.

To get started, please tell me about your AI system across these four dimensions:

1. **What does it do?** — Describe the AI tool or solution in plain language.
2. **Where is it hosted?** — For example: cloud service (AWS, Azure), on-premise servers, a SaaS platform, a mobile app.
3. **What data does it process?** — For example: personal data, financial records, medical information, images of people, employee data.
4. **How can it impact users?** — What decisions does it make or support? Who is affected, and can a human override the AI's output?

You can answer all four questions at once, or we can go through them one by one. Just start typing below!
"""

if not st.session_state.messages:
    with st.chat_message("assistant", avatar="⚖️"):
        st.markdown(OPENING_MESSAGE)

# ── Display conversation history ──────────────────────────────────────────────
for msg in st.session_state.messages:
    avatar = "⚖️" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ── Guard: no API key ─────────────────────────────────────────────────────────
if not api_key:
    st.info("👈 Enter your Anthropic API key in the sidebar to begin the assessment.")
    st.stop()

# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input(
    "Describe your AI system or answer the questions above…",
    key="chat_input",
)

if user_input:
    # Display user message
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Build the API messages list (only user/assistant turns from session)
    api_messages = st.session_state.messages.copy()

    # Call Claude
    try:
        system_prompt = build_system_prompt(regulatory_version)
        client = get_client(api_key)

        with st.chat_message("assistant", avatar="⚖️"):
            with st.spinner("Analyzing…"):
                response_text = send_message(api_messages, system_prompt, client)
            st.markdown(response_text)

        st.session_state.messages.append(
            {"role": "assistant", "content": response_text}
        )

    except ValueError as e:
        st.error(f"Configuration error: {e}")
    except Exception as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "api_key" in error_msg.lower() or "401" in error_msg:
            st.error(
                "**Invalid API key.** Please check your Anthropic API key in the sidebar. "
                "It should start with 'sk-ant-' and be copied exactly from console.anthropic.com."
            )
        else:
            st.error(f"An error occurred while contacting the API: {e}")
