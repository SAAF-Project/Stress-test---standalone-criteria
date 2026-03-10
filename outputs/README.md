# Outputs

Standardized report formats, schemas, and examples for AI audit agent outputs.

## Subfolders

| Folder | Contents |
|---|---|
| [`templates/`](templates/) | Report and log templates in Markdown and CSV |
| [`schemas/`](schemas/) | JSON/YAML schemas for structured output validation |
| [`examples/`](examples/) | Completed example outputs per use case |

## Contributing

- Templates use `[Placeholder]` notation for fields to be filled in.
- Schemas follow JSON Schema Draft 7 or later.
- Example outputs should be based on synthetic or fully anonymized data — never real audit evidence.
- Name files to match the use case they belong to (e.g. `access-review-output.md` corresponds to `prompts/audit-use-cases/access-review.md`).
