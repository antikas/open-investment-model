# E-30 — Goal

A client's investment objective — a target value to reach by a target date, at a priority, with a required probability of success. The unit the goals-based paradigm allocates against: a household has many goals, each funded by its own sub-portfolio.

## Purpose

For a wealth manager running goals-based investing, the client does not have a single objective optimised against one policy benchmark. The household has a hierarchy of goals — fund retirement, fund a child's education, leave a legacy, buy a second home — each with its own time horizon, its own required probability of success, and its own funded sub-portfolio. The household portfolio is the emergent sum of those independently-funded sub-portfolios.

The Goal is the record of one such objective: what it is, what it targets, by when, at what priority, and how likely it must be to succeed. It is the stable per-goal record the goals-based loop turns on — the subject SD-01.13 allocates a sub-portfolio to, the subject SD-09.5 measures a probability of meeting, and the subject SD-15.15 tracks funding adequacy against over the life of the plan.

A Goal is **distinct from the mandate facet of E-03 Portfolio / Mandate**. The mandate is the supply-side governing definition of a *container* — its objective, benchmark and constraints. The Goal is the demand-side objective the container is built to *meet*. A goal sits above the portfolio: it can be re-funded by a different sub-portfolio, and it persists as the client's objective regardless of how the capital that funds it is currently organised. It sits in the same family as E-27 Liability Profile, E-28 Risk Budget and E-29 Allocation Plan — the objective and target records that allocation and portfolio construction serve.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `goal_id` | varchar | Primary key. |
| `household_entity_id` | varchar (FK → E-01) | The client / household the goal belongs to, in the client role of Legal Entity. |
| `goal_name` | varchar | The goal's name — *retirement income*, *Anna's university fees*, *legacy bequest*. |
| `goal_type` | varchar | The kind of goal — `retirement` / `education` / `legacy` / `major_purchase` / `lifestyle` / `philanthropic`. |
| `priority_layer` | varchar | The goals-based priority tier — `safety` (must be met) / `lifestyle` (important) / `aspirational` (desirable). Determines the risk profile of the funding sub-portfolio. |
| `target_value` | decimal | The amount the goal requires. |
| `target_currency` | char | The currency the target is expressed in. |
| `target_date` | date | When the goal must be met. |
| `required_probability_of_success` | float | The probability of meeting the goal the client requires — higher for safety goals, lower for aspirational ones. |
| `funding_portfolio_id` | varchar (FK → E-03) | The sub-portfolio funding the goal; null while a goal is framed but not yet funded. A goal may be funded by more than one sub-portfolio over its life — the current funding link is held here, the history in E-03's lifecycle. |
| `status` | varchar | `proposed` / `active` / `met` / `abandoned` / `revised`. |

## Notes

- **One household, many goals, many sub-portfolios.** The cardinality is the load-bearing reason the Goal is its own entity: a household holds a hierarchy of goals, each funded by a sub-portfolio (E-03), and the household allocation is assembled bottom-up as the sum. A model that folded the goal into the portfolio could not represent the hierarchy or the bottom-up assembly.
- **`priority_layer` drives the funding profile.** A safety goal is funded conservatively to a high required probability of success; an aspirational goal is funded for upside at a lower required probability. The layer is the link between the behavioural goal hierarchy and the per-goal allocation SD-01.13 sets.
- **The required probability is the demand; the measured probability is the supply.** `required_probability_of_success` is what the client needs; the *measured* probability of meeting the goal at a point in time is E-31 Goal Progress Measurement, computed by SD-09.5. The gap between the two drives re-allocation.

## Out of scope

- The comprehensive multi-year financial plan the goal sits within — the cash-flow model, the estate and wealth-transfer strategy, the decumulation plan — that is the advisory artefact of SD-15.15, a distinct candidate entity; E-30 is one objective within a plan, not the plan.
- The per-goal target allocation and the assembled household allocation — those are the allocation artefacts of SD-01.13, carried as E-29 Allocation Plan; E-30 is the objective the allocation is set to meet, not the allocation.
- The measured probability of meeting the goal — that is E-31 Goal Progress Measurement; E-30 carries the *required* probability the client sets, not the *measured* probability SD-09.5 computes.
- The funding sub-portfolio itself — that is E-03 Portfolio / Mandate; E-30 references it through `funding_portfolio_id`.

## Owned and consumed by

- **Owned by:** SD-01.14 Goals-Based Planning — the strategy capability that frames and maintains the client's goal hierarchy. The goal originates in the planning act that elicits and prioritises the client's objectives as the strategic statement of what the household's capital is for.
- **Consumed by:** SD-01.13 Goals-Based Allocation (allocates a sub-portfolio per goal), SD-09.5 Investment Analytics & Insight (computes the probability of meeting the goal), SD-15.15 Financial & Wealth Planning (the advisory delivery the goal hierarchy sits inside — the advisory-wrapping consumer of the goal hierarchy), SD-15.14 Client & Investor Reporting (per-goal progress reporting), SD-15.12 Client Advice & Suitability (the goal as the objective a recommendation is suitable against).

## Open extensions

- The goal-hierarchy structure — the parent / child and dependency relationships between goals (a legacy goal contingent on a retirement goal being met first).
- The funding-adequacy sub-model — how a goal's required contributions are derived from its target, horizon and current funding.
- The relationship between a Goal and the behavioural-finance mental-accounting framing the goals-based paradigm rests on.
