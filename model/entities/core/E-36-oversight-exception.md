# E-36 — Oversight Exception

The structured exception record from the firm's oversight of an outsourced administrator — the shadow-NAV difference, the fee-calculation variance, the reconciliation-process gap, the breach-resolution lag — with its severity, monetary impact, investigation and resolution. The audit-trail record evidencing continuous control over delegated processing.

## Purpose

Accountability cannot be outsourced. A firm that delegates fund accounting, NAV calculation, reconciliation and operations processing to a third-party administrator remains responsible to the regulator, the board and its investors for what the administrator does. The regulatory regimes that codify this — the FCA outsourcing rules, the EBA Guidelines on Outsourcing Arrangements, DORA Chapter V, AIFMD Article 20 — all require the firm to evidence continuous, data-driven control over the delegated processing. The Oversight Exception is the record that makes that evidence operational: every exception the firm's oversight surfaces is stored, classified, investigated and resolved through the record.

The capability runs the shadow NAV (an independent, parallel NAV calculation that checks the administrator's struck NAV), independently verifies the administrator's fee and expense calculations, and reviews the administrator's reconciliation process. When any of those checks surfaces a difference, a variance, a gap or a resolution lag, the exception is the record of it.

The Oversight Exception is a computed-metric-as-entity: a record that feeds a governance, audit or regulatory decision answerable only from a stored record, *and* one that recomputation may not reproduce. The Oversight Exception meets both tests: the regulator and the audit committee must be able to ask "show me the exceptions your administrator oversight surfaced this quarter, how each was investigated and how each was resolved" — the answer must come from a stored record, not from a recomputation that today's reconciliations would no longer reproduce (the exception's evidence is the difference *as it existed*, which a re-run after correction would erase). The exception's set is the continuous-control evidence the oversight discipline exists to produce.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `oversight_exception_id` | varchar | Primary key. |
| `administrator_entity_id` | varchar (FK → E-01) | The administrator the exception is against, in the administrator role of Legal Entity. |
| `exception_date` | date | The date the exception was surfaced. |
| `exception_type` | varchar | The exception classification — `shadow_nav_difference` / `fee_calculation_variance` / `reconciliation_gap` / `breach_resolution_lag` / `other`. |
| `exception_description` | text | The exception as observed — what the firm's oversight saw that did not match the administrator's record. |
| `severity` | varchar | `minor` / `material` / `significant` — the firm's classification of the exception's bearing on the integrity of the delegated processing. |
| `monetary_impact_amount` | decimal | The monetary impact of the exception where one can be quantified (a shadow-NAV difference, a fee variance); null where not material or not yet known. |
| `investigation_note` | text | The investigation findings — what the firm's review concluded about the cause, the scope and the bearing on prior reporting periods. |
| `resolution_action` | text | The action taken — the administrator's correction, the firm's adjustment, the process change put in place. |
| `resolution_date` | date | The date the exception was resolved; null while open or under investigation. |
| `status` | varchar | `open` / `investigating` / `resolved` / `escalated`. |

## Notes

- **Append-by-update on the exception grain.** An exception exists as one record updated through its lifecycle — surfaced, investigated, resolved or escalated. The exception text and the original observation are preserved; the investigation findings and resolution action are added as the lifecycle progresses. A resolved exception is not deleted — the resolved record is the continuous-control evidence.
- **`shadow_nav_difference`** is the canonical exception type — the difference between the firm's independently-calculated shadow NAV and the administrator's struck NAV, beyond tolerance. The shadow-NAV check is the primary mechanism the oversight discipline runs; the exception record is the audit trail of every difference the check has surfaced.
- **The exception set is the continuous-control evidence.** The regulator does not ask "did you have an oversight process" — it asks "show me what your oversight surfaced this quarter and what you did about it." The set of exception records, with their investigations and resolutions, is the load-bearing answer.
- **`escalated`** status moves an exception into a broader investigation — typically when the cause turns out to be systemic, the monetary impact crosses a threshold, or the same exception type has recurred. The escalation route is to SD-14.7 Internal Control & Assurance and SD-14.1 Operational Risk Management; the exception record carries the flag but the broader investigation runs outside it.

## Out of scope

- The administrator's own internal exception management — that is the administrator's record, not the firm's; E-36 is the firm-side record of what the firm's oversight saw, distinct from what the administrator's own controls saw.
- The reconciliation breaks the firm operates on its own books — those are E-24 Reconciliation Break, owned by SD-12.10 Reconciliation; E-36 is the *administrator's* reconciliation-process gap, surfaced by the firm's review of the administrator's process.
- The shadow NAV result itself — the shadow-NAV figure is a kind of E-07 Valuation (the firm's independent valuation), and the administrator's struck NAV is also E-07; E-36 carries the *exception* the comparison surfaces, not the underlying valuations.
- The commercial management of the administrator relationship — that is SD-17.8 Vendor, Outsourcing & Service-Provider Oversight, which manages the contract, the SLA and the exit plan; E-36 is the operational-oversight record SD-17.8 *consumes* as input to the relationship.
- The remediation programme that responds to a systemic finding — that runs outside the exception record; the `escalated` status is the flag, the programme is separate.

## Owned and consumed by

- **Owned by:** SD-12.16 Outsourced-Operations Oversight — the retained-organisation capability that runs the shadow NAV, the fee verification and the administrator-process review.
- **Consumed by:** SD-14.7 Internal Control & Assurance (the continuous-control evidence consumed into the management-assurance picture), SD-14.1 Enterprise & Operational Risk Management (the operational-risk events the exception set surfaces), SD-17.8 Vendor, Outsourcing & Service-Provider Oversight (the operational-evidence input to the commercial relationship), SD-14.8 Internal Audit (the as-surfaced record the audit reads).

## Open extensions

- The shadow-NAV tolerance and divergence-investigation sub-model — the precise threshold below which a difference is not raised as an exception, and the staged investigation route above it.
- The relationship to E-24 Reconciliation Break — the model could capture the administrator-side reconciliation gap as a specialisation of E-24, or as a distinct E-36 type. The current model keeps them distinct (firm-side breaks vs administrator-side exceptions); whether that boundary holds is open.
- The cross-administrator aggregation — how exception sets across multiple administrators are aggregated into a single oversight picture.
- The systemic-remediation linkage — the structured relationship between an exception record carrying `status = escalated` and the operational-risk programme that closes the cause.
