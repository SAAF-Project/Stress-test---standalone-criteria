# Example Output: Access Review — User Access Analysis

**Use case:** User access review
**Source prompt:** `prompts/audit-use-cases/access-review.md`
**System / application:** [Example — CRM System]
**Review date:** 2026-03-09
**Reviewed by:** AI audit agent (Claude), reviewed and approved by [Lead Auditor Name]
**Data used:** Synthetic / anonymized example data — not real audit evidence

---

## Summary

| Indicator | Count |
|---|---|
| Total accounts reviewed | 142 |
| Accounts flagged for follow-up | 17 |
| Accounts inactive > 90 days | 9 |
| Accounts with Inactive/Unknown employment status | 5 |
| Privileged accounts | 6 |
| Accounts with missing department | 3 |

---

## Flagged Accounts

| Username | Issue Type | Risk Level | Recommended Action |
|---|---|---|---|
| j.bakker | No login in 183 days; status Active | High | Verify with HR; disable if no longer required |
| svc_batch01 | Service account with admin role; no login in 47 days | High | Confirm ownership; restrict to minimum permissions |
| a.de.vries | Employment status: Inactive | High | Disable immediately; confirm with HR |
| m.jansen | Employment status: Unknown | Medium | Verify employment status with HR within 5 business days |
| admin_test | Generic/test account with privileged role | High | Disable and remove; no test accounts in production |
| p.smit | No login in 94 days; status Active | Medium | Contact account owner to confirm ongoing need |
| db_reader | Service account; department field empty | Low | Update record with owning team and business justification |
| l.willemsen | No login in 102 days; status Active | Medium | Verify with manager; disable if no longer required |
| k.hendricks | Role: Superuser; last login 12 days ago | Medium | Confirm business justification for privileged access |

*(Remaining flagged accounts omitted from this example for brevity.)*

---

## Privileged Accounts

| Username | Role | Last Login | Notes |
|---|---|---|---|
| admin_test | Admin | Never | Test account — should not exist in production |
| svc_batch01 | Admin | 47 days ago | Service account — confirm minimum permissions |
| k.hendricks | Superuser | 12 days ago | Active; confirm justification |
| sys_admin | Admin | 3 days ago | Active; confirm justification |
| db_admin | Admin | 31 days ago | Active; confirm justification |
| crm_super | Superuser | 61 days ago | Low activity; review continued need |

---

## Auditor Notes

- The AI agent correctly identified all accounts meeting the defined criteria based on the data provided.
- The auditor independently verified 5 of the 17 flagged accounts against HR records; findings were consistent.
- Two flagged accounts were subsequently confirmed as false positives (shared service accounts with infrequent but legitimate access patterns).
- All findings will be tracked in the findings log (`findings-log-template.csv`).

---

*This is a synthetic example for illustration purposes. All usernames and data are fictional.*
