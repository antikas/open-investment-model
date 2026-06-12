# E-31 — Goal Progress Measurement

A stored point-in-time measure of the probability of meeting a goal — the figure SD-09.5 computes for a goal, on a stated basis, with the assumptions and provenance behind it. The goals-based analogue of Risk Measurement (E-19) and Performance Result (E-20): a computed number, stored, with how it was produced.

## Purpose

For a wealth manager running goals-based investing, the question the client asks is "am I on track to meet this goal?" SD-09.5 answers it by computing the probability of meeting each goal as a forward-looking measure on the goal's funding sub-portfolio, against the capital-market assumptions and the goal's current funding position. The Goal Progress Measurement is the record of one such figure: for one goal, as of one date, on one set of assumptions.

It is a deliberate modelling choice that the measure is an **entity**, not only a transient analytic. Under the computed-metric-as-entity principle, OpenIM stores a computed figure when it feeds a governance, audit or regulatory decision answerable only from a record, *and* recomputation may not reproduce it. The probability of meeting a goal meets both tests for a regulated wealth manager: the suitability and advice record must be able to answer "what probability of meeting this goal did we tell the client, and when" from a stored figure; and the measure cannot be reproduced after the fact, because it was computed against the capital-market assumptions and the funding position as they stood at the time. "What did we tell the client, computed how, from which assumptions" must be answerable from a record, not from a recomputation that today's assumptions would no longer reproduce.

Like Risk Measurement and Performance Result, a Goal Progress Measurement is **append-only** — a re-measure for a later date is a new row, never an overwrite; the set of measurements for a goal is its progress history.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `goal_progress_measurement_id` | varchar | Primary key. |
| `goal_id` | varchar (FK → E-30) | The goal the measure is for. |
| `as_of_date` | date | The date the probability is *as of*. |
| `probability_of_success` | float | The computed probability of meeting the goal by its target date on the current funding and allocation. |
| `funding_adequacy` | decimal | The current funded value of the goal's sub-portfolio relative to the funding the goal requires — the surplus or shortfall against target. |
| `projected_value_at_target` | decimal | The projected value of the funding sub-portfolio at the goal's target date, on the assumptions in force. |
| `cma_set_ref` | varchar | The capital-market-assumption set the measure was computed against (SD-01.3) — the assumptions in force, named so the figure is reproducible-in-principle. |
| `metric_definition_id` | varchar (FK → E-22) | The governed Metric Definition the probability was computed to — the methodology version in force. |
| `computed_by_sd` | varchar | The Service Domain that computed the measure — SD-09.5. |

## Notes

- **Append-only.** The set of Goal Progress Measurements for a goal is its progress history. A re-measure — run because the markets moved, the funding changed, or the assumptions were updated — is a new row; the trajectory toward the goal is read across the rows.
- **`cma_set_ref` and `metric_definition_id` are the provenance hooks.** Every stored measure names the capital-market-assumption set (E-29 / SD-01.3) and the Metric Definition (E-22) version it was computed to, so a change to the assumptions or the methodology does not silently rewrite the as-advised history.
- **The suitability record is the load-bearing consumer.** A regulated wealth manager must be able to defend "we told the client this goal had an N% probability of success on this date, on these assumptions" — exactly what an append-only, provenance-bearing record preserves, and exactly what a transient recomputable analytic would lose.
- The measured `probability_of_success` is compared against the goal's `required_probability_of_success` (E-30): the gap is what drives re-allocation across and within goals (SD-01.13).
- **Produced only when SD-01.13 is active.** E-31 is produced only when SD-01.13 Goals-Based Allocation is active; an asset-only-model-portfolio wealth manager (which runs SD-01.4 as its allocation paradigm), and any institutional investor not running goals-based allocation, does not produce or consume it.

## Out of scope

- The *required* probability of success — that is the client's demand, held on E-30 Goal; E-31 is the *measured* probability, the supply-side figure.
- The realised return of the funding sub-portfolio — that is E-20 Performance Result; E-31 is a forward-looking probability, not a realised return. They are distinct entities, not variants of one.
- The *definition* of the probability measure — how the probability of success is computed — that is a Metric Definition (E-22) in the semantic layer; E-31 references it through `metric_definition_id`.
- The capital-market assumptions themselves — those are SD-01.3's analytical artefact; E-31 names the set it used, it does not hold the assumptions.

## Owned and consumed by

- **Owned by:** SD-09.5 Investment Analytics & Insight — the Service Domain that computes the goals-based forward-looking measure.
- **Consumed by:** SD-01.13 Goals-Based Allocation (the gap between measured and required probability drives re-allocation), SD-15.15 Financial & Wealth Planning (the funding-adequacy input to the planning review), SD-15.14 Client & Investor Reporting (per-goal progress reporting), SD-15.12 Client Advice & Suitability (the as-advised probability in the suitability record).

## Open extensions

- The Monte-Carlo or analytic distribution behind the headline probability — whether the full distribution warrants storage alongside the point estimate.
- The relationship between a Goal Progress Measurement and the re-allocation decision (SD-01.13) it triggers.
- Restatement modelling — how a re-measure on revised assumptions relates to the prior as-advised figure.
