"""
Signal catalog — all detection constants live here so both the AST scanner
and the ripgrep wrapper import from one place.
"""
from dataclasses import dataclass
from typing import Literal

Severity = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class Signal:
    name: str
    severity: Severity
    fix: str
    description: str = ""


# ---------------------------------------------------------------------------
# Cloud endpoint hostnames searched as substrings
# ---------------------------------------------------------------------------
CLOUD_ENDPOINTS: list[str] = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "aiplatform.googleapis.com",       # Vertex AI
    "bedrock-runtime.",                # AWS Bedrock (regional prefix)
    ".openai.azure.com",               # Azure OpenAI
    "api.cohere.ai",
    "api.mistral.ai",
    "api.together.xyz",
    "api.groq.com",
    "api.perplexity.ai",
    "api.replicate.com",
]

# ---------------------------------------------------------------------------
# Cloud-only API namespaces (detected via dotted attribute chains in AST)
# ---------------------------------------------------------------------------
CLOUD_ONLY_NAMESPACES: list[str] = [
    "beta.assistants",       # OpenAI Assistants API
    "beta.threads",
    "beta.vector_stores",
    "fine_tuning.jobs",
    "images.generate",       # DALL-E — no OSS equivalent
    "images.edit",
    "images.create_variation",
    "audio.speech",          # TTS
    "audio.transcriptions",  # Whisper (cloud endpoint)
    "moderations",           # OpenAI moderation
]

# ---------------------------------------------------------------------------
# SDK imports that indicate a non-portable cloud dependency
# ---------------------------------------------------------------------------
CLOUD_SDK_IMPORTS: dict[str, str] = {
    "anthropic":              "Anthropic SDK — no OpenAI-compatible shim",
    "boto3":                  "AWS SDK (likely Bedrock)",
    "botocore":               "AWS SDK low-level (likely Bedrock)",
    "google.generativeai":    "Google AI (Gemini) SDK",
    "google.cloud.aiplatform":"Vertex AI SDK",
    "vertexai":               "Vertex AI SDK",
    "cohere":                 "Cohere SDK",
    "mistralai":              "Mistral SDK",
    "together":               "Together AI SDK",
    "groq":                   "Groq SDK",
    "replicate":              "Replicate SDK",
}

# litellm is a *good* sign — it's already a portability shim
LITELLM_IMPORTS: set[str] = {"litellm"}

# ---------------------------------------------------------------------------
# Constructor kwargs that prove the endpoint IS configurable
# ---------------------------------------------------------------------------
CONFIGURABLE_KWARGS: set[str] = {
    "base_url", "api_base", "base", "endpoint", "host",
}

# Env var names that indicate env-driven endpoint (informational)
CONFIGURABLE_ENV_VARS: set[str] = {
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE",
    "LITELLM_BASE_URL",
    "OLLAMA_BASE_URL",
    "LLM_BASE_URL",
    "MODEL_BASE_URL",
    "AZURE_OPENAI_ENDPOINT",
}

# ---------------------------------------------------------------------------
# Cloud model name patterns (matched against literal model= kwarg values)
# ---------------------------------------------------------------------------
CLOUD_MODEL_PATTERNS: list[str] = [
    r"gpt-4[o\-]?[\d\.]*",                       # gpt-4, gpt-4o, gpt-4-turbo, gpt-4.1
    r"gpt-3\.5",
    r"o[134](?:-preview|-mini)?$",               # o1, o3, o4, o1-mini, o3-mini
    r"claude-[234]-",                             # Anthropic Claude 2/3/4 numeric family
    r"claude-3-[a-z]",
    r"claude-(?:opus|sonnet|haiku)-\d",          # claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5
    r"claude-(?:opus|sonnet|haiku)(?:@\d)?$",    # claude-opus, claude-sonnet (bare alias)
    r"gemini-(?:pro|ultra|flash)",
    r"gemini-\d",                                 # gemini-2.5-pro, gemini-1.5-flash etc.
    r"text-davinci-\d+",
    r"command(?:-r)?(?:-plus)?",                  # Cohere
    r"mistral-(?:large|medium|small)",
    r"llama-[234]-\d+b-chat",                    # hosted Llama (not self-hosted naming)
]

