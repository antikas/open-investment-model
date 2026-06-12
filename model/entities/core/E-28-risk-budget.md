# E-28 — Risk Budget

A risk allowance allocated to a strategy, pod or portfolio manager — the allocated amount, its basis, and the allocation lifecycle. Distinct from a Risk Limit (E-16): a deliberate share of a finite risk pool handed to a team, not a ceiling a measured risk must stay within.

## Purpose

A multi-strategy or multi-manager platform allocates **risk capital** the way an asset-only investor allocates asset-class weights. The unit of allocation is not a portfolio weight but a risk budget — a volatility contribution, a value-at-risk allowance, a stop-loss limit — handed to a strategy, a trading pod or a portfolio manager. The Risk Budget is the record of one such allocation: the amount, the measure it is expressed in, the team it is allocated to, and how the allocation changes over time as the platform reallocates toward performers and cuts drawdowns.

It is genuinely distinct from a Risk Limit (E-16). A Risk Limit is a *constraint* — a ceiling a measured risk must not cross, a configured threshold. A Risk Budget is an *allocation* — a deliberate distribution of a finite risk pool: budgets sum to a total, and they are reallocated continuously as a deliberate management act. A VaR ceiling on a pod is a Risk Limit; the share of the firm's total VaR budget the pod is given to use is a Risk Budget. The constraint and the allocation overlap in numbers but differ in meaning, and the **allocation / reallocation lifecycle** is the content E-16 cannot carry — which is why the Risk Budget is its own entity.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `risk_budget_id` | varchar | Primary key. |
| `subject_type` | varchar | What the budget is allocated to — `strategy` / `pod` / `portfolio_manager` / `portfolio` (E-03). |
| `subject_id` | varchar | The identifier of the team or portfolio the budget is allocated to. |
| `budget_measure` | varchar | The measure the budget is expressed in — `volatility_contribution` / `var_allowance` / `stop_loss` / `capital_at_risk`. |
| `allocated_amount` | decimal | The risk allowance allocated. |
| `total_pool_ref` | varchar | The total risk pool the budget is a share of — the parent the allocations sum to. |
| `leverage_limit` | decimal | The leverage allowed against the budget, where applicable. |
| `drawdown_trigger` | decimal | The drawdown level at which the budget is automatically cut or reviewed. |
| `currency` | char | The currency, where the measure is monetary. |
| `effective_from` | date | When this allocation became active. |
| `effective_to` | date | When it was superseded by a reallocation; null while active. |
| `allocated_by` | varchar | The risk-capital or CIO function that made the allocation. |

## Notes

- **Versioned by reallocation.** A risk budget is reallocated continuously — toward performers, away from drawdowns. Each reallocation is a new effective-dated record; the prior is retained, so the allocation history of a pod is traceable. This append-by-version lifecycle is the content that distinguishes a budget from a static limit.
- The distinction from E-16 Risk Limit is the load-bearing one: a limit is a boundary (a ceiling), a budget is a share of a pool (an allocation). The budgets allocated against a pool sum to the pool; limits do not sum to anything. A pod typically has both — a Risk Budget it is given and Risk Limits it must stay within.
- The `drawdown_trigger` is the performance-reactive hook — the level at which a budget is automatically cut, which is the multi-strategy platform's core risk-allocation discipline.

## Out of scope

- The configured ceiling a measured risk must stay within — that is E-16 Risk Limit; E-28 is the allocated allowance, not the constraint, and a team typically carries both.
- The measured risk number itself — that is E-19 Risk Measurement; E-28 is the budget the measurement is consumed against, not the measurement.
- The performance of the team the budget is allocated to — that is the performance and attribution domain (E-20); E-28 carries the allocation, not the return it produced.

## Owned and consumed by

- **Owned by:** SD-01.9 Risk-Capital & Strategy Allocation.
- **Consumed by:** SD-07.1 Market Risk Management (measuring usage against the budget), SD-07.7 Investment Risk Reporting & Limits Governance, SD-05.2 Portfolio Management & Monitoring, SD-09.2 Performance Attribution (risk-adjusted contribution against budget).

## Open extensions

- The reallocation model — the rules and triggers by which a budget is cut, increased or reallocated across the pool.
- The relationship between a Risk Budget and the Risk Measurements (E-19) that measure usage against it.
- The hierarchy of budgets — a firm-level pool allocated to strategies, sub-allocated to pods.
