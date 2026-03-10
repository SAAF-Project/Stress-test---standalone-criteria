# ISO 27001:2022 — AI Audit Agent Control Mapping

This document maps relevant ISO 27001:2022 Annex A controls to audit agent activities and identifies how each control applies to the SAAF framework.

| Control | Title | Relevance to AI Audit Agents | SAAF Mitigation |
|---|---|---|---|
| A.5.1 | Policies for information security | AI usage must be governed by an approved policy | See `policies/ai-usage-policy-template.md` |
| A.5.23 | Information security for use of cloud services | LLM APIs are cloud services; data classification applies | Only share data approved for the tool's data class |
| A.8.2 | Privileged access rights | Agents with system access must have minimal privileges | Restrict tool permissions; see `guardrails/allowed-commands.md` |
| A.8.4 | Access to source code | Agent repositories must have controlled access | Use branch protection and access reviews on this repo |
| A.8.15 | Logging | Agent actions must be logged | Ensure MCP servers and scripts log all invocations |
| A.8.16 | Monitoring activities | Agent behavior should be monitored for anomalies | Review agent logs periodically; flag unexpected tool calls |
| A.8.28 | Secure coding | Scripts in `tools/` must follow secure coding standards | See `prompts/system-instructions/copilot-instructions.md` |

## Notes

- This mapping is indicative, not exhaustive. Adapt to your organization's ISO 27001 Statement of Applicability.
- Update this table as new agent capabilities are introduced into the SAAF framework.
- Cross-reference with your organization's existing risk register where applicable.