# ---------------------------------------------------------------------------
# Signal singletons imported by scanners
# ---------------------------------------------------------------------------
SIGNAL_HARDCODED_ENDPOINT = Signal(
    name="hardcoded_cloud_endpoint",
    severity="high",
    fix="Move endpoint to OPENAI_BASE_URL env var; pass base_url=os.getenv('OPENAI_BASE_URL') to client",
)
SIGNAL_HARDCODED_KEY = Signal(
    name="hardcoded_api_key",
    severity="high",
    fix="Remove hardcoded key; read from OPENAI_API_KEY env var instead",
)
SIGNAL_CLOUD_ONLY_API = Signal(
    name="cloud_only_api",
    severity="high",
    fix="This API has no OpenAI-compatible OSS equivalent; refactor or remove",
)
SIGNAL_ENDPOINT_NOT_CONFIGURABLE = Signal(
    name="endpoint_not_configurable",
    severity="medium",
    fix="Pass base_url=os.getenv('OPENAI_BASE_URL') to the client constructor",
)
SIGNAL_HARDCODED_MODEL = Signal(
    name="hardcoded_model_name",
    severity="medium",
    fix="Move model name to MODEL or LLM_MODEL env var",
)
SIGNAL_CLOUD_SDK = Signal(
    name="cloud_sdk_import",
    severity="low",
    fix="Consider using openai SDK with configurable base_url instead",
)
SIGNAL_OPENAI_CLIENT = Signal(
    name="openai_client_detected",
    severity="low",
    fix="",
    description="OpenAI-compatible client instantiation detected (informational)",
)

# ---------------------------------------------------------------------------
# New criteria — provider portability depth checks
# ---------------------------------------------------------------------------

# 1. Provider-specific request features
#    response_format (json_schema), parallel_tool_calls, strict tool schemas,
#    logprobs, seed — many local models ignore or error on these.
PROVIDER_SPECIFIC_KWARGS: set[str] = {
    "response_format",
    "parallel_tool_calls",
    "logprobs",
    "top_logprobs",
    "seed",
}
SIGNAL_PROVIDER_FEATURE = Signal(
    name="provider_specific_request_feature",
    severity="medium",
    fix=(
        "Confirm the local model supports this parameter; "
        "wrap in try/except or guard behind a capability flag"
    ),
)

# 2. Hard API-key format assumption
#    Code that validates the key starts with "sk-" will crash on local dummy keys.
SIGNAL_API_KEY_ASSUMPTION = Signal(
    name="api_key_format_assumption",
    severity="medium",
    fix=(
        "Remove key-format validation; local endpoints accept any non-empty string as a key"
    ),
)

# 3. Cloud-managed embeddings (separate from the chat model)
CLOUD_EMBEDDING_NAMESPACES: list[str] = [
    "embeddings.create",
    "Embedding.create",
    "embed_documents",
    "embed_query",
]
CLOUD_EMBEDDING_IMPORTS: dict[str, str] = {
    "voyageai":                "Voyage AI embeddings (cloud-only)",
    "langchain_voyageai":      "LangChain Voyage embeddings",
    "langchain_openai":        "May use OpenAI embeddings (cloud endpoint)",
    "fastembed":               "FastEmbed (check model source)",
}
SIGNAL_CLOUD_EMBEDDINGS = Signal(
    name="cloud_embeddings_dependency",
    severity="high",
    fix=(
        "Replace with a self-hosted embedding model (e.g. nomic-embed-text via Ollama) "
        "and set EMBEDDING_BASE_URL as an env var"
    ),
)

