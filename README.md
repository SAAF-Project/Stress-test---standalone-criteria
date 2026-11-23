# SAAF Standalone-Readiness Checker

A static Python/JavaScript/TypeScript portability scanner in
[`standalone-check/`](standalone-check). It reads source and selected configuration
files for model-provider dependencies and writes JSON plus Markdown reports.
It does **not** run the scanned agent, provision a model or prove local execution.

The Docker/Ollama runtime harness described in earlier design notes is **planned,
not implemented**. There are no `scan` or `runtime` CLI subcommands. The root
`app/`, `tools/`, `prompts/`, `regulatory/` and `outputs/` directories are inherited
scaffolding; they are not evidence that this scanner implements those workflows.
Existing history and contributors remain intact.

## Install and run offline

Python 3.11 or 3.12. Run from repository root in a separate virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes --only-binary=:all: -r requirements-ci.txt
python -m pip install --no-deps --no-build-isolation ./standalone-check
python -m pip check
standalone-check ./standalone-check/tests/fixtures/proj_env_driven --no-llm -o ./reports
```

This synthetic fixture should produce `yes`, exit 0: a **static candidate**, not
runtime certification. `proj_hardcoded` produces `no`, exit 1. Missing evidence
produces exit 2. A report's JSON status and `assessment_errors` must be checked;
file existence or process completion alone is not a pass.

```sh
# Scan a selected, stable local checkout; no target code is executed.
standalone-check /absolute/path/to/project -o /absolute/path/to/reports
# Select one immediate project directory in a monorepo.
standalone-check /absolute/path/to/monorepo -p example-agent --no-llm
# Run synthetic tests (network calls are rejected by the test fixture).
python -m pytest standalone-check/tests -q -o pythonpath=standalone-check
```

Model use is disabled by default, even when `STANDALONE_CHECK_BASE_URL` is set.
`--no-llm` remains accepted. Only explicit `--llm` opts into the existing advisory
pass. Its separate `llm` extra installs `openai`; an operator must approve endpoint,
source disclosure, terms and cost before use. It sends up to eight Python snippets
of 500 characters, which may contain sensitive source. Returned notes **do not
modify the deterministic verdict**; proposed extra model blockers are not applied.
No provider evaluation was performed in this batch.

The existing optional Streamlit interface (`web` extra, `standalone-check-web`)
uses the same verdict and scanners. It includes URL-cloning and ZIP-upload flows
outside ordinary offline CI; host it only in a trusted local environment. This
batch tests presentation helpers with a UI stub, not browser, clone or upload safety.

## Evidence and exit contract (0.2.0)

| `standalone_ready` | Meaning within the selected static scope |
|---|---|
| `yes` | Recognised OpenAI-compatible client constructor, endpoint argument present, no high/medium signal or assessment error. Runtime is untested. |
| `partial` | Recognised client with a medium signal or missing/nonconfigurable endpoint. |
| `no` | At least one high-severity signal, including when other files could not be assessed. |
| `not_assessed` | No recognised model client or incomplete/unreadable/invalid input, with no high-severity signal. |

CLI exit **0** requires all selected reports to be `yes` with no assessment errors;
**1** means known `no`/`partial`; **2** means any incomplete assessment, invalid
selection or missing input. A known high-severity blocker remains `no` even when
the process exits 2 for another error. Consumers previously accepting only three
statuses must add `not_assessed` and read the new `assessment_errors` array.

Reports retain `project`, `model_access`, `blockers`, `cloud_only_features`, and
`notes`. File paths and source snippets can be sensitive; keep reports local and
outside public Git. Select a fresh output directory for each revision: reports are
not a durable evidence store, and an earlier file is not proof of the current run.
Record the source commit, checker commit, interpreter and CI run alongside them.

## Scan boundary and limitations

Python uses AST plus text patterns; JS/TS (`js`, `jsx`, `ts`, `tsx`, `mjs`, `cjs`)
uses text patterns. The text reader is deterministic and does not depend on
ripgrep or `.gitignore`. Selected `requirements*.txt`, `setup.cfg`, `pyproject.toml`,
`.env*`, YAML and YML files contribute heuristic dependency/endpoint signals.
TOML is parsed; other formats are text matching, not full schema validation.

Root-level source or a supported root dependency/configuration marker makes a
checkout one project including nested packages. This also covers `src/` layouts
without omitting root TOML or environment files. Otherwise immediate source-bearing
directories are separate projects. Select an explicit subdirectory path when a
monorepo's shared configuration should not apply to that project's scan. Root YAML
(including `agent.yaml`) also selects one root project; `-p` then accepts that root
name, not its children. Pass the child's explicit path to inspect it separately.
Generated/dependency directories `.git`, `.github`, `.venv`, `venv`, `__pycache__`,
`.tox`, `site-packages`, `node_modules`, `reports`, `dist`, and `build` are excluded.
Use a real path without symlink components; symlinks/special files in the selected
walk and read/UTF-8/Python-parse errors prevent a clean result. Inspect a stable copy;
these checks are not a sandbox for a concurrently changing malicious filesystem.

Heuristics do not resolve aliases, dynamic values, wrappers, call graphs, transitive
dependencies or actual network egress. An endpoint expression is not proof it has
a nonempty local value at runtime. Comments, fixtures and strings can cause false
positives. JS-only/custom-client projects cannot obtain a Python-client `yes`.
A vendor import is evidence to review, not proof that a network call occurred.
No model quality, authentication, data residency, cost controls or legal compliance
is certified. The future runtime harness needs a separate approved design and tests.

## Repository standards

- [`agent.yaml`](agent.yaml): proposed Living Map metadata and descriptive mandate,
  explicitly `confirmed: false`; not executable access control or owner acceptance.
- [`AUDIT-CRITERIA.md`](AUDIT-CRITERIA.md): stable draft criteria tied to tests and gaps.
- [`DEPENDENCIES.md`](DEPENDENCIES.md): runtime, development and optional dependency scope.
- [Offline CI](.github/workflows/offline-ci.yml): pinned actions, read-only permissions,
  Python 3.11/3.12 tests and separately pinned canonical manifest validation.

No repository licence was found. Do not infer MIT or commercial reuse permission.
Accepted ownership/CODEOWNERS, a private security contact and licensing remain open
human decisions; this PR does not fill those standards with unapproved claims.
