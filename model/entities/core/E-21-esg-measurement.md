# E-21 — ESG Measurement

A point-in-time ESG, sustainability or emissions data point for a subject — a score, a rating, an emissions figure, a taxonomy-alignment percentage — from a named provider, with its as-of date and methodology. The ESG analogue of Price & Market Data (E-08): an observed, multi-provider, time-series data point.

## Purpose

ESG and sustainability data has the same essential shape as market data: a value, for a subject, on a date, from a provider — and, like market data, the providers disagree. One rating agency scores an issuer differently from another; emissions estimates differ by methodology and vintage; taxonomy-alignment figures depend on the assessor. That **provider divergence is itself material information** — a wide spread across providers tells the investor something a single flattened number hides. The ESG Measurement entity carries one provider's data point per row, so divergence is first-class and visible rather than collapsed into a single value.

This is the parallel to E-08 Price & Market Data, and the reason ESG data is modelled as a measurement entity rather than only as a time-varying classification (E-11 / E-12): a categorical attribute — a controversy flag, a sector exclusion — fits the classification machinery, but a multi-provider numeric series with material divergence is closer to a market observation, and is modelled as one.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `esg_measurement_id` | varchar | Primary key. |
| `subject_type` | varchar | What the measurement is for — `instrument` (E-02) / `issuer` (E-01) / `fund` (PM-01) / `portfolio` (E-03). |
| `subject_id` | varchar | The identifier of the subject. |
| `pillar` | varchar | The ESG pillar or theme — `environmental` / `social` / `governance` / `climate` / `impact`. |
| `measure_type` | varchar | The kind of measurement — `score` / `rating` / `emissions` / `controversy` / `taxonomy_alignment` / `temperature_alignment`. |
| `as_of_date` | date | The date the measurement is *as of*. |
| `value` | decimal | The measured value, where numeric (a score, an emissions figure, an alignment percentage). |
| `rating_label` | varchar | The categorical label, where the measurement is a rating rather than a number; null for purely numeric measures. |
| `unit` | varchar | The unit of a numeric measure — `tco2e`, `score_0_100`, `pct`, where applicable. |
| `provider` | varchar | The ESG-data provider the measurement came from — the row is one provider's view. |
| `methodology` | varchar | The provider's methodology or framework version behind the measurement. |

## Notes

- **Multi-provider by row.** One ESG Measurement row is one provider's data point. The full set for a subject and measure across providers is the divergence picture — surfacing disagreement is a stated requirement, not a flaw to be reconciled away into a single number.
- The distinction from the classification machinery (E-11 / E-12) matters: a categorical, taxonomy-style ESG attribute — a binary exclusion, a sector flag — is a classification; a numeric, multi-provider, time-series measurement is an ESG Measurement. The clean split is by shape, not by topic, and some ESG data sits on each side.
- Growing assurance and disclosure regimes (the SFDR and ISSB sustainability-disclosure standards) raise the audit-provenance bar: a reported sustainability figure must name its provider, methodology and as-of date, which the per-provider row carries natively.

## Out of scope

- A categorical ESG attribute — a controversy flag, a sector exclusion, a binary screen — that is better carried as a time-varying classification (E-11 Classification Type & Value / E-12 Classification History); E-21 is the numeric, multi-provider, time-series measurement.
- A climate risk *result* produced by the risk function — a climate VaR, a transition-risk loss under a scenario — that is E-19 Risk Measurement (`risk_type = climate`); E-21 is the input ESG / emissions data, not the computed risk number.
- The raw market price of a green bond or a carbon allowance — that is E-08 Price & Market Data; E-21 is the sustainability attribute, not the market observation.

## Owned and consumed by

- **Owned by:** SD-13.9 ESG & Sustainability Data.
- **Consumed by:** SD-07.8 Climate Risk Analytics, SD-10.9 ESG & Sustainability Compliance, SD-05.1 Portfolio Construction (ESG-tilted construction), SD-16.2 Owner & Investor Reporting, SD-16.3 Regulatory Reporting & Filings (sustainability disclosure).

## Open extensions

- The provider-divergence model — how the spread across providers for a subject and measure is summarised and surfaced.
- Look-through aggregation — rolling issuer-level ESG measurements up to a portfolio-level footprint through the holdings.
- The relationship between an ESG Measurement and a derived portfolio sustainability metric defined in the semantic layer (E-22).
