# E-22 — Metric Definition

The governed definition of a metric — its formula, inputs, conventions and variant forms, owned and versioned. The single authoritative statement of *how a number is defined*, that the stored results computed to it (E-20, E-19) reference.

## Purpose

A buy-side firm computes the same metric many ways unless it governs the definition. "Return" is time-weighted or money-weighted, gross or net, in base currency or local; "exposure" is notional or delta-adjusted; "yield" is one of several conventions. The Metric Definition entity is the governed statement of one such metric — the formula, the inputs it consumes, the currency and period conventions, the variant forms, the owner and the version — so that everyone computing the metric computes the same thing, and a stored result can name the exact definition it was computed to.

It is the semantic-layer counterpart to the stored-result entities: where E-20 Performance Result and E-19 Risk Measurement are *the numbers*, E-22 is *the definition the numbers were computed to*. A stored result references its Metric Definition, so a change in how a metric is defined is a new version of the definition — not a silent rewrite of the figures already reported under the old one.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `metric_definition_id` | varchar | Primary key. |
| `metric_name` | varchar | Canonical name — `time_weighted_return`, `value_at_risk_99_1d`, `tracking_error`, `dpi`. |
| `metric_family` | varchar | The domain the metric belongs to — `performance` / `risk` / `exposure` / `accounting` / `esg`. |
| `formula_spec` | document (JSON) | The structured specification of the computation — the inputs, the operations, the conventions — in the computation-as-data spirit of the E-17 `shock_set` and PM-10 fund terms. |
| `input_metrics` | array | The metric definitions or entities this metric is computed from, where it composes lower-level metrics. |
| `currency_convention` | varchar | The currency basis — `base` / `local` / `hedged`, where applicable. |
| `period_convention` | varchar | The period basis — `daily` / `monthly` / `since_inception` / `annualised`, where applicable. |
| `version` | varchar | The version of the definition. |
| `effective_from` | date | When this version of the definition became active. |
| `effective_to` | date | When it was superseded; null while active. |
| `owner` | varchar | The steward accountable for the definition. |
| `status` | varchar | `draft` / `certified` / `deprecated`. |

## Notes

- **Versioned, not edited in place.** A metric whose formula or convention is changed is a new version; the prior version is retained, so a stored result computed under the old definition stays traceable to the exact definition it used.
- The `formula_spec` is structured data, not prose — it is the typed specification the analytics layer reads and applies, the same discipline as the E-17 Scenario `shock_set`.
- This is the one governance-layer promotion in the entity model: the data-quality rule, the lineage record and the certified-dataset register stay as Service-Domain artefacts (SD-13.7), but the Metric Definition is first-class because a stored result (E-20, E-19) needs to *reference* it.

## Out of scope

- The computed *result* of applying a metric definition — that is E-20 Performance Result, E-19 Risk Measurement, or E-07 Valuation; E-22 is the definition, not the number produced from it.
- The data-quality rule, the lineage record and the certified-dataset register — these stay Service-Domain artefacts of SD-13.7 Data Quality & Governance, not first-class entities; E-22 is promoted because stored results reference it, which those records do not require.
- The semantic model and the business glossary as a whole — that is the broader SD-13.8 estate; E-22 is the single governed metric definition within it.

## Owned and consumed by

- **Owned by:** SD-13.8 Semantic & Metric Layer.
- **Consumed by:** SD-09.1 Performance Measurement (E-20 references it), SD-07.1 / SD-07.2 / SD-07.3 / SD-07.4 Investment Risk Management (E-19 references it), SD-16.2 Owner & Investor Reporting, SD-16.4 Financial Reporting & Disclosure.

## Open extensions

- The `formula_spec` document grammar — the typed vocabulary a metric's computation is expressed in.
- The dependency graph between composed metrics — a portfolio metric built from instrument-level metrics.
- The relationship between a Metric Definition and the certified-dataset register it is computed over.
