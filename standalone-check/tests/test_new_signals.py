"""
Tests for the 9 new portability signals plus gaps in the existing 6.

Covers:
  - SIGNAL_PROVIDER_FEATURE (response_format json_schema, parallel_tool_calls, strict tool schema)
  - SIGNAL_API_KEY_ASSUMPTION (startswith "sk-")
  - SIGNAL_CLOUD_EMBEDDINGS (import + call)
  - SIGNAL_CLOUD_VECTOR_STORE (import)
  - SIGNAL_MULTIMODAL_ASSUMPTION (image_url content type)
  - SIGNAL_PROVIDER_RESPONSE_PARSING (content[0].text, delta.text via text scanner)
  - SIGNAL_TELEMETRY_CALLBACK (import + os.getenv)
  - SIGNAL_CLOUD_IAM (azure.identity import)
  - SIGNAL_LONG_CONTEXT (max_tokens > 16000)
  - SIGNAL_HARDCODED_MODEL via visit_Assign (new: MODEL = "claude-opus-4-6")
  - Claude 4 model patterns (claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5)
"""
import textwrap
from pathlib import Path

import pytest

from standalone_check.scanner.python_ast import scan_python_file
from standalone_check.scanner.ripgrep import scan_js_ts_project
from standalone_check.scanner.signals import (
    SIGNAL_API_KEY_ASSUMPTION,
    SIGNAL_CLOUD_EMBEDDINGS,
    SIGNAL_CLOUD_IAM,
    SIGNAL_CLOUD_VECTOR_STORE,
    SIGNAL_HARDCODED_MODEL,
    SIGNAL_LONG_CONTEXT,
    SIGNAL_MULTIMODAL_ASSUMPTION,
    SIGNAL_PROVIDER_FEATURE,
    SIGNAL_PROVIDER_RESPONSE_PARSING,
    SIGNAL_TELEMETRY_CALLBACK,
)


def _write(tmp_path: Path, src: str, name: str = "agent.py") -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(src))
    return p


def _signals(path: Path) -> list[str]:
    return [f.signal.name for f in scan_python_file(path)]


def _rg_signals(tmp_path: Path) -> list[str]:
    return [f.signal.name for f in scan_js_ts_project(tmp_path)]


# ---------------------------------------------------------------------------
# SIGNAL_HARDCODED_MODEL — new visit_Assign path + claude-4 patterns
# ---------------------------------------------------------------------------

class TestHardcodedModelNewPaths:
    def test_model_variable_assignment_caught(self, tmp_path):
        p = _write(tmp_path, 'MODEL = "claude-opus-4-6"\n')
        assert SIGNAL_HARDCODED_MODEL.name in _signals(p)

    def test_claude4_opus_pattern(self, tmp_path):
        p = _write(tmp_path, 'MODEL = "claude-opus-4-6"\n')
        assert SIGNAL_HARDCODED_MODEL.name in _signals(p)

    def test_claude4_sonnet_pattern(self, tmp_path):
        p = _write(tmp_path, 'MODEL = "claude-sonnet-4-6"\n')
        assert SIGNAL_HARDCODED_MODEL.name in _signals(p)

    def test_claude4_haiku_pattern(self, tmp_path):
        p = _write(tmp_path, 'MODEL = "claude-haiku-4-5"\n')
        assert SIGNAL_HARDCODED_MODEL.name in _signals(p)

    def test_claude3_still_caught(self, tmp_path):
        p = _write(tmp_path, 'MODEL = "claude-3-sonnet-20240229"\n')
        assert SIGNAL_HARDCODED_MODEL.name in _signals(p)

    def test_env_driven_model_not_flagged(self, tmp_path):
        src = """\
            import os
            MODEL = os.getenv("LLM_MODEL", "gpt-4o")
        """
        p = _write(tmp_path, src)
        assert SIGNAL_HARDCODED_MODEL.name not in _signals(p)


# ---------------------------------------------------------------------------
# SIGNAL_PROVIDER_FEATURE
# ---------------------------------------------------------------------------

