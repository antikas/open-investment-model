# E-29 — Allocation Plan

A versioned plan that governs how capital is allocated — a strategic asset allocation, a reference-portfolio and factor risk budget, or a commitment-pacing plan — so a decision traces to the plan in force when it was taken. Key-partitioned by `plan_type`.

## Purpose

The allocation a portfolio is run to is set by a plan: the strategic asset allocation and its policy bands, the reference portfolio and factor risk budget under a total-portfolio approach, or the commitment / deployment pacing schedule for private markets. Each is a governed, approved statement of intent that changes over time — and when it changes, the decisions taken under the prior version must remain traceable to it. The Allocation Plan is the versioned record of that plan, so a portfolio's positioning can always be measured against the allocation that governed it at the time.

It is one entity with a `plan_type` discriminator rather than three near-identical plan entities — the model's key-partitioned pattern again (as E-04 is partitioned by `book`). The plan kinds differ in content — target weights, a reference portfolio, a pacing schedule — but they are the same kind of artefact: a versioned, approved, effective-dated plan that capital is allocated against. The common shape is the traceability the three surfacing capabilities each asked for; the differing content is carried in the plan-content field.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `plan_id` | varchar | Primary key. |
| `plan_type` | varchar | The partition key — `strategic` (a strategic asset allocation) / `reference_portfolio` (a total-portfolio reference and factor budget) / `commitment_pacing` (a private-markets pacing plan). Part of the plan's identity. |
| `subject_id` | varchar (FK → E-03) | The portfolio, pool or mandate the plan governs. |
| `version` | varchar | The version of the plan. |
| `effective_from` | date | When this version became the plan in force. |
| `effective_to` | date | When it was superseded; null while active. |
| `plan_content` | document (JSON) | The plan itself — target weights and policy bands (`strategic`), the reference holdings and factor risk budget (`reference_portfolio`), or the period-by-period commitment / deployment schedule (`commitment_pacing`). |
| `approved_by` | varchar | The governance body or function that approved the plan version. |
| `approval_date` | date | When the plan version was approved. |
| `status` | varchar | `draft` / `approved` / `in_force` / `superseded`. |

## Notes

- **Versioned, append-by-version.** A plan that is re-set — a strategic reallocation, a revised pacing schedule — is a new version; the prior version is retained with its effective window, so a decision is always traceable to the plan version in force when it was taken. This traceability is the load-bearing reason the plan is an entity.
- **Key-partitioned by `plan_type`.** A strategic allocation, a reference portfolio and a commitment-pacing plan are the same kind of artefact — a versioned, approved plan — distinguished by type. The `plan_type` partition determines which Service Domain is the authoritative source for that plan kind, the same pattern E-04 uses on `book`.
- `plan_content` carries the type-specific structure as data — target weights for a strategic plan, reference holdings and a factor budget for a reference portfolio, a pacing schedule for commitment pacing — in the computation-as-data spirit of the model's other typed-content fields.

## Out of scope

- The policy benchmark a strategic allocation encodes — that is reference data (E-10 Benchmark / Index) administered by the benchmark-management capability; the Allocation Plan names which benchmark encodes the policy, it does not hold the benchmark.
- The realised holdings the plan is implemented as — those are E-04 Holding / Position; the Allocation Plan is the target the holdings are managed toward, not the holdings themselves.
- The mandate's objectives and constraints — those are the mandate facet of E-03 Portfolio / Mandate; the Allocation Plan is the allocation set within the mandate, not the mandate.

## Owned and consumed by

- **Owned by:** key-partitioned by `plan_type`, co-equal. **SD-01.4 Strategic Asset Allocation** is the authoritative source for `plan_type = strategic`; **SD-01.6 Total Portfolio Approach** for `plan_type = reference_portfolio`; **SD-01.10 Commitment Pacing & Deployment Planning** for `plan_type = commitment_pacing`. Neither holds schema authority over the others; the schema is the model's, defined here. The full pattern is documented in [`ownership-map.md`](../../ownership-map.md).
- **Consumed by:** SD-05.1 Portfolio Construction (construction to the plan), SD-05.2 Portfolio Management & Monitoring (drift against the plan), SD-01.5 Tactical & Dynamic Asset Allocation (tactical tilts within the strategic plan), SD-16.2 Owner & Investor Reporting.

## Open extensions

- The `plan_content` document grammar per plan type — the typed structure of target weights, reference holdings and pacing schedules.
- The relationship between an Allocation Plan version and the rebalancing decisions taken under it.
- The drift model — measuring a portfolio's position against the policy bands of the strategic plan in force.
