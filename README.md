# SAAF Standalone-Readiness Checker

**Goal:** A tool that checks whether each agent project in the SAAF ecosystem can run against a self-hosted / local model instead of a cloud LLM API.

Part of the [SAAF Project](https://github.com/SAAF-Project).

---

## 1. What this is

A **provider-portability conformance checker** — a black-box test on each agent as-is. It does not modify agents, only inspects and runs them.

The property under test:

> Does the agent reach its model through a swappable, OpenAI-compatible endpoint, with nothing cloud-only in the request path?

If yes → it can run in-tenant against a local model. If no → it's cloud-locked.

### Two tiers

| Tier | What it does | Evidence type | Ships when |
|------|-------------|---------------|------------|
| **Tier 1 — Static scan** | Parses source code for cloud lock-in signals using Python `ast` and ripgrep. No infrastructure needed. | Design evidence — where the cloud dependency lives (`file:line`) | First |
| **Tier 2 — Runtime proof** | Stands up a local model behind a gateway, repoints the agent, blocks cloud egress, and records whether the agent completes. | Operating-effectiveness evidence — it actually ran with no cloud egress | After Tier 1 is validated |

> **Critical caveat:** Tier 1 catches intent, Tier 2 proves behaviour. An agent can read as portable but still hit a cloud host via a transitive dependency (e.g. a framework's default embedder). Tier 1 alone must never output a "certified" verdict.

This is **not** an rLLM project. rLLM is a reinforcement-learning training framework that modifies agents — we do the opposite.

---

## 2. Prerequisites

### Phase 1 (static scan)

- Python 3.11+ (uses `tomllib`; falls back to regex on older versions)
- [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) — cross-language pattern matching for JS/TS
- No network required when running with `--no-llm`

### Phase 1 (with optional LLM pass)

- An OpenAI-compatible LLM endpoint at `STANDALONE_CHECK_BASE_URL` (e.g. local Ollama at `http://localhost:11434/v1`)
- `openai` Python SDK (`pip install openai`)

### Phase 2 (runtime harness)

- Docker + Docker Compose
- ~2 GB disk for Ollama + `llama3.2:3b` model weights
- No GPU required (CPU inference is sufficient — testing plumbing, not quality)

---

## 3. CLI usage

```bash
# Phase 1 — static scan, no network (deterministic only)
standalone-check scan /path/to/repo --no-llm

# Phase 1 — static scan with LLM fuzzy pass
export STANDALONE_CHECK_BASE_URL=http://localhost:11434/v1
standalone-check scan /path/to/repo

# Phase 1 — scan a single project subdirectory
standalone-check scan /path/to/repo/agent-name --no-llm

# Phase 2 — runtime proof (requires Docker)
standalone-check runtime /path/to/repo

# Phase 2 — runtime with a specific model
standalone-check runtime /path/to/repo --model llama3.2:3b

# View the summary
cat ./reports/summary.md
```

---

## 4. Output schema

Phase 1 emits one JSON object per project to `./reports/<project>.json`:

```json
{
  "project": "<name>",
  "standalone_ready": "yes | partial | no",
  "model_access": {
    "client": "openai|anthropic|litellm|bedrock|azure|google|unknown",
    "endpoint_configurable": true,
    "evidence": [ {"file": "...", "line": 0, "snippet": "..."} ]
  },
  "blockers": [
    {"type": "...", "severity": "high|medium|low", "location": "file:line", "fix": "..."}
  ],
  "cloud_only_features": [ "..." ],
  "notes": "..."
}
```

**Verdict rules:**

| Verdict | Condition |
|---------|-----------|
| **no** | Any HIGH-severity blocker (hardcoded cloud endpoint, cloud-only API) |
| **partial** | Client is swappable in principle but endpoint/model not configurable via env/config, OR a MEDIUM blocker exists |
| **yes** | Model endpoint is env/config-driven and no cloud-only features in the path. Still requires Phase 2 to confirm. |

Phase 1 also emits `./reports/summary.md` — a human-readable table: project | verdict | top blocker.

Phase 2 writes `./reports/<project>.runtime.json` and folds runtime verdicts back into `summary.md`:

| Result | Condition |
|--------|-----------|
| **PASS** | Smoke task completes AND zero cloud-egress attempts logged |
| **FAIL** | Task fails, or any attempt to reach a cloud host was logged (with which host) |

---

## 5. SIGNALS — the Tier 1 detection rubric

### HIGH-severity blockers (force verdict "no")

| Signal | Detection pattern |
|--------|-------------------|
| Hardcoded cloud endpoint | `base_url` / `api_base` literal pointing at `api.openai.com`, `api.anthropic.com`, `*.amazonaws.com`, `generativelanguage.googleapis.com`, `*.openai.azure.com` |
| OpenAI Assistants API | `client.beta.assistants`, `client.beta.threads` — won't run locally, deprecated (shutdown 26 Aug 2026) |
| Bedrock-only path | `boto3` + `bedrock-runtime`, `.converse()` / `.invoke_model()` |
| Azure-only client | `AzureOpenAI()` instantiation |
| Anthropic-native tooling | Anthropic SDK features with no local equivalent (e.g. computer-use, native tool-use formats relied on for control flow) |
| Raw HTTP to cloud API | `requests.post("https://api.openai.com/...")` or similar via `httpx`, `urllib`, `fetch` |

### MEDIUM-severity blockers (verdict "partial")

| Signal | Detection pattern |
|--------|-------------------|
| Endpoint not configurable | Client is swappable (`openai.OpenAI`, `ChatOpenAI`, `litellm`) but no `base_url`/`api_base` read from env or config |
| Hardcoded model name | `gpt-4o`, `gpt-4`, `o1`, `o3`, `claude-3*`, `gemini-*` with no override path |
| Cloud embeddings dependency | `text-embedding-3*`, `voyage*`, `cohere.embed` |
| Managed vector store | Pinecone, Weaviate Cloud — data dependency, not model, but breaks "runs in-tenant" |

### PORTABLE signals (support verdict "yes")

| Signal | Detection pattern |
|--------|-------------------|
| Configurable endpoint | `base_url=os.environ.get("OPENAI_BASE_URL")` / `api_base` from config |
| LiteLLM abstraction | `litellm.completion(...)` as the call layer |
| Dynamic model name | Model resolved from env var or config file, not a literal |
| Provider abstraction | A project-level module that routes all LLM calls through one swappable interface |

---

## 6. Tier 2 runtime harness

### Architecture

```
┌────────────────────────────────────────────────────┐
│                 docker-compose stack                 │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐  │
│  │  ollama   │───▶│ litellm  │◀───│ agent-runner  │  │
│  │ llama3.2  │    │  :4000   │    │              │  │
│  └──────────┘    └──────────┘    └──────────────┘  │
│                                    │  BLOCKED  │     │
│                                    ▼           │     │
│                              ☁ public internet ✗     │
└────────────────────────────────────────────────────┘
```

- **ollama** — serves a small local model (default: `llama3.2:3b`), OpenAI-compatible
- **litellm** — proxy in front of ollama, exposing OpenAI-compatible `:4000`. Image version **must be pinned** (see Security)
- **agent-runner** — runs the agent with `OPENAI_BASE_URL=http://litellm:4000` and `OPENAI_API_KEY=dummy`

### Network rule (this is the point of the test)

`agent-runner` is on an internal-only Docker network with NO route to the public internet. Its only reachable service is litellm. Any cloud call fails by construction. The denial log is what turns "it ran" into operating-effectiveness evidence.

### Model choice

Ollama with `llama3.2:3b` — you're testing plumbing, not output quality, so a tiny CPU-runnable model is fine. Swap to vLLM only if you need GPU realism.

---

## 7. Target repos — what we're scanning

The checker is designed to scan any repo containing agent projects. The primary target is the SAAF ecosystem, but it works against any codebase.

### Primary: [SAAF-Project/threewaysecurity](https://github.com/SAAF-Project/threewaysecurity)

| Agent | Entry point | LLM client | Expected Phase 1 verdict |
|---|---|---|---|
| Audit Document Reviewer | `review_document.py` | `anthropic` SDK | **no** — Anthropic-native |
| OWASP Agent Reviewer | `review_agent.py` + `app.py` | `anthropic` SDK | **no** — Anthropic-native |
| SAAF Compliance Agent | `saaf/core/agent.py` | `anthropic` SDK | **no** — Anthropic-native |
| Project prototype | `project_2026-03-24/app.py` | `anthropic` SDK | **no** — Anthropic-native |

### Example test target: [SAAF-Project/OWASP-top-10-LLM-assessment](https://github.com/SAAF-Project/OWASP-top-10-LLM-assessment)

Useful as a test target to validate the checker against a known-state repo:

| Agent | Entry point | LLM client | Expected Phase 1 verdict |
|---|---|---|---|
| Agent Reviewer | `agent-reviewer/review_agent.py` | `anthropic` SDK | **no** — Anthropic-native |
| LLM-OWASP Audit Pipeline | `llm-owasp/owasp_llm_audit/auditor.py` | `anthropic` SDK | **no** — Anthropic-native |

**Note:** All agents currently use the Anthropic SDK directly with `claude-opus-4-6`. None use the OpenAI-compatible interface today. Every agent will score **"no"** on the first run — which is the correct, expected result. The value is in documenting exactly where the lock-in lives and what the fix path would be.

---

## 8. Scope edges — signals not yet covered

### Multi-provider wrappers

Agents routing through a custom abstraction layer (e.g. `providers/llm.py` wrapping both Anthropic and OpenAI). The AST scanner may not trace through the indirection. This is the primary use case for the optional LLM pass — it reads the provider module in context and assesses portability holistically.

### Transitive dependencies

A framework (e.g. LangChain, CrewAI) may default to a cloud embedder or vector store even if the top-level LLM call is portable. Phase 1 flags the framework import as a **warning** but cannot resolve the runtime behaviour — this is exactly why Phase 2 exists.

### Non-LLM cloud dependencies

Some agents depend on cloud services that aren't LLM endpoints (e.g. Pinecone for vectors, S3 for storage, a managed database). These break "runs fully in-tenant" but are a different class of finding. Flag them under `cloud_only_features`, not as model-access blockers.

---

## 9. Proposed file layout

```
standalone-check/
├── standalone_check/
│   ├── __init__.py
│   ├── cli.py                 # argparse entry point
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── python_ast.py      # ast-based Python analysis
│   │   ├── ripgrep.py         # rg-based cross-language fallback
│   │   ├── signals.py         # SIGNALS rubric as structured data
│   │   └── verdict.py         # verdict logic (yes/partial/no)
│   ├── llm_pass.py            # optional LLM fuzzy-case review
│   ├── reporter.py            # JSON + summary.md output
│   └── runtime/               # Phase 2
│       ├── __init__.py
│       ├── harness.py          # docker-compose generation + orchestration
│       ├── egress_logger.py    # parse blocked connection logs
│       └── templates/
│           ├── docker-compose.yml.j2
│           └── litellm_config.yml.j2
├── reports/                   # generated output (gitignored)
├── tests/
│   ├── fixtures/
│   │   ├── agent_portable/    # fake agent that should score "yes"
│   │   ├── agent_locked/      # fake agent that should score "no"
│   │   └── agent_partial/     # fake agent that should score "partial"
│   ├── test_python_ast.py
│   ├── test_ripgrep.py
│   ├── test_verdict.py
│   └── test_reporter.py
├── pyproject.toml
├── README.md
└── .gitignore
```

---

## 10. Test plan

### Synthetic fixtures

Three fake agent directories under `tests/fixtures/`:

| Fixture | Expected verdict | What it contains |
|---|---|---|
| `agent_portable/` | **yes** | Uses `openai.OpenAI(base_url=os.environ.get("OPENAI_BASE_URL"))`, model from env |
| `agent_locked/` | **no** | Uses `anthropic.Anthropic()` directly, hardcoded `claude-3` model |
| `agent_partial/` | **partial** | Uses `openai.OpenAI()` but `base_url` not configurable, hardcoded `gpt-4o` |

### Real-world validation

Run against SAAF repos (see section 7). All agents should produce HIGH-severity blockers of type "anthropic-native client" with `file:line` evidence pointing at `client = anthropic.Anthropic()` and `model="claude-opus-4-6"`.

### Self-check

The checker's own LLM client must pass its own scan:

```bash
standalone-check scan ./standalone-check --no-llm
# Expected: "yes" — uses openai SDK with configurable STANDALONE_CHECK_BASE_URL
```

---

## 11. Security / known issues

- **Pin the LiteLLM image version.** LiteLLM disclosed a suspected supply-chain incident in March 2026; guidance is to pin to a specific tag rather than `latest` and rotate credentials. Do not deploy the proxy untagged.
- **OpenAI Assistants API is deprecated** and scheduled to shut down 26 August 2026. Any agent using it is a double finding — non-portable now, and dead on the cloud side shortly. Surface it as its own blocker type.
- **Tier 1 cannot certify.** Only Tier 2 with egress blocked proves standalone behaviour. Phase 1 "yes" means "no static blockers found," not "confirmed standalone."
- **The checker must pass its own check.** Its LLM client uses the OpenAI SDK with a configurable `STANDALONE_CHECK_BASE_URL`. No hardcoded API keys anywhere, including examples.

> **Audit framing:** Tier 1 = design evidence (`file:line`); Tier 2 = operating-effectiveness evidence (ran with no cloud egress). That two-layer split makes the output auditable, not just a script result.

---

## 12. Guardrails

- Never modify files inside the agents under test. Treat them as read-only subjects.
- Ask before installing anything outside the project, before any `docker run` that touches host networking, and before pulling model weights (state the size first).
- No hardcoded API keys anywhere, including examples.
- Keep Phase 1 runnable with zero network access (`--no-llm`).

---

## 13. Resources

| Resource | Use | Link |
|---|---|---|
| LiteLLM — OpenAI-compatible endpoints | core gateway concept | https://docs.litellm.ai/docs/providers/openai_compatible |
| LiteLLM — vLLM backend | GPU-realistic Tier 2 | https://docs.litellm.ai/docs/providers/vllm |
| LiteLLM — proxy server setup | the proxy config | https://docs.litellm.ai/docs/proxy_server |
| LiteLLM 2026 self-host guide (+ supply-chain note) | deployment + security | https://effloow.com/articles/litellm-ai-gateway-llm-proxy-guide-2026 |
| Ollama | local model serving (default) | https://ollama.com |
| vLLM | GPU serving (optional) | https://docs.vllm.ai |
| Python `ast` | static analysis of Python | https://docs.python.org/3/library/ast.html |
| ripgrep | cross-language pattern fallback | https://github.com/BurntSushi/ripgrep |

---

## Related repos

- [SAAF-Project/threewaysecurity](https://github.com/SAAF-Project/threewaysecurity) — main SAAF agents (primary scan target)
- [SAAF-Project/OWASP-top-10-LLM-assessment](https://github.com/SAAF-Project/OWASP-top-10-LLM-assessment) — OWASP audit agents (example test target)
- [SAAF-Project/SAAF-Project](https://github.com/SAAF-Project/SAAF-Project) — main SAAF monorepo