class TestProviderFeature:
    def test_parallel_tool_calls_flagged(self, tmp_path):
        src = """\
            import openai
            client = openai.OpenAI(base_url="http://localhost:11434")
            client.chat.completions.create(
                model="llama3",
                parallel_tool_calls=False,
                messages=[],
            )
        """
        p = _write(tmp_path, src)
        assert SIGNAL_PROVIDER_FEATURE.name in _signals(p)

    def test_logprobs_flagged(self, tmp_path):
        src = """\
            import openai
            client = openai.OpenAI(base_url="http://localhost")
            client.chat.completions.create(model="x", logprobs=True, messages=[])
        """
        p = _write(tmp_path, src)
        assert SIGNAL_PROVIDER_FEATURE.name in _signals(p)

    def test_response_format_json_schema_flagged(self, tmp_path):
        src = """\
            import openai
            client = openai.OpenAI(base_url="http://localhost")
            client.chat.completions.create(
                model="x",
                response_format={"type": "json_schema", "json_schema": {}},
                messages=[],
            )
        """
        p = _write(tmp_path, src)
        assert SIGNAL_PROVIDER_FEATURE.name in _signals(p)

    def test_response_format_json_object_not_flagged(self, tmp_path):
        src = """\
            import openai
            client = openai.OpenAI(base_url="http://localhost")
            client.chat.completions.create(
                model="x",
                response_format={"type": "json_object"},
                messages=[],
            )
        """
        p = _write(tmp_path, src)
        assert SIGNAL_PROVIDER_FEATURE.name not in _signals(p)

    def test_strict_tool_schema_via_text_scanner(self, tmp_path):
        (tmp_path / "tools.py").write_text(
            'tools = [{"type": "function", "strict": true}]\n'
        )
        assert SIGNAL_PROVIDER_FEATURE.name in _rg_signals(tmp_path)

    def test_strict_true_python_dict_via_text_scanner(self, tmp_path):
        # Python dict uses capital True — pattern must match both cases
        (tmp_path / "agent.py").write_text(
            'tools = [{"strict": True, "name": "my_tool"}]\n'
        )
        assert SIGNAL_PROVIDER_FEATURE.name in _rg_signals(tmp_path)


# ---------------------------------------------------------------------------
# SIGNAL_API_KEY_ASSUMPTION
# ---------------------------------------------------------------------------

class TestApiKeyAssumption:
    def test_startswith_sk_flagged(self, tmp_path):
        src = """\
            def validate(key):
                if not key.startswith("sk-"):
                    raise ValueError("bad key")
        """
        p = _write(tmp_path, src)
        assert SIGNAL_API_KEY_ASSUMPTION.name in _signals(p)

    def test_startswith_sk_ant_flagged(self, tmp_path):
        src = """\
            def check(k):
                return k.startswith("sk-ant-")
        """
        p = _write(tmp_path, src)
        assert SIGNAL_API_KEY_ASSUMPTION.name in _signals(p)

    def test_other_startswith_not_flagged(self, tmp_path):
        src = 'assert token.startswith("Bearer ")\n'
        p = _write(tmp_path, src)
        assert SIGNAL_API_KEY_ASSUMPTION.name not in _signals(p)


# ---------------------------------------------------------------------------
# SIGNAL_CLOUD_EMBEDDINGS
# ---------------------------------------------------------------------------

class TestCloudEmbeddings:
    def test_voyageai_import_flagged(self, tmp_path):
        p = _write(tmp_path, "import voyageai\n")
        assert SIGNAL_CLOUD_EMBEDDINGS.name in _signals(p)

    def test_embeddings_create_call_flagged(self, tmp_path):
        src = """\
            import openai
            client = openai.OpenAI(base_url="http://localhost")
            resp = client.embeddings.create(model="text-embedding-ada-002", input="hello")
        """
        p = _write(tmp_path, src)
        assert SIGNAL_CLOUD_EMBEDDINGS.name in _signals(p)

    def test_langchain_openai_import_flagged(self, tmp_path):
        p = _write(tmp_path, "from langchain_openai import OpenAIEmbeddings\n")
        assert SIGNAL_CLOUD_EMBEDDINGS.name in _signals(p)


# ---------------------------------------------------------------------------
# SIGNAL_CLOUD_VECTOR_STORE
# ---------------------------------------------------------------------------

class TestCloudVectorStore:
    def test_pinecone_import_flagged(self, tmp_path):
        p = _write(tmp_path, "import pinecone\n")
        assert SIGNAL_CLOUD_VECTOR_STORE.name in _signals(p)

    def test_qdrant_import_flagged(self, tmp_path):
        p = _write(tmp_path, "from qdrant_client import QdrantClient\n")
        assert SIGNAL_CLOUD_VECTOR_STORE.name in _signals(p)

    def test_weaviate_import_flagged(self, tmp_path):
        p = _write(tmp_path, "import weaviate\n")
        assert SIGNAL_CLOUD_VECTOR_STORE.name in _signals(p)


# ---------------------------------------------------------------------------
# SIGNAL_MULTIMODAL_ASSUMPTION
# ---------------------------------------------------------------------------

class TestMultimodalAssumption:
    def test_image_url_type_flagged(self, tmp_path):
        src = """\
            msg = {"type": "image_url", "image_url": {"url": "data:..."}}
        """
        p = _write(tmp_path, src)
        assert SIGNAL_MULTIMODAL_ASSUMPTION.name in _signals(p)

    def test_input_audio_type_flagged(self, tmp_path):
        src = """\
            content = [{"type": "input_audio", "data": "..."}]
        """
        p = _write(tmp_path, src)
        assert SIGNAL_MULTIMODAL_ASSUMPTION.name in _signals(p)

    def test_text_content_type_not_flagged(self, tmp_path):
        src = '{"type": "text", "text": "hello"}\n'
        p = _write(tmp_path, src)
        assert SIGNAL_MULTIMODAL_ASSUMPTION.name not in _signals(p)


