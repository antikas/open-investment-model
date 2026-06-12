# E-18 — Limit Breach

An event: a measured risk crossed a Risk Limit (E-16). The record of the breach, its severity, and its resolution.

## Purpose

A limit framework is only as good as what happens when a limit is crossed. The Limit Breach is the record of that event — when a risk measurement exceeded a limit, by how much, how serious it was, and how it was resolved. It exists as an entity, not as a transient alert, for three reasons: a breach must be **escalated** through a governance process that needs a record to act on; a breach is **audited** — a regulator or an internal-audit review will ask "what breaches occurred, and what was done"; and breach history is a **risk signal** in itself — a limit breached repeatedly says something the single breach does not.

A Limit Breach is an immutable event, in the same family as a Transaction (E-05) — something happened, on a date, and the record of it is a fact.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `breach_id` | varchar | Primary key. |
| `limit_id` | varchar (FK → E-16) | The risk limit that was breached. |
| `measurement_id` | varchar (FK → E-19) | The risk measurement that crossed the limit. |
| `breach_date` | date | The date the breach was identified. |
| `observed_value` | decimal | The measured value that crossed the limit. |
| `threshold_value` | decimal | The limit threshold in force at the time (from the E-16 version effective on `breach_date`). |
| `breach_severity` | varchar | `warning` (the warning level was crossed but not the hard threshold) / `breach` (the hard threshold was crossed) / `severe` (a breach beyond a defined tolerance). |
| `status` | varchar | `open` / `escalated` / `resolved` / `accepted` (a breach formally accepted by governance rather than remediated). |
| `resolved_date` | date | When the breach was resolved or accepted; null while open. |
| `resolution_note` | varchar | How the breach was resolved — the action taken, or the rationale for acceptance. |

## Notes

- The breach record is **immutable as an event** — the breach happened. Its `status` and `resolved_date` are updated as the breach moves through escalation to resolution, but the breach itself is never deleted, even once resolved.
- `threshold_value` is captured *on the breach* because the limit (E-16) is versioned — the breach must record the threshold that was actually in force when it occurred, not whatever the limit says later.
- A `warning`-severity breach is the early-warning signal: the E-16 warning level was crossed ahead of the hard threshold, giving the risk function time to act before a hard breach.

## Out of scope

- The limit that was breached — that is E-16 Risk Limit; E-18 references it through `limit_id` and captures the in-force `threshold_value` on the breach, but the limit definition is E-16.
- The risk measurement that crossed the limit — that is E-19 Risk Measurement, referenced through `measurement_id`; E-18 is the breach event, not the measurement.
- The escalation workflow itself — the path through `open`, `escalated`, `resolved` and who acts at each step — named as an open extension; the entity carries the `status` field, not the process.

## Owned and consumed by

- **Owned by:** SD-07.7 Investment Risk Reporting & Limits Governance.
- **Consumed by:** SD-07.1 / SD-07.2 / SD-07.3 / SD-07.4 (the risk-measurement domains, which detect breaches), SD-16.1 Corporate & Fund Governance (breach reporting to governance), SD-14.8 Internal Audit.

## Open extensions

- The escalation workflow — the path from `open` through `escalated` to `resolved`, and who acts at each step.
- Recurring-breach detection — the pattern across breaches of the same limit over time.
