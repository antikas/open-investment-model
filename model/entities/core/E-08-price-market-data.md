# E-08 — Price & Market Data

Observed market data for an instrument (E-02) — prices, yields, rates, spreads, FX. The observable inputs that value liquid holdings and feed risk and analytics.

## Purpose

Where E-07 Valuation is the *value of a holding*, E-08 is the *market observation* a valuation may be built from. A liquid instrument is valued at its market price; that price is a Price & Market Data point. Beyond pricing, market data is the raw input to market-risk measurement, performance attribution, and analytics — yield curves, credit spreads, FX rates, index levels, volatilities.

The entity is named here with its essential shape. Market-data management is a substantial domain in its own right (SD-13.4); the full depth — vendor-feed reconciliation, the term structure of curves, point-in-time correctness of market data — sits in the public-markets specialisation and the open extensions below.

## Attribute schema (essential shape)

| Column | Type | Definition |
|---|---|---|
| `market_data_id` | varchar | Primary key. |
| `instrument_id` | varchar (FK → E-02) | The instrument the observation is for; null for an instrument-independent observation (an FX rate, a benchmark rate). |
| `data_type` | varchar | `price` / `yield` / `spread` / `fx_rate` / `index_level` / `volatility` / `reference_rate`. |
| `observation_date` | date | The date the observation is *as of*. |
| `value` | decimal | The observed value. |
| `currency` | char | The currency, where applicable. |
| `provider` | varchar | The market-data provider the observation came from. |

## Notes

- Market data is **observed**, not assigned — it is sourced from external providers and exchanges, validated, and distributed. The OpenIM record is the validated, distributed observation.
- The distinction from E-07 Valuation matters: a Price is a market fact; a Valuation is the value of a *holding*, which for a liquid holding is derived from a Price and for an illiquid one is not. Conflating them is the mistake the separation avoids.

## Out of scope

- The value of a *holding* — that is E-07 Valuation; a Price is a market fact, a Valuation is the value of a position, derived from a Price for a liquid holding and not for an illiquid one.
- The full market-data depth — curve term structure, vendor-feed reconciliation, point-in-time correctness — that is the public-markets specialisation and an open extension; E-08 carries only the essential shape.
- A benchmark or index level held as managed comparator reference data — that is E-10 Benchmark / Index; E-08 holds raw observed data points.

## Owned and consumed by

- **Owned by:** SD-13.4 Market & Reference Data Management.
- **Consumed by:** SD-08.1 Security Pricing, SD-07.1 Market Risk Management, SD-09 Performance & Analytics, SD-11.3 FX Execution & Share-Class Hedging.

## Open extensions

- The full market-data model in the public-markets specialisation — curves and their term structure, the vendor-feed reconciliation model, point-in-time correctness for market data.
- The relationship between a Price observation and the E-07 Valuation that consumes it.
