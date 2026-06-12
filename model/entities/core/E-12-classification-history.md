# E-12 — Classification History

The bi-temporal record of time-varying classifications on a holding or investment — which department holds it, its credit rating, its sector, its strategy, its geography — with every change dated, so an aggregation is correct at *any* point in time, not only now.

## The problem this entity solves

Holdings and investments carry attributes that change. An investment transfers from one department to another; a credit rating moves from AAA to AA; a sector is reclassified. These attributes drive how things are grouped and aggregated in reporting — and the requirement is exact: a query scoped to one quarter must show the classification that was true *in that quarter*. The sum across all values of a classifier must equal the total at every point in time — no double-counting, no gaps.

A flat table updated in place loses history the moment a value changes. A standard slowly-changing dimension is better but becomes fragile when data arrives from multiple sources, at different frequencies, and must be corrected after the fact. The deeper issue is that standard designs conflate *identity*, *relationships* and *attributes* in one structure; classification history must keep attribute change separate from identity, and it must keep two clocks separate.

## The pattern — two time axes

The entity records every classification as a dated event, and keeps **two separate dates**:

- **`effective_from` / `effective_to`** — when the classification was *true in the business*.
- **load date** — when the platform *received* the record.

For current data the two coincide. For a historical record loaded later — or a correction — they can be years apart. Keeping them separate is what makes it possible to load history correctly, and to answer both "what was the classification in that quarter?" and "what did we *believe* it was, as of when we reported it?"

One row exists per change event, per classification type, per holding or investment. The history is append-only: a change produces a new row; the prior row is never overwritten and never deleted.

## Gaps are held explicitly

Where no historical signal exists for a period, the classification is set to the reserved **`UNKNOWN`** value (E-11), not left null. Every holding with no resolved classification for a period joins to `UNKNOWN`, which keeps aggregations clean — they still sum to the total — and keeps the gap *visible and queryable*. When a real classification is later recovered, a row is inserted with the correct `effective_from` and the placeholder is superseded.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `classification_id` | varchar | Primary key. |
| `subject_type` | varchar | What is being classified — `holding` (E-04) or, in the private-markets pack, `fund_investment` (PM-09). |
| `subject_id` | varchar | The identifier of the holding or investment being classified. |
| `classification_type` | varchar (FK → E-11) | The classifier — department, credit rating, sector, strategy, geography. |
| `classification_value` | varchar (FK → E-11) | The value within that classifier; the reserved `UNKNOWN` value where no signal exists. |
| `effective_from` | date | When this classification became true in the business. |
| `effective_to` | date | When it was superseded; null while current. |
| `confidence_tier` | int | The reliability of the record: `1` deterministic (a system audit-log change event) / `2` bounded (a snapshot delta or issuance window) / `3` inferred (a proxy signal) / `4` manual (human reconciliation, no data signal). |
| `source_method` | varchar | How the record was derived — change event, snapshot delta, identifier lineage, document proxy, report anchor, or manual. |

## Notes

- **Durable identity is a prerequisite.** Classification history can only be tracked correctly against a subject that has a *durable* identifier — one that survives operational system changes. Where an operational identifier is not durable, the model resolves to a durable key and tracks the operational identifiers as aliases (E-13).
- **`confidence_tier` makes uncertain history honest.** A reconstructed or inferred classification is queryable but distinguishable from a high-confidence one. Reporting can default to tiers 1–2 until tier 3–4 records have been reviewed and accepted. A tier is not permanent — a tier-4 manual record is upgraded if a system record later surfaces for the same period.
- **All classifiers are one problem.** Department is not special — it is one instance of "a time-varying attribute." Adding a new classifier type is a governance action on E-11, not a schema change.

## Out of scope

- The definition of *what classifiers exist* and *what values are valid* within each — that is E-11 Classification Type & Value; E-12 records classifications, E-11 defines them.
- The asset-class taxonomy itself — that is E-09 Asset Class; E-12 may record a strategy classification, but the asset-class structure is E-09.
- Identity resolution and the operational identifiers a subject has been seen under — that is E-13 Entity Alias; E-12 presumes a durable identifier already resolved.

## Owned and consumed by

- **Owned by:** SD-13.7 Data Quality & Governance.
- **Classifier definitions from:** E-11 Classification Type & Value.
- **Consumed by:** SD-09.1 Performance Measurement and SD-09.2 Performance Attribution (department- and strategy-level performance), SD-13.10 Investment Reporting & Dashboards, SD-07.4 Concentration & Exposure Risk.

## Open extensions

- The full bi-temporal query pattern — how a point-in-time aggregation joins the fact to this history with a date-range predicate.
- The completeness target — every subject carries a classification record covering its full active life, gaps held as `UNKNOWN`, no null foreign keys.
- This entity is the canonical model's worked example of **P5 — Time-Series Uncertainty**.
