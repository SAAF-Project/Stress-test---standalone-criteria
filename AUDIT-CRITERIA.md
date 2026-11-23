# Draft criteria: standalone static review

These criteria supplement the existing nine SAAF repository standards. They do
not establish a new norm. Metadata and mandate remain proposed (`confirmed: false`),
owner acceptance pending. Preserve checker/source commit, interpreter, run URL and
result when using evidence. Tests are synthetic; model/runtime evidence is separate.

| ID | Criterion | Evidence and boundary |
|---|---|---|
| ST-01 [code] | The five original synthetic projects retain expected hardcoded, configurable, partial, provider-import and Assistants signals. | `test_python_ast.py`, `test_verdict.py`; static observations, not executed agent behaviour. |
| ST-02 [code] | Empty findings, unrecognised clients, syntax/encoding/read errors and invalid TOML cannot become `yes`. Existing high-severity findings remain `no` even when assessment is incomplete. | `test_assessment_boundary.py`; synthetic invalid files and permission mock. |
| ST-03 [code] | Explicit `None`, empty or false endpoint values are not accepted as configurable. | Boundary tests; dynamic endpoint values are not evaluated. |
| ST-04 [code] | Source and supported configuration at the project root are not lost when source-bearing subdirectories exist; supported JS/TS extensions and gitignored source remain visible. | Root/subdirectory and extension tests. Generated/dependency directories remain explicitly excluded. |
| ST-05 [code] | Selected file/directory/root/parent symlinks and non-regular files prevent a clean result. | Boundary tests; stable local copies only, no protection against concurrent filesystem races. |
| ST-06 [code] | TOML dependency arrays contribute real package findings; invalid dependency shapes remain incomplete. | Dependency and malformed-TOML cases. Other config formats are heuristic text matching. |
| ST-07 [code] | JSON preserves `not_assessed` and assessment errors. CLI returns 0 only for a static candidate, 1 for known blockers/partial, 2 for incomplete input. | CLI/reporter tests; schema status extended in 0.2.0, consumers must handle the fourth state. |
| ST-08 [code] | Default CLI does not invoke the model even with endpoint env configured; scanned source is never imported/executed. Explicit advisory call is covered with a fake function only. | Boundary tests and autouse network rejection; provider and UI hosting paths not exercised. |
| ST-09 [code] | Existing additional portability signals retain regression coverage. Unknown results are not displayed as certified runtime success. | `test_new_signals.py` and presentation tests with a UI stub; no browser/clone/upload test. |
| ST-10 [llm] | Model advice is source-grounded, complete and robust to instructions in source. | **Not assessed**: no approved model/version/evaluation set; current pass adds advisory notes only. |
| ST-11 [runtime] | A selected agent completes against a controlled local endpoint with blocked cloud egress. | **Not assessed**: runtime harness, target execution and model provisioning are not implemented here. |
| ST-12 [human] | A qualified owner accepts detector scope, source-processing rules, licence and report use. | **Not assessed**: no accepted owner/CODEOWNERS, licence or dedicated security contact found. |

Run from root: `python -m pytest standalone-check/tests -q -o pythonpath=standalone-check`.
CI runs Python 3.11/3.12 with a hash-locked dependency set and no provider SDK.
A pinned Living Map validator checks metadata separately. A passing PR test run
is not an independent trusted-policy gate for arbitrary candidate code.
