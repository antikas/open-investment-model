# E-17 — Scenario

A defined stress or hypothetical scenario — a named set of market shocks and assumptions applied across the portfolio to ask "what would happen if." The definition a stress test or scenario analysis runs against.

## Purpose

Scenario analysis and stress testing ask what the portfolio would be worth, and what risk it would carry, under conditions other than today's. A Scenario is the *definition* of one such condition: a named, governed set of shocks — an equity-market fall, a rates move, a credit-spread widening, an FX dislocation, a liquidity freeze — that can be applied consistently across every holding. Modelling the scenario as an entity, rather than as a transient analyst calculation, is what makes a stress result reproducible, auditable and comparable over time: the same scenario run this quarter and last is genuinely the same scenario.

A Scenario is a definition; running it produces Risk Measurements (E-19) tagged to it.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `scenario_id` | varchar | Primary key. |
| `scenario_name` | varchar | Canonical name. |
| `scenario_type` | varchar | `historical` (a replay of a past episode) / `hypothetical` (a forward-constructed condition) / `reverse` (a target loss, solved back to the conditions that produce it) / `regulatory` (a prescribed supervisory scenario). |
| `description` | varchar | What the scenario represents and why it is run. |
| `shock_set` | document (JSON) | The structured set of shocks — the factors moved and by how much. A typed specification the stress engine interprets, in the same computation-as-data spirit as PM-10 Fund Terms. |
| `horizon` | varchar | The time horizon the scenario is expressed over. |
| `effective_from` | date | When this version of the scenario became active. |
| `effective_to` | date | When it was retired or superseded; null while active. |
| `owner` | varchar | The risk owner accountable for the scenario definition. |

## Notes

- **Scenarios are versioned, not edited in place.** A scenario whose shocks are recalibrated is a new version; the prior version is retained, so a historical stress result remains traceable to the exact scenario definition it was produced from.
- The `shock_set` is structured data, not prose — the stress engine reads and applies it, the same discipline as the `formula_spec` of a computed fund term.
- A Scenario applies across asset classes — an equity shock, a rates move and a spread widening hit a multi-asset portfolio together — which is why it is a core entity, not specific to any one specialisation pack.

## Out of scope

- The result of running a scenario — that is E-19 Risk Measurement, tagged to the scenario through `scenario_id`; E-17 is the definition, E-19 is the produced number.
- The configured risk constraint a stress result is judged against — that is E-16 Risk Limit; E-17 is the hypothetical condition, not the threshold.
- The `shock_set` document grammar — the typed vocabulary the shocks are expressed in — named as an open extension; the entity carries the shock set as structured data without the formal grammar.

## Owned and consumed by

- **Owned by:** SD-07.6 Scenario Analysis & Stress Testing.
- **Consumed by:** SD-07.1 Market Risk Management, SD-07.3 Liquidity Risk Management, SD-07.7 Investment Risk Reporting & Limits Governance; produces Risk Measurements (E-19).

## Open extensions

- The `shock_set` document grammar — the typed vocabulary a scenario's shocks are expressed in.
- Scenario libraries and the relationship between a reverse-stress scenario and the loss target that defines it.
