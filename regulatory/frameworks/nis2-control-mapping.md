# NIS2 Directive — AI Audit Agent Control Mapping

This document maps relevant NIS2 Directive requirements (Articles 20–21) to audit agent activities.

NIS2 applies to essential and important entities in the EU. If your organization is in scope, the following requirements are relevant when deploying AI audit agents.

| NIS2 Requirement | Article | Relevance to AI Audit Agents | SAAF Mitigation |
|---|---|---|---|
| Risk management policies | Art. 21(1) | AI agents introduce new risk vectors (data leakage, hallucination, unauthorized access) | Document risks in your organization's risk register; see `policies/ai-usage-policy-template.md` |
| Incident handling | Art. 21(2)(b) | Malfunction or misuse of an audit agent may constitute an incident | Define incident criteria for AI agents; include in incident response procedures |
| Supply chain security | Art. 21(2)(d) | LLM providers and MCP server dependencies are third-party suppliers | Conduct supplier assessments for AI tool providers |
| Security in network and information systems | Art. 21(2)(e) | Scripts and APIs must not introduce new attack surfaces | Follow secure coding standards; see `guardrails/allowed-commands.md` |
| Access control and asset management | Art. 21(2)(i) | Agents should not have broader access than necessary | Apply least-privilege principle to all agent tool permissions |
| Use of cryptography | Art. 21(2)(j) | Credentials used by agents must be stored securely | Use environment variables or a secrets manager; never hardcode credentials |
| Training | Art. 21(2)(g) | Auditors using AI agents should be trained on risks and limitations | Run awareness sessions alongside SAAF hackathons |

## Notes

- NIS2 was transposed into Dutch law via the Cyberbeveiligingswet (Cbw), expected to enter into force in 2025.
- Consult your legal and compliance team to determine your organization's exact NIS2 scope and obligations.
- This mapping is intended as a starting point, not a compliance checklist.
