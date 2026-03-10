# Allowed Commands — AI Agent Guardrails

This document defines which shell commands an AI audit agent is permitted to execute. Use this list when configuring MCP servers, Claude Code hooks, or other agent execution environments.

## Principles

- **Allowlist by default:** deny everything not explicitly listed.
- **Read before write:** prefer read-only operations; require explicit approval for writes.
- **No network egress from scripts:** scripts should not initiate outbound connections unless through an approved API connector.
- **No privilege escalation:** `sudo`, `su`, and similar commands are never permitted.

## Permitted Commands

### File system (read-only)
```
ls
cat
head
tail
wc
find
stat
```

### File system (write — with approval)
```
cp          # copy files; never overwrite without confirmation
mkdir       # create directories
mv          # move or rename; never overwrite without confirmation
```

### Data processing
```
python      # run approved scripts from the tools/scripts/ folder only
python3
csv         # via Python only
jq          # parse JSON
```

### Version control (read-only)
```
git status
git log
git diff
git show
```

## Explicitly Prohibited Commands

```
rm          # deletion
sudo        # privilege escalation
curl        # arbitrary network requests
wget        # arbitrary network requests
ssh         # remote shell access
scp         # remote file transfer
chmod       # permission changes
chown       # ownership changes
cron        # scheduled task creation
pip install # package installation at runtime
```

## Notes

- Configure these restrictions in your MCP server's tool definitions (see `integrations/mcp-server-example.md`).
- If a task genuinely requires a prohibited command, escalate to a human operator.
- Review and update this list after each SAAF hackathon session.
