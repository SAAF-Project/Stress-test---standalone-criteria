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
