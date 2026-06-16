# SAAF Standalone-Readiness Checker — Build Brief

**For:** the teammate building this in Claude Code
**Goal:** a tool that checks whether each agent project in the SAAF GitHub repo can run against a self-hosted / local model instead of a cloud LLM API.

---

## 1. What we're actually building (read this first)

This is **not** an rLLM project. rLLM is a reinforcement-learning training framework — it modifies agents. We are doing the opposite: a **black-box conformance test** on each agent as-is.

The property under test is **provider-portability**:

> Does the agent reach its model through a swappable, OpenAI-compatible endpoint, with nothing cloud-only in the request path?

If yes → it can run in-tenant against a local model. If no → it's cloud-locked. That's the whole question.

**Two tiers, build in this order:**

- **Tier 1 — static scan.** No infra. Greps/parses each project's source for cloud lock-in signals. Ships first; it's the defensible audit artifact on its own.
- **Tier 2 — runtime proof.** Stands up a local model behind a gateway, repoints the agent at it, runs the agent with cloud egress blocked, and records whether it completes. This is the actual evidence; Tier 1 only catches intent.

> **Critical caveat to bake in:** Tier 1 catches intent, Tier 2 proves behaviour. An agent can read as portable but still hit a cloud host via a transitive dependency (e.g. a framework's default embedder). Tier 1 alone must never output a "certified" verdict.

---

## 2. Claude Code prompt (paste this)

```
You are building a CLI tool called `standalone-check` that audits agent projects in a
monorepo to determine whether each can run against a self-hosted, OpenAI-compatible
model instead of a cloud LLM API. This is a portability conformance check — do NOT
modify the agents under test, only inspect and run them.

Build in two phases. Get Phase 1 fully working and tested before starting Phase 2.

== PHASE 1: STATIC SCAN (priority — must work standalone) ==

Input: a path to a repo containing multiple agent project subdirectories.
For each project, statically analyse the source (Python first; add a ripgrep-based
fallback for JS/TS) and detect the lock-in signals listed in SIGNALS below.

Use Python's `ast` module for Python files (not regex) to find client instantiations
and their keyword args. Use ripgrep for cross-language string/pattern matches.

Output one JSON object per project to ./reports/<project>.json with this schema:
{
  "project": "<name>",
  "standalone_ready": "yes" | "partial" | "no",
  "model_access": {
    "client": "openai|anthropic|litellm|bedrock|azure|google|unknown",
    "endpoint_configurable": true|false,
    "evidence": [ {"file": "...", "line": 0, "snippet": "..."} ]
  },
  "blockers": [
    {"type": "...", "severity": "high|medium|low", "location": "file:line", "fix": "..."}
  ],
  "cloud_only_features": [ "..." ],
  "notes": "..."
}

Verdict rules:
- "no"      if any HIGH-severity blocker (hardcoded cloud endpoint, cloud-only API).
- "partial" if the client is swappable in principle but the endpoint/model is not
            configurable via env/config, OR a medium blocker exists.
- "yes"     if the model endpoint is env/config-driven and no cloud-only features
            are in the path. (Still requires Phase 2 to confirm.)

Also emit ./reports/summary.md — a human-readable table: project | verdict | top blocker.

After the deterministic pass, run ONE optional LLM pass per project to catch fuzzy
cases the AST/grep missed (e.g. a custom provider wrapper). The checker's own LLM
client MUST itself be OpenAI-compatible with a configurable base_url read from
STANDALONE_CHECK_BASE_URL — i.e. the checker must pass its own check. Make this pass
skippable with --no-llm so Phase 1 runs with zero network.

== PHASE 2: RUNTIME HARNESS ==

For each project that scores "yes" or "partial" in Phase 1, prove it at runtime.

Produce a docker-compose stack with three services:
1. `ollama`  — serves a small local model (default: llama3.2:3b), OpenAI-compatible.
2. `litellm` — LiteLLM proxy in front of ollama, exposing OpenAI-compatible :4000.
                PIN the image to a specific version tag (see SECURITY). Config via YAML.
3. `agent-runner` — runs the target agent's own entrypoint/smoke task with
                OPENAI_BASE_URL=http://litellm:4000 and OPENAI_API_KEY=dummy.

Network rule (this is the point of the test): `agent-runner` is on an internal-only
docker network with NO route to the public internet EXCEPT the litellm service.
Any attempt by the agent to reach a cloud LLM host therefore fails by construction.
Log every blocked/attempted egress connection.

Result per project:
- PASS  = smoke task completes AND zero cloud-egress attempts logged.
- FAIL  = task fails, or any attempt to reach a cloud host was logged (with which host).

Write results to ./reports/<project>.runtime.json and fold the verdict back into summary.md.

== GUARDRAILS ==
- Never modify files inside the agents under test. Treat them as read-only subjects.
- Ask before installing anything outside the project, before any `docker run` that
  touches host networking, and before pulling model weights (state the size first).
- No hardcoded API keys anywhere, including examples.
- Keep Phase 1 runnable with zero network access (--no-llm).

Start by proposing the file/module layout and the SIGNALS detection list as code,
then implement Phase 1.
```

---

## 3. SIGNALS — the Tier 1 detection rubric

Hand this list to Claude Code as the seed for the static scan. Refine against the actual SAAF repo.

### HIGH-severity blockers (force verdict "no")

- **Hardcoded cloud endpoint:** `base_url` / `api_base` literal pointing at `api.openai.com`, `api.anthropic.com`, `*.amazonaws.com`, `generativelanguage.googleapis.com`, `*.openai.azure.com`.
- **OpenAI Assistants API:** `client.beta.assistants`, `client.beta.threads` — won't run locally and is being shut down (see Security).
- **Bedrock-only path:** `boto3` + `bedrock-runtime`, `.converse(` / `.invoke_model(`.
- **`AzureOpenAI(` instantiation.**
- **Anthropic-native tooling** that has no local equivalent (e.g. computer-use / native tool-use formats relied on for control flow).

### MEDIUM-severity blockers (verdict "partial")

- Client is swappable (`openai.OpenAI`, `ChatOpenAI`, `litellm`) but endpoint not configurable — no `base_url`/`api_base` read from env or config.
- Model name hardcoded with no override path: `gpt-4o`, `gpt-4`, `o1`, `o3`, `claude-3*`, `gemini-*`.
- Cloud embeddings as a hard dependency: `text-embedding-3*`, `voyage*`, `cohere.embed`.
- Managed vector store as hard dependency (Pinecone, Weaviate Cloud) — flag separately; it's a data dependency, not a model one, but it breaks "runs in-tenant."

### PORTABLE signals (support verdict "yes")

- `base_url=os.environ.get("OPENAI_BASE_URL")` / `api_base` from config.
- LiteLLM as the abstraction layer (`litellm.completion(...)`).
- Model name resolved from env/config, not a literal.
- A provider-abstraction module the project routes all calls through.

---

## 4. Tier 2 harness notes

- **Model choice:** Ollama (`llama3.2:3b`) is the fast default — you're testing plumbing, not output quality, so a tiny model is fine and CPU-runnable. Swap to vLLM only if you need GPU realism.
- **Egress block = the evidence.** Don't try to allow-list cloud CIDRs; invert it. Give `agent-runner` an internal-only network whose only reachable service is the proxy. Then any cloud call fails by construction and you log the attempt. That denial log is what turns "it ran" into operating-effectiveness evidence.
- **LiteLLM treats local models identically to cloud** — Ollama and vLLM are native backends, so the agent's existing OpenAI SDK integration works unchanged once `base_url` points at the proxy.

---

## 5. Resources

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

## 6. Security / known issues (call these out in the build)

- **Pin the LiteLLM image version.** LiteLLM disclosed a suspected supply-chain incident in March 2026; guidance is to pin to a specific tag rather than `latest` and rotate credentials. Do not deploy the proxy untagged.
- **OpenAI Assistants API is deprecated** and scheduled to shut down 26 August 2026. Any agent using it is a double finding — non-portable now, and dead on the cloud side shortly. Surface it as its own blocker type.
- **Tier 1 cannot certify.** Only Tier 2 with egress blocked proves standalone behaviour. Keep the verdicts honest: Phase 1 "yes" means "no static blockers found," not "confirmed standalone."

> **Framing note for the audit angle:** Tier 1 = design evidence (where the cloud dependency lives, `file:line`); Tier 2 = operating-effectiveness evidence (it actually ran with no cloud egress). That two-layer split is what makes the output auditable rather than just a script result.

---

## 7. Prerequisites

**Phase 1 (static scan):**

- Python 3.11+ (uses `tomllib`; falls back to regex on older versions)
- [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) — for cross-language pattern matching on JS/TS files
- No network required when running with `--no-llm`

**Phase 1 (with LLM pass):**

- An OpenAI-compatible LLM endpoint accessible at `STANDALONE_CHECK_BASE_URL` (e.g. a local Ollama instance at `http://localhost:11434/v1`)
- `openai` Python SDK (`pip install openai`)

**Phase 2 (runtime harness):**

- Docker + Docker Compose
- ~2 GB disk for Ollama + `llama3.2:3b` model weights
- No GPU required (CPU inference is sufficient — we're testing plumbing, not quality)

---

## 8. Target repo — what we're scanning

The SAAF repo: [github.com/SAAF-Project/threewaysecurity](https://github.com/SAAF-Project/threewaysecurity)

It contains these agent projects:

| Agent | Entry point | LLM client | What it does |
|---|---|---|---|
| Audit Document Reviewer | `review_document.py` | `anthropic` SDK | Reviews internal audit docs, returns structured findings |
| OWASP Agent Reviewer | `review_agent.py` + `app.py` | `anthropic` SDK | Reviews agent source code against OWASP Top 10 for LLMs |
| SAAF Compliance Agent | `saaf/core/agent.py` | `anthropic` SDK | Generates structured compliance reports via Pydantic models |
| Project prototype | `project_2026-03-24/app.py` | `anthropic` SDK (via Flask) | Earlier prototype of the OWASP web portal |

**Note:** All agents currently use the Anthropic SDK directly with `claude-opus-4-6`. None use the OpenAI-compatible interface today. This means every agent will likely score **"no"** in Phase 1 on the first run — which is the correct, expected result. The value is in documenting exactly where the lock-in lives and what the fix path would be.

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

## 10. CLI usage examples

```bash
# Phase 1 — static scan, no network (deterministic only)
standalone-check scan /path/to/SAAF --no-llm

# Phase 1 — static scan with LLM fuzzy pass (needs STANDALONE_CHECK_BASE_URL)
export STANDALONE_CHECK_BASE_URL=http://localhost:11434/v1
standalone-check scan /path/to/SAAF

# Phase 1 — scan a single project subdirectory
standalone-check scan /path/to/SAAF/saaf --no-llm

# Phase 2 — runtime proof (requires Docker)
standalone-check runtime /path/to/SAAF

# Phase 2 — runtime with a specific model
standalone-check runtime /path/to/SAAF --model llama3.2:3b

# View the summary
cat ./reports/summary.md
```

---

## 11. Test plan — validating the scanner

### Test fixtures (synthetic agents)

Build three fake agent directories under `tests/fixtures/`:

| Fixture | Expected verdict | What it contains |
|---|---|---|
| `agent_portable/` | **yes** | Uses `openai.OpenAI(base_url=os.environ.get("OPENAI_BASE_URL"))`, model from env |
| `agent_locked/` | **no** | Uses `anthropic.Anthropic()` directly, hardcoded `claude-3` model |
| `agent_partial/` | **partial** | Uses `openai.OpenAI()` but `base_url` not configurable, hardcoded `gpt-4o` |

### First real-world validation

Run against the SAAF repo itself:

```bash
standalone-check scan C:\Users\natha\SAAF --no-llm
```

**Expected results for SAAF agents:**

- `review_document.py` → **no** (Anthropic SDK, no OpenAI-compatible path)
- `review_agent.py` → **no** (same — `anthropic.Anthropic()` with `claude-opus-4-6`)
- `saaf/` → **no** (same pattern in `core/agent.py`)
- `project_2026-03-24/` → **no** (same)

All four should produce HIGH-severity blockers of type "anthropic-native client" with `file:line` evidence pointing at the `client = anthropic.Anthropic()` instantiation and the `model="claude-opus-4-6"` parameter.

### Self-check

The checker's own LLM client must pass its own scan:

```bash
standalone-check scan ./standalone-check --no-llm
# Expected: "yes" — uses openai SDK with configurable STANDALONE_CHECK_BASE_URL
```

---

## 12. Scope edges — signals not yet covered

The detection rubric in section 3 covers SDK-based access patterns. These additional patterns should be flagged but are handled differently:

### Raw HTTP calls to cloud LLM APIs

Agents that bypass SDKs and call LLM APIs via `requests.post("https://api.openai.com/v1/chat/completions", ...)` or similar. Detection: grep for known cloud API URL patterns inside `requests`, `httpx`, `urllib`, or `fetch` calls. Treat as HIGH severity — same as a hardcoded endpoint.

### Multi-provider wrappers

Agents that route through a custom abstraction layer (e.g. `providers/llm.py` that wraps both Anthropic and OpenAI). The AST scanner may not trace through the indirection. This is the primary use case for the optional LLM pass — it reads the provider module in context and assesses portability holistically.

### Transitive dependencies

A framework (e.g. LangChain, CrewAI) may default to a cloud embedder or a cloud vector store even if the top-level LLM call is portable. Phase 1 can flag the framework import as a **warning** but cannot resolve the runtime behaviour — this is exactly why Phase 2 exists.

### Non-LLM cloud dependencies

Some agents depend on cloud services that aren't LLM endpoints (e.g. Pinecone for vectors, S3 for storage, a managed database). These break "runs fully in-tenant" but are a different class of finding. Flag them separately under `cloud_only_features` in the report, not as model-access blockers.