# ---------------------------------------------------------------------------
# SIGNAL_PROVIDER_RESPONSE_PARSING (text scanner)
# ---------------------------------------------------------------------------

class TestProviderResponseParsing:
    def test_anthropic_content_index_text_flagged(self, tmp_path):
        (tmp_path / "agent.py").write_text(
            'result = response.content[0].text\n'
        )
        assert SIGNAL_PROVIDER_RESPONSE_PARSING.name in _rg_signals(tmp_path)

    def test_anthropic_delta_text_flagged(self, tmp_path):
        # Anthropic streaming uses event.delta.text — the pattern matches "delta.text" anywhere
        (tmp_path / "agent.py").write_text(
            'yield delta.text\n'
        )
        assert SIGNAL_PROVIDER_RESPONSE_PARSING.name in _rg_signals(tmp_path)

    def test_message_content_index_flagged(self, tmp_path):
        (tmp_path / "stream.js").write_text(
            'const text = message.content[0];\n'
        )
        assert SIGNAL_PROVIDER_RESPONSE_PARSING.name in _rg_signals(tmp_path)

    def test_openai_choices_not_flagged(self, tmp_path):
        (tmp_path / "agent.py").write_text(
            'text = response.choices[0].message.content\n'
        )
        assert SIGNAL_PROVIDER_RESPONSE_PARSING.name not in _rg_signals(tmp_path)


# ---------------------------------------------------------------------------
# SIGNAL_TELEMETRY_CALLBACK
# ---------------------------------------------------------------------------

class TestTelemetryCallback:
    def test_langsmith_import_flagged(self, tmp_path):
        p = _write(tmp_path, "import langsmith\n")
        assert SIGNAL_TELEMETRY_CALLBACK.name in _signals(p)

    def test_wandb_import_flagged(self, tmp_path):
        p = _write(tmp_path, "import wandb\n")
        assert SIGNAL_TELEMETRY_CALLBACK.name in _signals(p)

    def test_langsmith_api_key_env_read_flagged(self, tmp_path):
        src = """\
            import os
            key = os.getenv("LANGSMITH_API_KEY")
        """
        p = _write(tmp_path, src)
        assert SIGNAL_TELEMETRY_CALLBACK.name in _signals(p)

    def test_langchain_tracing_js_flagged(self, tmp_path):
        (tmp_path / "config.ts").write_text(
            'const key = process.env.LANGCHAIN_TRACING;\n'
        )
        assert SIGNAL_TELEMETRY_CALLBACK.name in _rg_signals(tmp_path)


# ---------------------------------------------------------------------------
# SIGNAL_CLOUD_IAM
# ---------------------------------------------------------------------------

class TestCloudIam:
    def test_azure_identity_import_flagged(self, tmp_path):
        p = _write(tmp_path, "from azure.identity import DefaultAzureCredential\n")
        assert SIGNAL_CLOUD_IAM.name in _signals(p)

    def test_google_auth_import_flagged(self, tmp_path):
        p = _write(tmp_path, "import google.auth\n")
        assert SIGNAL_CLOUD_IAM.name in _signals(p)

    def test_google_oauth2_import_flagged(self, tmp_path):
        p = _write(tmp_path, "from google.oauth2 import service_account\n")
        assert SIGNAL_CLOUD_IAM.name in _signals(p)


# ---------------------------------------------------------------------------
# SIGNAL_LONG_CONTEXT
# ---------------------------------------------------------------------------

class TestLongContext:
    def test_max_tokens_above_threshold_flagged(self, tmp_path):
        src = """\
            import openai
            client = openai.OpenAI(base_url="http://localhost")
            client.chat.completions.create(
                model="x",
                max_tokens=32000,
                messages=[],
            )
        """
        p = _write(tmp_path, src)
        assert SIGNAL_LONG_CONTEXT.name in _signals(p)

    def test_max_tokens_at_threshold_not_flagged(self, tmp_path):
        src = """\
            import openai
            client = openai.OpenAI(base_url="http://localhost")
            client.chat.completions.create(
                model="x",
                max_tokens=8192,
                messages=[],
            )
        """
        p = _write(tmp_path, src)
        assert SIGNAL_LONG_CONTEXT.name not in _signals(p)

    def test_max_tokens_exactly_threshold_not_flagged(self, tmp_path):
        src = """\
            import openai
            client = openai.OpenAI(base_url="http://localhost")
            client.chat.completions.create(model="x", max_tokens=16000, messages=[])
        """
        p = _write(tmp_path, src)
        assert SIGNAL_LONG_CONTEXT.name not in _signals(p)