# 4. Cloud-managed vector store / retrieval
CLOUD_VECTOR_STORE_IMPORTS: dict[str, str] = {
    "pinecone":             "Pinecone (managed cloud vector store; data egress)",
    "langchain_pinecone":   "LangChain Pinecone integration",
    "weaviate":             "Weaviate (check cloud vs local mode)",
    "langchain_weaviate":   "LangChain Weaviate integration",
    "qdrant_client":        "Qdrant (check cloud vs local mode)",
    "zilliz":               "Zilliz Cloud (Milvus-hosted; data egress)",
}
CLOUD_VECTOR_STORE_NAMESPACES: list[str] = [
    "Index(",           # Pinecone Index
    "Pinecone(",
    "WeaviateClient(",
    "QdrantClient(",
]
SIGNAL_CLOUD_VECTOR_STORE = Signal(
    name="cloud_vector_store",
    severity="high",
    fix=(
        "Replace with a local vector store (pgvector, Chroma, Qdrant local mode) "
        "or make the connection string env-driven for in-tenant deployment"
    ),
)

# 5. Multimodal / vision / audio assumed capability
MULTIMODAL_CONTENT_TYPES: set[str] = {"image_url", "image_file", "input_audio"}
SIGNAL_MULTIMODAL_ASSUMPTION = Signal(
    name="multimodal_assumption",
    severity="medium",
    fix=(
        "Ensure the local model supports vision/audio; "
        "add a capability check or make the multimodal path optional"
    ),
)

# 6. Provider-coupled response parsing
#    Reading Anthropic-style .content[0].text or .completion instead of
#    OpenAI-compatible .choices[0].message.content
PROVIDER_RESPONSE_PATTERNS: list[str] = [
    r"\.content\[0\]\.text",    # Anthropic Message.content[0].text
    r"response\.completion",    # old Anthropic completions
    r"delta\.text",             # Anthropic streaming (bare or chained: event.delta.text)
    r"message\.content\[0\]",   # Anthropic message block
]
SIGNAL_PROVIDER_RESPONSE_PARSING = Signal(
    name="provider_coupled_response_parsing",
    severity="medium",
    fix=(
        "Read .choices[0].message.content (OpenAI-compatible schema) "
        "instead of provider-specific attributes"
    ),
)

# 7. Telemetry / callbacks phoning home
TELEMETRY_IMPORTS: dict[str, str] = {
    "langsmith":                            "LangSmith tracing (egress to langsmith.com)",
    "langchain.callbacks.tracers.langsmith": "LangSmith via LangChain callbacks",
    "wandb":                                "Weights & Biases (cloud ML tracking)",
    "arize":                                "Arize Phoenix (cloud ML observability)",
    "opentelemetry.exporter.otlp":          "OTLP exporter (check endpoint target)",
}
TELEMETRY_ENV_VARS: set[str] = {
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_API_KEY",
    "LANGSMITH_ENDPOINT",
    "LANGCHAIN_API_KEY",
    "WANDB_API_KEY",
}
SIGNAL_TELEMETRY_CALLBACK = Signal(
    name="telemetry_callback",
    severity="medium",
    fix=(
        "Gate tracing behind an env var (e.g. TRACING_ENABLED=false by default); "
        "disable LangSmith/analytics callbacks when running air-gapped"
    ),
)

# 8. Cloud IAM in the model path (AWS / Azure credentials)
CLOUD_IAM_IMPORTS: dict[str, str] = {
    "azure.identity":           "Azure AD credentials (required for Azure OpenAI IAM auth)",
    "azure.core.credentials":   "Azure credential objects",
    "google.auth":              "Google Cloud authentication",
    "google.oauth2":            "Google OAuth2 credentials",
}
SIGNAL_CLOUD_IAM = Signal(
    name="cloud_iam_in_model_path",
    severity="high",
    fix=(
        "Replace cloud IAM auth with a simple API key or bearer token "
        "accepted by the local endpoint"
    ),
)

# 9. Long-context assumptions the local model may not meet
LONG_CONTEXT_TOKEN_THRESHOLD = 16_000   # tokens — most local models cap below this
SIGNAL_LONG_CONTEXT = Signal(
    name="long_context_assumption",
    severity="low",
    fix=(
        f"Verify the local model's context limit; "
        "add chunking or summarisation for inputs that may exceed it"
    ),
)
