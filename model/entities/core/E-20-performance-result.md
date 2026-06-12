# E-20 — Performance Result

A stored point-in-time return figure — a portfolio's return for a period, on a stated basis — with the inputs, methodology version and provenance behind it. The performance analogue of Valuation (E-07) and Risk Measurement (E-19): a computed number, stored, with how it was produced.

## Purpose

Performance measurement produces numbers — a portfolio's time-weighted return for the month, a money-weighted return since inception, a GIPS-composite return for the year. The Performance Result entity is the record of one such figure, for one subject, over one period, on one basis.

It is a deliberate modelling choice that a return *result* is an **entity**, not only a metric in the semantic layer. OpenIM treats the *definition* of a return — how time-weighted return is computed, how a composite is constructed — as a semantic-layer concern (the Metric Definition, E-22, owned by SD-13.8). But a return *result* — this return, for this portfolio, over this period, computed to this methodology version — is a stored artefact, for the same reason a Valuation is: GIPS verification and performance audit require return figures to have provenance. "What return did we report for that period, computed how, from which inputs, to which methodology version" must be answerable from a record, not from a recomputation that may no longer reproduce the original once a methodology version or an underlying valuation has changed.

Like Valuation and Risk Measurement, a Performance Result is **append-only** — a recomputed or restated return for a prior period is a new row, never an overwrite.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `performance_result_id` | varchar | Primary key. |
| `subject_type` | varchar | What the return is for — `portfolio` (E-03) / `mandate` (E-03) / `composite` (a GIPS composite) / `total_fund` / `asset_class` (E-09). |
| `subject_id` | varchar | The identifier of the subject. |
| `period_start` | date | The start of the measurement period. |
| `period_end` | date | The end of the measurement period; the date the return is *as of*. |
| `return_basis` | varchar | `gross` / `net` — gross of fees or net of fees. |
| `return_method` | varchar | How the return was computed — `time_weighted` / `money_weighted` / `modified_dietz` / `since_inception`. |
| `return_value` | decimal | The return, as a rate over the period. |
| `currency` | char | The currency the return is expressed in, where a currency basis applies. |
| `metric_definition_id` | varchar (FK → E-22) | The governed Metric Definition the return was computed to — the methodology version in force. |
| `composite_id` | varchar | The GIPS composite the result belongs to, where `subject_type = composite`; null otherwise. |
| `valuation_source` | varchar | The valuation basis the return was computed from — the book of valuations (E-07) underlying the period. |
| `confidence_score` | float | A confidence score for the result, where the inputs warrant one (an interim return on incomplete valuations). |

## Notes

- **Append-only.** The set of Performance Results for a subject and period is its reported-return history. A recomputed return for a prior period — restated because an underlying valuation was corrected or a methodology version changed — is a new row; restatement is detected by comparing the new result to the prior one for the same subject and period.
- `metric_definition_id` is the hook that makes the return reproducible-in-principle and audit-traceable: every stored return names the Metric Definition (E-22) version it was computed to, so a change to how a return is defined does not silently rewrite history.
- GIPS verification is the load-bearing consumer: a composite return must be defensible against the inputs and the methodology as they stood when it was struck, which is exactly what an append-only, provenance-bearing record preserves.

## Out of scope

- The *definition* of a return measure — how time-weighted return is computed, how a composite is constructed — that is a Metric Definition (E-22) in the semantic layer; E-20 is a stored return *result*, not the definition.
- The value of a holding the return is computed from — that is E-07 Valuation; E-20 is the return derived over a period of valuations, not the valuation itself.
- Performance attribution — the decomposition of a return into its sources (allocation, selection, currency) — named as an open extension; the entity carries the headline return figure.

## Owned and consumed by

- **Owned by:** SD-09.1 Performance Measurement.
- **Consumed by:** SD-09.2 Performance Attribution, SD-09.3 Performance Appraisal, SD-09.6 GIPS & Performance Standards Compliance, SD-16.2 Owner & Investor Reporting, SD-16.1 Corporate & Fund Governance, SD-14.8 Internal Audit.

## Open extensions

- Performance attribution as a sub-structure or a related entity — the decomposition of a return into allocation, selection and currency effects.
- The relationship between a Performance Result and the benchmark return (E-10) it is measured against — relative return and tracking error as stored figures.
- Restatement modelling — how a recomputed return for a prior period relates to the original.
