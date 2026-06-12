# E-10 — Benchmark / Index

A benchmark or index, and its constituents, held as managed reference data. The comparator a portfolio or holding's performance is measured against.

## Purpose

Performance is meaningless without a comparator. E-10 is the managed reference data for those comparators across asset classes: a constituent-weighted market index for a public-markets portfolio, a vintage / strategy peer universe for a private-markets fund, an investor-constructed blend for a total-portfolio benchmark. It is referenced by Portfolio / Mandate (E-03) as the portfolio's benchmark and is consumed throughout the performance and allocation domains.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `benchmark_id` | varchar | **Golden key.** The OpenIM identifier for the benchmark or index. |
| `benchmark_name` | varchar | Canonical name. |
| `benchmark_kind` | varchar | `market_index` (a constituent-weighted index) / `private_peer_universe` (a vintage / strategy peer set) / `reference_rate` (a rate-based hurdle, e.g. a cash rate plus spread) / `custom` (an investor-constructed blend). |
| `provider` | varchar | The provider — an index provider, a private-markets data provider (Cambridge Associates, Burgiss / MSCI, Preqin), or internal for a custom benchmark. |
| `asset_class` | varchar (FK → E-09) | The asset class the benchmark covers. |
| `vintage_year` | int | The vintage cohort, for a private peer universe. |
| `methodology` | varchar | The methodology — constituent-weighted return, vintage quartile, pooled IRR, public-market equivalent (PME). |
| `currency` | char | The benchmark's currency basis. |

## Constituents

A `market_index` benchmark has **constituents** — the instruments in it and their weights, effective-dated as the index rebalances. The constituent sub-structure is part of the public-markets specialisation and the open extensions below. A `private_peer_universe` has no constituents in this sense — its membership is the provider's set of peer funds, defined by the provider, not the investor; the mapping from an investor's own fund into that universe is **PM-12 Benchmark Cross-Reference** in the private-markets pack.

## Out of scope

- The effective-dated constituent and weight rows of a market index — that is PB-09 Index Constituent in the public-markets pack; E-10 carries the benchmark header, not its membership.
- The mapping from an investor's own fund into an external private-markets peer universe — that is PM-12 Benchmark Cross-Reference; E-10 is the benchmark data, PM-12 is the join.
- The portfolio a benchmark is set against — that is E-03 Portfolio / Mandate, which references E-10 through `benchmark_id`.
- Raw observed market data — prices, yields, rates — that is E-08 Price & Market Data, not a benchmark.

## Owned and consumed by

- **Owned by:** SD-13.5 Benchmark & Index Data Management.
- **Consumed by:** SD-09.2 Performance Attribution, SD-09.4 Benchmark Management, SD-09.8 Private-Markets Performance Analytics, SD-01.4 Strategic Asset Allocation (the policy benchmark), E-03 Portfolio / Mandate.

## Open extensions

- The full index-constituent sub-structure — constituents, weights, effective-dated rebalancing — in the public-markets specialisation.
- Custom / blended benchmark construction, including the total-portfolio policy benchmark.
- The relationship between E-10 and PM-12 Benchmark Cross-Reference — the benchmark data versus the fund-to-universe mapping.
