# Prompt: Journal Entry Testing

**Use case:** Journal entry analysis for fraud risk indicators
**Applicable standards:** ISA 240, ISAE 3402, SOC 1
**Intended AI tool:** Claude (or similar instruction-following LLM)

---

## System Context

You are an AI audit assistant supporting journal entry testing. The auditor will provide a dataset of general ledger journal entries. Your task is to identify entries that match known fraud risk indicators.

## User Prompt Template

```
I am performing journal entry testing for the period [start date] to [end date].

Attached is a sample of journal entries exported from [ERP system]. The columns are:
- Journal ID
- Posting date
- Entry date
- Posted by (user)
- Debit account
- Credit account
- Amount
- Description / Narration
- Approval status

Please analyze the entries and flag the following risk indicators:

1. Entries posted outside business hours (before 07:00 or after 20:00, or on weekends/holidays).
2. Round-number entries (amounts that are exact multiples of 10,000).
3. Entries posted by users who do not typically post to that account type.
4. Entries with missing or very short descriptions (fewer than 5 characters).
5. Entries that are reversed within 5 business days of posting.
6. Entries posted by system or generic accounts (e.g. "ADMIN", "SYSTEM", "BATCH").

Present your findings in a table with columns: Journal ID, Risk Indicator, Description, Recommended Follow-Up.
Summarize the total number of entries reviewed and the count flagged per indicator.
```

## Notes

- Do not share actual journal entry data with an AI tool unless your organization has approved that data classification for the tool in use.
- Consider anonymizing amounts or using synthetic data for prompt development and testing.
- Results are indicative only; auditor judgment is required to determine which flagged entries require further investigation.
