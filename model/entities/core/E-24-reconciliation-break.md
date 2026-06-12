# E-24 — Reconciliation Break

An event: two records of the same thing disagree. The owned, aged record of a reconciliation difference — the two sides, the difference, its cause, and its resolution lifecycle.

## Purpose

A reconciliation compares two records that should agree — the investment book against the accounting book, the firm's positions against the custodian's, cash against the bank statement, a trade against the counterparty's confirmation — and where they do not, the difference is a **break**. The Reconciliation Break is the record of that break: which two records disagreed, by how much, why, how serious it is, how long it has been open, and how it was resolved.

It exists as an entity, not as a transient finding, for the same reasons a Limit Breach (E-18) does: a break must be **escalated** through a process that needs a record to act on; a break is **audited** — internal audit and the regulator ask "what breaks occurred, how aged are they, and what was done"; and the **ageing** of a break is itself a control signal — a break open for thirty days says something a freshly-identified one does not. The difference is recomputable from the two source records; the cause classification, the ageing and the resolution trail are not, and those are why the break is stored.

A Reconciliation Break is shaped like a Limit Breach (E-18): an identified event with a status that moves through investigation and escalation to resolution, while the event itself is never deleted.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `break_id` | varchar | Primary key. |
| `reconciliation_type` | varchar | What was reconciled — `position` / `cash` / `transaction` / `ibor_abor` / `custodian` / `counterparty`. |
| `record_a_ref` | varchar | The first record being compared — the OpenIM-side record (a holding E-04, a cash flow E-06, a transaction E-05). |
| `record_b_ref` | varchar | The second record — the counter-record it disagreed with (the other book, the custodian's, the counterparty's). |
| `as_of_date` | date | The date the two records are being compared *as of*. |
| `identified_date` | date | The date the break was identified. |
| `difference_amount` | decimal | The monetary difference between the two records, where applicable. |
| `difference_qty` | decimal | The quantity difference, where the break is a position quantity. |
| `cause_classification` | varchar | The classified root cause — `timing` / `pricing` / `missing_transaction` / `data_error` / `fx` / `fees` / `unexplained`. |
| `materiality` | varchar | `low` / `medium` / `high` — the materiality of the break. |
| `age_days` | int | Days since `identified_date`; derived, kept for ageing and escalation. |
| `status` | varchar | `open` / `investigated` / `escalated` / `resolved` / `accepted` (a break formally accepted rather than corrected). |
| `resolved_date` | date | When the break was resolved or accepted; null while open. |
| `resolution_note` | varchar | How the break was resolved — the correcting entry made, or the rationale for acceptance. |
| `correcting_entry_ref` | varchar | A reference to the transaction or adjustment that resolved the break, where one was made. |

## Notes

- The break record is **immutable as an event** — the disagreement happened on a date. Its `status`, `age_days`, `resolved_date` and resolution fields are updated as the break moves through investigation to resolution, but the break is never deleted, even once resolved.
- `age_days` is the control signal: unresolved breaks are aged and escalated by materiality, so a stale break is visible rather than buried. Recurring breaks of the same cause and pairing are a process-quality signal in their own right.
- The difference is recomputable from the two source records; the cause classification, the ageing and the resolution trail are not, which is why the break is stored rather than computed as a transient view.

## Out of scope

- The two records being compared — those are the entities other Service Domains own (E-04 Holding / Position on its two books, E-06 Cash Flow Event, E-05 Transaction); E-24 references them and records the difference, it does not own them.
- The correcting entry that resolves a break — that is a Transaction (E-05) or an adjustment in the relevant book; E-24 references it through `correcting_entry_ref`.
- The escalation workflow itself — who acts at each step from `open` through `escalated` to `resolved` — named as an open extension; the entity carries the `status` field, not the process.

## Owned and consumed by

- **Owned by:** SD-12.10 Reconciliation.
- **Consumed by:** SD-12.1 Investment Book of Record (IBOR), SD-12.2 Accounting Book of Record (ABOR), SD-14.7 Internal Control & Assurance, SD-14.8 Internal Audit, SD-16.1 Corporate & Fund Governance.

## Open extensions

- The escalation workflow — the path from `open` through `escalated` to `resolved`, and who acts at each step.
- Recurring-break detection — the pattern across breaks of the same pairing and cause over time.
- The break-to-correcting-entry sub-model — linking a break to the full set of adjustments that closed it.
