# Regulatory

Control mappings, guardrails, and AI usage policies to keep audit agents compliant and within sanctioned boundaries.

## Subfolders

| Folder | Contents |
|---|---|
| [`frameworks/`](frameworks/) | Per-framework control mappings (ISO 27001, NIS2, BIO, etc.) |
| [`guardrails/`](guardrails/) | Whitelisted commands, restricted file access, AI permission boundaries |
| [`policies/`](policies/) | Organizational AI usage policy templates |

## Contributing

- Name framework mapping files as `[framework-id]-control-mapping.md` (e.g. `iso27001-control-mapping.md`).
- Guardrail files should be self-contained and reference the specific AI tool or environment they apply to.
- Policy templates use `[Placeholder]` notation for organization-specific fields.
