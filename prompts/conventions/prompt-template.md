# Prompt Template — Reusable Pattern

Use this template as a starting point when creating a new audit use-case prompt.

---

## Metadata Header

Every prompt file should start with:

```
# Prompt: [Use Case Name]

**Use case:** [Short description]
**Applicable standards:** [e.g. ISO 27001 A.x.x, IIA Standard x.x]
**Intended AI tool:** [e.g. Claude, GitHub Copilot, GPT-4]
```

---

## Recommended Structure

### 1. System Context (optional but recommended)

A brief paragraph describing the AI's role and scope for this task. Used as a system prompt or preamble.

```
You are an AI audit assistant supporting [task]. You will be provided with [inputs].
Your task is to [goal]. Do not [restriction].
```

### 2. User Prompt Template

The actual prompt the auditor pastes or sends. Use placeholders in `[square brackets]` for fields the auditor fills in.

```
I am performing [audit procedure] for [entity/period].

[Context about the data or situation.]

Please do the following:
1. [Step 1]
2. [Step 2]
3. [Step 3]

Present your output as [format: table / bullet list / structured Markdown].
```

### 3. Notes

- Any caveats, data privacy considerations, or tips for adapting the prompt.
- Known limitations of using AI for this procedure.
- Suggestions for validating AI output.

---

## Conventions

- Use active, imperative language: "Identify...", "List...", "Flag...", "Summarize..."
- Be explicit about output format to get consistent results.
- Include what the AI should NOT do (e.g. "Do not make assumptions about intent").
- Version-control prompt files alongside the evidence they were used to produce, where possible.
