# Prompt: Access Review

**Use case:** User access review (recertification)
**Applicable standards:** ISO 27001 A.9.2, BIO, SOC 2 CC6.2
**Intended AI tool:** Claude (or similar instruction-following LLM)

---

## System Context

You are an AI audit assistant supporting a user access review. The auditor will provide you with an exported user access list. Your task is to identify anomalies that warrant follow-up.

## User Prompt Template

```
I am performing a user access review for [system/application name].

Attached is the exported access list as of [date]. The columns are:
- Username
- Role / Permission level
- Last login date
- Employment status (Active / Inactive / Unknown)
- Department

Please do the following:

1. Identify accounts with no login in the past 90 days that are still active.
2. Flag accounts where employment status is Inactive or Unknown.
3. Identify accounts with privileged roles (admin, superuser, root, or similar) and list them separately.
4. Note any accounts where the department field is missing or inconsistent with the assigned role.
5. Summarize your findings in a table with columns: Username, Issue Type, Risk Level (High/Medium/Low), Recommended Action.

Do not make assumptions about intent. Flag anomalies and let the auditor decide on next steps.
```

## Notes

- Adjust column names to match your actual export.
- For large exports, ask the AI to process in batches or focus on specific issue types first.
- Always validate AI output against the source file before including in audit documentation.
