# Dependencies and execution scope

`standalone-check/pyproject.toml` is the package manifest (Python >=3.11). The
static CLI requires Click; AST, TOML, traversal and reporting use the standard
library. The historical `scanner/ripgrep.py` import path remains, but text scans
now use the same deterministic reader everywhere; installing `rg` is unnecessary.

`requirements-ci.in` declares tested Click, pytest and Hatchling build-tool pins.
`requirements-ci.txt` resolves their transitive dependencies with hashes, generated
with uv 0.11.28:

```sh
uv pip compile requirements-ci.in --python-version 3.11 --generate-hashes --no-emit-index-url --output-file requirements-ci.txt
python -m pip install --require-hashes --only-binary=:all: -r requirements-ci.txt
python -m pip install --no-deps --no-build-isolation ./standalone-check
python -m pip check
```

Review changes to lock files and CI together. Hashes constrain distribution bytes;
they are not a vulnerability assessment or ongoing update guarantee. Build tools
are development dependencies, not required by an already installed CLI wheel.

`requirements-manifest.txt` pins PyYAML only for the separate canonical Living Map
validator. It is not a scanner runtime dependency.

Optional extras remain: `llm` installs OpenAI for explicit source-to-model advice;
`web` installs Streamlit for the local UI; `dev` is the historical unpinned convenience
extra. These optional dependency closures are not the tested CI lock and no live
provider, browser deployment, cloning or upload execution is validated here.
No target project dependencies are installed or imported during a static scan.
