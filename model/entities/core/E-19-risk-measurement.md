# E-19 — Risk Measurement

A point-in-time risk result — a VaR figure, an exposure, a sensitivity, a stress-test loss — and the record of how it was produced. The risk analogue of Valuation (E-07): a measured number, stored, with its method and confidence.

## Purpose

Risk management produces numbers — value-at-risk, expected shortfall, a factor sensitivity, a counterparty exposure, the loss under a stress scenario. The Risk Measurement entity is the record of one such number, at one date, for one subject.

It is a deliberate modelling choice that risk *results* are an **entity**, not only metrics in the semantic layer. OpenIM treats *metric definitions* — how VaR is defined, how exposure is computed — as semantic-layer concerns (SD-13.8). But a risk *result* — this VaR figure, for this portfolio, on this date, from this model — is a stored artefact, for the same reason a Valuation is: model-risk governance and regulatory audit require risk numbers to have provenance. "What was our VaR on that date, which model produced it, and how confident were we" must be answerable from a record, not from a recomputation that may no longer reproduce the original. A risk number consumed by a governance decision is a fact that happened; the model stores it.

Like Valuation, Risk Measurement is **append-only** — a re-run or a restatement is a new row, never an overwrite.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `measurement_id` | varchar | Primary key — the surrogate identity of one stored measurement (one row). |
| `risk_type` | varchar | The risk *domain* the measurement belongs to — `market` / `credit` / `counterparty` / `liquidity` / `concentration` / `scenario` / `stress` / `climate`. Part of the measurement's identity: it determines the single authoritative producing capability (a market-risk measure and a credit-risk measure are different instances, produced by different sources). The risk domain, not the kind of number — see `measure_type` and the orthogonality note below. |
| `subject_type` | varchar | What was measured — `total_fund` / `portfolio` (E-03) / `holding` (E-04) / `counterparty` (E-01) / `asset_class` (E-09). |
| `subject_id` | varchar | The identifier of the thing measured. |
| `measure_type` | varchar | The risk measure — the *kind of number* — `var` / `expected_shortfall` / `sensitivity` / `exposure` / `concentration` / `stress_loss` / `liquidity_coverage` / `liquidity_tier_classification` (the per-holding liquidity tier SD-07.3 assigns by applying the SD-01.11 taxonomy). Orthogonal to `risk_type` — see the note below. |
| `as_of_date` | date | The date the measurement is *as of*. |
| `value` | decimal | The measured value. |
| `currency` | char | The currency, where the measure is monetary. |
| `method` | varchar | How it was produced — historical simulation, parametric, Monte Carlo, full revaluation, factor model, scenario application. |
| `scenario_id` | varchar (FK → E-17) | The scenario applied, where the measurement is a stress or scenario result; null for an unconditional measure. |
| `model_id` | varchar | The risk model that produced the measurement — the link to model governance (SD-14.4). |
| `confidence_score` | float | A confidence score for the measurement, where the method warrants one. |

## Notes

- **`risk_type` and `measure_type` are two orthogonal axes.** `risk_type` is the risk *domain* — which kind of risk is being measured (market, credit, liquidity, climate …), and which capability is the authoritative source for it. `measure_type` is the *kind of number* — how the risk is expressed (a VaR, an expected shortfall, a sensitivity, an exposure figure, a stress loss). The two cross rather than mirror: a single `measure_type` can appear under more than one `risk_type` (an `exposure` figure is produced both as a counterparty-risk measure and within a concentration measure), and a `risk_type` carries several `measure_type` values (market risk is expressed as VaR, expected shortfall and sensitivities). `risk_type` is therefore the discriminator that assigns a measurement to its single producing source; `measure_type` describes the figure once the domain is known. Neither subsumes the other, so both are kept. The one token that appears on both axes — `concentration` — is not an ambiguity: `risk_type = concentration` is the risk domain (the SD-07.4 partition), while `measure_type = concentration` is the concentration-ratio figure (a top-N or single-issuer share) produced under that domain — the same one-domain-one-figure relationship as `risk_type = market` with `measure_type = var`, simply sharing a word.
- **The grain — `risk_type` is in the identity.** `measurement_id` is the surrogate primary key: one stored measurement is one row, identified by `measurement_id`. `risk_type` is part of the measurement's *logical* identity — it is the key the record set is partitioned on (a market-risk measure and a credit-risk measure are different instances by domain, produced by different authoritative sources), the same shape Holding / Position (E-04) uses with `book`. So `risk_type` is a required column that is part of the identity for ownership and partition purposes, while `measurement_id` remains the single-column surrogate row-handle; every measurement carries exactly one `risk_type`, and that value names the one source authoritative for it.
- **Append-only.** The set of Risk Measurements for a subject and measure is its risk trajectory over time. A re-run for a prior date — a corrected or restated number — is a new row; restatement is detected by comparing the new measurement to the prior one for the same `as_of_date`.
- The distinction from the semantic layer matters: the *definition* of VaR is a metric definition (SD-13.8); a *VaR result* is a Risk Measurement. Conflating them loses the provenance that model risk and audit depend on — the same separation OpenIM keeps between a performance metric's definition and the stored Valuation it is computed from.
- `model_id` is the hook into Model Governance & AI Governance (SD-14.4): every stored risk number names the model behind it, so a model found to be flawed can be traced to every measurement it produced.
- A Risk Measurement is what a Risk Limit (E-16) is evaluated against; a crossing produces a Limit Breach (E-18).

## Out of scope

- The *definition* of a risk measure — how VaR is defined, how exposure is computed — that is a semantic-layer metric definition (SD-13.8); E-19 is a stored risk *result*, not a metric definition.
- The configured constraint a measurement is evaluated against — that is E-16 Risk Limit; a crossing produces an E-18 Limit Breach, not a Risk Measurement.
- The scenario a stress result was produced under — that is E-17 Scenario; E-19 references it through `scenario_id`, but the definition is E-17.
- The value of a *holding* — that is E-07 Valuation; E-19 is the risk analogue, a measured risk number, not a position value.

## Owned and consumed by

- **Owned by:** key-partitioned by `risk_type`. **SD-07.1 Market Risk Management** produces `risk_type = market`; **SD-07.2 Credit & Counterparty Risk Management** — `credit` / `counterparty`; **SD-07.3 Liquidity Risk Management** — `liquidity`; **SD-07.4 Concentration & Exposure Risk** — `concentration`; **SD-07.6 Scenario Analysis & Stress Testing** — `scenario` / `stress`; **SD-07.8 Climate Risk Analytics** — `climate`. Each measurement Service Domain is the sole authoritative source for instances of its risk type. SD-07.7 Investment Risk Reporting & Limits Governance is the consolidating *consumer* (limits-breach detection and risk-committee reporting); it is not a producing source. The full pattern is documented in [`ownership-map.md`](../../ownership-map.md).
- **Consumed by:** SD-07.7 Investment Risk Reporting & Limits Governance (limit evaluation, risk reporting), SD-14.4 Model Governance & AI Governance, SD-16.1 Corporate & Fund Governance; SD-05.6 Liquidity-Aware Portfolio Management and SD-11.2 Liquidity Management consume the `risk_type = liquidity` partition for the per-holding liquidity classification.

## Open extensions

- Restatement modelling — how a re-run risk number for a prior date relates to the original.
- The decomposition of an aggregate measure (a total-fund VaR) into its contributions (by portfolio, by factor) — whether each contribution is its own Risk Measurement or a sub-structure.
- The relationship to the R.E.S.T.-style risk-metrics catalogue at the evaluation layer.
