# E-16 — Risk Limit

A configured constraint on risk — the threshold a measured risk must stay within. The limit framework an institutional investor governs itself by: market-risk limits, credit and counterparty limits, concentration limits, liquidity limits.

## Purpose

Risk management is not only measurement; it is measurement *against a constraint*. A Risk Limit is that constraint, made an explicit, governed, versioned record rather than a number in a spreadsheet or a policy document. Every investor runs a limit framework — a VaR ceiling on a portfolio, a maximum single-issuer exposure, a counterparty exposure cap, a minimum liquidity buffer — and the framework is configured data: a limit has a definition, a scope, a threshold and a warning level, it is owned and approved, and it changes over time under governance. The Risk Limit entity is universal — it is not specific to any asset class — which is why it is core.

It is the risk analogue of Fund Terms (PM-10): configured, versioned, evaluable data, not a scalar buried in prose.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `limit_id` | varchar | Primary key. |
| `limit_type` | varchar | The kind of risk constrained — `market` / `credit` / `counterparty` / `concentration` / `liquidity` / `leverage` / `mandate`. |
| `measure` | varchar | What is measured against the limit — VaR, expected shortfall, single-issuer exposure %, sector exposure %, counterparty exposure, liquidity-coverage ratio, etc. |
| `scope_type` | varchar | What the limit applies to — `total_fund` / `portfolio` / `counterparty` / `issuer` / `asset_class`. |
| `scope_id` | varchar | The identifier of the thing in scope — a Portfolio (E-03), a Legal Entity (E-01), an Asset Class (E-09) — null for a total-fund limit. |
| `threshold` | decimal | The hard limit value. |
| `warning_level` | decimal | The level at which a warning is raised ahead of the hard threshold; null if none. |
| `enforcement` | varchar | `hard` (a breach blocks or escalates) or `soft` (a breach is reported and monitored). |
| `effective_from` | date | When this version of the limit became effective. |
| `effective_to` | date | When it was superseded; null while current. |
| `owner` | varchar | The risk owner accountable for the limit. |
| `approved_by` | varchar | The governance body or role that approved it. |

## Notes

- **Versioned.** A limit framework changes under governance. A change inserts a new row with a new `effective_from` and closes the prior row — the full history of "what the limit was, when" is preserved, which a breach investigation and an audit both need.
- A limit is *evaluated* by a Service Domain against a Risk Measurement (E-19); a Limit Breach (E-18) records the event where a measurement crosses a limit.
- Investment-mandate guideline limits — what a portfolio may and may not hold — are closely related; OpenIM models the mandate's coded restrictions through SD-10 Investment Compliance & Guideline Monitoring, and `limit_type = mandate` is the bridge where a mandate constraint is expressed as a risk limit.

## Out of scope

- The measured risk number a limit is evaluated against — that is E-19 Risk Measurement; E-16 is the configured constraint, E-19 is the result.
- The event where a measurement crosses a limit — that is E-18 Limit Breach; E-16 defines the threshold, E-18 records the crossing.
- The coded investment-guideline restriction library a mandate imposes — that is SD-10 Investment Compliance & Guideline Monitoring; `limit_type = mandate` is the bridge, but the rule library is the service domain's.
- The portfolio, counterparty or issuer a limit is scoped to — those are E-03, E-01 and E-09, which E-16 references through `scope_id`.

## Owned and consumed by

- **Owned by:** SD-07.7 Investment Risk Reporting & Limits Governance.
- **Consumed by:** SD-07.1 Market Risk Management, SD-07.2 Credit & Counterparty Risk Management, SD-07.3 Liquidity Risk Management, SD-07.4 Concentration & Exposure Risk, SD-10.1 Investment Guideline Monitoring.

## Open extensions

- The relationship between a Risk Limit of `limit_type = mandate` and the coded investment-restriction library in SD-10.
- Limit hierarchies — a total-fund limit decomposed into portfolio-level sub-limits.
