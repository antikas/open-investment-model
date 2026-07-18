# E-03 — Portfolio / Mandate

The container. An institutional investor's capital is organised into portfolios — and a portfolio is governed by a mandate that sets its objective, its benchmark and its constraints. Every holding (E-04) sits in a portfolio.

## Purpose

An investor does not hold positions in a single undifferentiated pool. Capital is structured: a strategic asset allocation splits it across asset classes; within each, capital sits in portfolios, sleeves, mandates and accounts. A portfolio is the unit a performance number is struck for, a benchmark is set against, a set of investment guidelines is monitored against, and a risk limit applies to. Both a private-equity allocation and a public-equity separately managed account are portfolios — the container generalises across the whole investor.

The **mandate** is the governing definition of a portfolio: its objective, return target, risk appetite, benchmark, and the constraints it must hold to. The model carries the mandate as the governing attributes of the portfolio; a standalone mandate entity is an open extension if mandates need their own lifecycle.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `portfolio_id` | varchar | **Golden key.** The OpenIM-assigned identifier for the portfolio. |
| `portfolio_name` | varchar | Canonical name. |
| `portfolio_type` | varchar | `total_fund` / `asset_class_portfolio` / `mandate` / `sleeve` / `sma` / `account`. |
| `parent_portfolio_id` | varchar (FK → self) | The parent in a portfolio hierarchy — a sleeve within an asset-class portfolio within the total fund; null at the top. |
| `asset_class` | int (FK → E-09) | The asset class — the integer surrogate key `asset_class_key` of the E-09 entry — for an asset-class portfolio; null for the total fund. |
| `mandate_objective` | varchar | The portfolio's investment objective. |
| `benchmark_id` | varchar (FK → E-10) | The benchmark the portfolio is measured against. |
| `base_currency` | char | The portfolio's reporting currency. |
| `managed_by_entity_id` | varchar (FK → E-01) | The legal entity managing the portfolio in the *manager* role — internal, or an external manager for an SMA / mandate. |
| `governing_plan_id` | varchar (FK → E-29) | The allocation-plan version **currently in force** governing this portfolio — the strategic asset allocation, reference-portfolio or commitment-pacing plan it is run to. The portfolio-grained pointer to the single in-force plan; distinct from `E-29.subject_id`, which every plan *version* carries pointing back at its subject (so the in-force plan is reached directly here rather than by scanning every version's effective window). Null before a plan is set. |
| `inception_date` | date | When the portfolio was established. |
| `status` | varchar | `active` / `closed` / `in_transition`. |

## Notes

- Portfolios form a **hierarchy** — the total fund at the top, asset-class portfolios beneath, sleeves and accounts below those. `parent_portfolio_id` carries it; exposure and performance roll up the hierarchy.
- A portfolio managed by an external manager (an SMA, a segregated mandate) references that manager through `managed_by_entity_id` in the manager role of E-01.
- The allocation the portfolio is run to is the **allocation plan in force** (E-29 Allocation Plan), reached through `governing_plan_id`. Two directions are modelled and are not the same edge: `governing_plan_id` (here) is the portfolio's pointer to its *single in-force* plan version; `E-29.subject_id` runs the other way, and every plan *version* — current and historical — carries it pointing back at the portfolio it governs. Traversing from the plan side yields the full version history; the pointer here yields only the version currently in force.
- The constraints a mandate imposes — what the portfolio may and may not hold — are coded investment rules consumed by SD-10 Investment Compliance & Guideline Monitoring; the model names the objective and benchmark on the portfolio, and leaves the coded rule library to that domain.

## Out of scope

- The positions inside a portfolio — that is E-04 Holding / Position; E-03 is the container, not its contents.
- A standalone mandate with its own lifecycle and amendment history — the model holds the mandate as the governing attributes of the portfolio; a separate Mandate entity is an open extension.
- The coded investment guidelines and restrictions a mandate imposes — those are the coded rule library of SD-10 Investment Compliance & Guideline Monitoring, not attributes of E-03.
- The benchmark a portfolio is measured against — that is E-10 Benchmark / Index, which E-03 references through `benchmark_id`.

## Owned and consumed by

- **Owned by:** **faceted** — E-03 carries two facets owned by different Service Domains. The **portfolio facet** (the live holdings container, the constraint-monitoring subject, the report subject) is owned by **SD-05.2 Portfolio Management & Monitoring** — the ongoing system of record for the operative portfolio. The **mandate facet** (objectives, return target, risk appetite, time horizon and constraints) is owned by **SD-01.2 Investment Mandate & Policy Definition**. SD-05.1 Portfolio Construction is **not** an owner — it *constructs* the initial target from the SD-05.2 record and the SD-01.2 mandate; SD-05.2 is the ongoing authoritative source. The faceted pattern is documented in [`ownership-map.md`](../../ownership-map.md).
- **Consumed by:** SD-05 Portfolio Management (all domains), SD-09 Performance & Analytics (performance is struck per portfolio), SD-10 Investment Compliance & Guideline Monitoring, SD-07 Investment Risk, SD-13.10 Investment Reporting & Dashboards.

## Open extensions

- A standalone **Mandate** entity, if mandates need a lifecycle independent of the portfolio (amendment history, mandate versioning).
- The coded **investment guideline / restriction** sub-model and its relationship to SD-10.
