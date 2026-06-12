# E-33 — Financial Plan

The structured, versioned multi-year financial plan a wealth manager builds and maintains for a household — the comprehensive advisory artefact the planning review consumes, with the goal hierarchy, the cash-flow model, the retirement and decumulation strategy, the insurance and risk-protection strategy and the estate / wealth-transfer strategy organised into one stored record.

## Purpose

A wealth manager's value proposition is the **comprehensive plan**: the multi-year cash-flow projection, the retirement and decumulation strategy, the insurance and risk-protection strategy, the estate and wealth-transfer strategy, and the goal hierarchy that ties it all together. The plan is the artefact the planning review runs against; the artefact the regulated suitability gate gates products against; the artefact the consumer-duty fair-value-evidencing record points to when asked what the firm did for this client. None of that is answerable from a transient calculation — the plan must exist as a stored record, versioned through time, with a known content and a known approval state.

The Financial Plan is that record. It is a computed-metric-as-entity: a record that feeds a governance, audit or regulatory decision answerable only from a stored record, *and* one that recomputation may not reproduce. The plan meets both tests for a regulated wealth manager: the suitability defence and the Consumer-Duty fair-value-evidencing record must be answerable from the plan in force when the advice was given — not from today's plan, which today's circumstances and market conditions would no longer reproduce. "What plan did we present, what did the client accept, on what date, against which goal set" must be answerable from a stored, versioned record.

The plan is **versioned**: a revised plan is a new version, the prior is retained, and a re-presentation of advice is traceable to the version in force at the time. The lifecycle moves through `draft` → `presented_to_client` → `accepted` → `in_force` → `superseded`.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `financial_plan_id` | varchar | Primary key. |
| `household_entity_id` | varchar (FK → E-01) | The client / household the plan is for, in the client role of Legal Entity. |
| `version` | varchar | The version of the plan; a re-plan is a new version, the prior is retained. |
| `effective_from` | date | The date the version is effective from. |
| `effective_to` | date | The date the version ceased to be effective (null while the version is `in_force`). |
| `plan_content` | document (JSON) | The plan content — the multi-year cash-flow model, retirement / decumulation strategy, insurance and risk-protection strategy, estate / wealth-transfer strategy. The structured-document grammar is an open extension. |
| `goal_set` | array (FK → E-30) | The goals included in the plan — the household's prioritised goal hierarchy at this version. |
| `approved_by_advisor` | varchar | The advisor who approved the plan version for presentation to the client. |
| `approval_date` | date | The date the plan version was approved. |
| `status` | varchar | `draft` / `presented_to_client` / `accepted` / `in_force` / `superseded`. |

## Notes

- **Versioned, append-by-version.** A plan is re-built periodically — annually for most relationships, on demand when the client's circumstances or markets change materially. Each re-plan is a new version; the prior is retained, so an advisory decision stays traceable to the plan in force when it was taken. Restatement is detected by comparing the new plan to the prior for the same household.
- **`goal_set` is the link to E-30.** The household's goal hierarchy lives as E-30 Goal records (one per goal, owned by SD-01.14); the plan references the set of goals included in this version. A revised goal hierarchy is a revised plan version.
- **The plan is the advisory artefact; the goals sit inside it; the suitability gate sits over it.** SD-01.14 Goals-Based Planning frames the goal hierarchy as a strategy artefact (the E-30 records); SD-15.15 Financial & Wealth Planning wraps the comprehensive advisory delivery around it (the plan); SD-15.12 Client Advice & Suitability gates the products the plan recommends. The Financial Plan is the SD-15.15 advisory artefact that sits between the SD-01.14 strategy framing and the SD-15.12 regulated gate.
- **The plan is the Consumer-Duty fair-value-evidencing record.** Under FCA Consumer Duty, the firm must be able to demonstrate, on demand, that the advice it gave was fair, suitable, and in the client's interest. The stored plan, with its approval record and version trajectory, is the evidence.

## Out of scope

- The individual goals the plan sits around — those are E-30 Goal records owned by SD-01.14 Goals-Based Planning; E-33 references the goal set through `goal_set`, it is not the goals themselves.
- The measured probability of meeting each goal — that is E-31 Goal Progress Measurement (computed by SD-09.5); E-33 is the plan the measure is reported against, not the measure itself.
- The regulated suitability assessment of a specific product recommendation — that is SD-15.12 Client Advice & Suitability's gate, recorded against the client profile; E-33 is the plan whose recommendations the gate is applied to.
- The portfolio that funds a goal — that is E-03 Portfolio / Mandate (the sub-portfolio funding the goal, referenced from E-30); E-33 is the plan that frames the household, not the funding container.
- The household's tax position — that is SD-17.4's strategic tax position (the lot record from E-32 underpinning it); the plan *consumes* the tax position as input, it does not own it.

## Owned and consumed by

- **Owned by:** SD-15.15 Financial & Wealth Planning — the wealth manager's advisory capability that builds, maintains and reviews the plan as the comprehensive multi-year planning artefact.
- **Consumed by:** SD-15.12 Client Advice & Suitability (the regulated suitability gate consumes the plan in advising on each recommendation), SD-15.14 Client & Investor Reporting (the plan-driven reporting the client receives), SD-01.14 Goals-Based Planning (the goal-hierarchy framing within the plan — the strategy capability frames the goals, the plan sits them inside the comprehensive advisory artefact).

## Open extensions

- The structured-document grammar for `plan_content` — the typed schema for the cash-flow model, the decumulation strategy, the estate strategy and the insurance and risk-protection strategy.
- The plan's relationship to the SD-15.12 suitability gate — whether the suitability record is stored against the plan, or against each product recommendation that the plan emits.
- Multi-advisor and multi-jurisdiction plans — how a plan version is owned where the household has more than one advisor or covers more than one jurisdiction.
- The plan-to-portfolio link — how a plan's recommended allocations are materialised through E-29 Allocation Plan records.
