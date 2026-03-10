# MCP Server Example

[Model Context Protocol (MCP)](https://modelcontextprotocol.io) lets you expose custom tools and data sources to AI assistants like Claude. This document walks through a minimal example for audit tooling.

## What MCP Enables

- Give Claude access to internal data without copy-pasting (e.g. query a database, read a file share).
- Expose controlled shell commands the agent is permitted to run.
- Restrict access to only approved tools and data sources.

## Minimal Setup (Python, stdio transport)

### 1. Install the SDK

```bash
pip install mcp
```

### 2. Create the server file

```python
# audit_mcp_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("SAAF Audit Tools")


@mcp.tool()
def list_csv_files(folder: str) -> list[str]:
    """List CSV files in the specified folder (restricted to /audit-data)."""
    import os
    base = "/audit-data"
    target = os.path.realpath(os.path.join(base, folder))
    if not target.startswith(base):
        raise ValueError("Access outside /audit-data is not permitted.")
    return [f for f in os.listdir(target) if f.endswith(".csv")]


@mcp.tool()
def read_csv_summary(file_path: str) -> dict:
    """Return row count and column names for a CSV file inside /audit-data."""
    import csv, os
    base = "/audit-data"
    full_path = os.path.realpath(os.path.join(base, file_path))
    if not full_path.startswith(base):
        raise ValueError("Access outside /audit-data is not permitted.")
    with open(full_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return {"row_count": len(rows), "columns": reader.fieldnames}


if __name__ == "__main__":
    mcp.run()
```

### 3. Register the server in Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "saaf-audit-tools": {
      "command": "python",
      "args": ["/path/to/audit_mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop. The tools `list_csv_files` and `read_csv_summary` will now be available.

## Security Considerations

- Always validate and sandbox file paths to prevent directory traversal.
- Only expose the minimum set of tools required for the task.
- Log all tool invocations for audit trail purposes.
- Review the MCP server code with your security team before deploying in production.

## Further Reading

- [MCP Documentation](https://modelcontextprotocol.io/docs)
- [FastMCP Examples](https://github.com/jlowin/fastmcp)
