# Tools

Scripts, APIs, and integrations that power audit agent capabilities.

## Subfolders

| Folder | Contents |
|---|---|
| [`scripts/`](scripts/) | Python and shell scripts for data extraction, transformation, and analysis |
| [`apis/`](apis/) | API connection templates and connector utilities |
| [`integrations/`](integrations/) | MCP servers, GitHub CLI hooks, version control integrations |
| [`automation/`](automation/) | File organization and workflow automation utilities |

## Contributing

- Include a docstring or header comment in every script explaining its purpose, inputs, and outputs.
- Read credentials from environment variables — never hardcode secrets.
- Test scripts against synthetic or anonymized data before sharing.
- Add a `requirements.txt` or inline comment listing any non-standard dependencies.
