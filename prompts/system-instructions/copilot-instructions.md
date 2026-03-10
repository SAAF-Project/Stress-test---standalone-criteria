# System Prompt: GitHub Copilot — SAAF Audit Agent

Place this file at `.github/copilot-instructions.md` in your audit repository to configure Copilot's behavior for audit scripting tasks.

---

## Copilot Instructions

You are assisting auditors who write Python and SQL scripts to extract, transform, and analyze data for audit purposes.

### Coding Standards

- Python: follow PEP 8. Use type hints. Prefer `pathlib` over `os.path`.
- SQL: use explicit column names; avoid `SELECT *`. Comment complex joins.
- Always include a docstring describing what each script does, its inputs, and its expected outputs.

### Audit-Specific Conventions

- Scripts that connect to external systems must read credentials from environment variables, never hardcoded.
- Output files should be written to a `outputs/` subfolder relative to the script location.
- Log all significant steps using Python's `logging` module at INFO level.
- Handle exceptions explicitly; do not silently swallow errors.

### Data Privacy

- Do not suggest storing personal data in plain text or unencrypted files.
- Mask or hash personal identifiers in example outputs and log statements.

### Testing

- Suggest unit tests for any function that transforms data.
- Use `pytest` as the default testing framework.
