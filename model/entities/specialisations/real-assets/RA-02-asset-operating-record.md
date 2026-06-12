# RA-02 — Asset Operating Record

The periodic operating data of a real asset (RA-01) — occupancy, throughput, generation, net operating income — the data that drives the asset's value and performance. One record per asset per reporting period.

## Purpose

A real asset is not valued from a quoted price; its value is driven by what it *does*. A building earns rent and incurs operating cost; a toll road carries traffic; a wind farm generates power and sells it; a forest grows merchantable timber. The Asset Operating Record captures that period-by-period operating reality so that performance can be measured and the next appraisal (RA-05) can be grounded in observed cash generation rather than assumption.

Where the core Holding (E-04) records *what is owned* and Valuation (E-07) records *what it is worth*, RA-02 records *how it performed* — the operating layer between them. Net operating income is the pivot: it is the figure an income-approach appraisal capitalises, so the operating record and the valuation are directly linked.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `operating_record_id` | varchar | Primary key. |
| `real_asset_id` | varchar (FK → RA-01) | The asset this record reports on. |
| `period_start` | date | Start of the reporting period. |
| `period_end` | date | End of the reporting period. |
| `gross_income` | decimal | Gross revenue earned in the period — rent, tolls, power sales, offtake, crop receipts. |
| `operating_expense` | decimal | Operating cost in the period — management, maintenance, utilities, rates, insurance. |
| `net_operating_income` | decimal | `gross_income` − `operating_expense` — the income-approach appraisal input. |
| `occupancy_rate` | float | For real estate — the share of lettable space let and income-producing. |
| `throughput` | decimal | For infrastructure — the volumetric measure of use: vehicles, passengers, MWh generated, tonnes handled. |
| `throughput_unit` | varchar | The unit `throughput` is expressed in. |
| `availability_pct` | float | For an availability-based asset — the share of the period the asset was available to the standard the contract requires. |
| `capacity_utilisation` | float | Output as a share of the asset's rated capacity — the load / capacity factor. |
| `capex_incurred` | decimal | Capital expenditure incurred in the period — distinct from operating expense, it changes the asset rather than maintaining it. |
| `revenue_basis` | varchar | How revenue arises — `regulated` / `availability` / `contracted` / `merchant`; the basis governs how stable the income is. |
| `currency` | char | The currency the amounts are expressed in. |
| `source` | varchar | The source the record was captured from — an asset manager report, an operator statement, a property manager return. |

## Notes

- `revenue_basis` is the risk discriminator. A `regulated` or `availability` asset earns a contracted, low-variability income; a `merchant` asset is exposed to price and volume. The same `net_operating_income` figure carries very different risk depending on this field, and the appraisal (RA-05) discount rate reflects it.
- The metric set is deliberately superset: a given asset populates the fields its category uses — a building populates `occupancy_rate` and leaves `throughput` null; a wind farm populates `throughput`, `capacity_utilisation` and `availability_pct` and leaves `occupancy_rate` null.
- Operating records are **periodic facts** — a record, once the period is closed, is not overwritten. A correction is a new record; restatement is detected by comparing records for the same period.

## Out of scope

- The asset the record reports on — that is RA-01 Direct Real Asset, referenced through `real_asset_id`; RA-02 is the operating data, not the asset.
- What the asset is *worth* — that is E-07 Valuation and RA-05 Asset Appraisal; RA-02 records how the asset *performed*, the operating layer the income-approach appraisal capitalises.
- The contractual leases that produce real-estate income — those are RA-03 Lease / Tenancy; RA-02's `gross_income` is the sum the leases produce, not the lease detail.
- The forecast / budget counterpart against which actuals are monitored — named as an open extension; RA-02 carries actuals only.

## Owned and consumed by

- **Owned by:** SD-04.10 Direct Real-Asset Management.
- **Populated via:** SD-13.6 GP & Manager Report Ingestion (asset-manager and operator reporting is captured on the same on-ramp as GP reporting).
- **Consumed by:** SD-08.3 Private-Asset Valuation (net operating income is the income-approach input), SD-09.1 Performance Measurement, SD-09.5 Investment Analytics & Insight, SD-05.2 Portfolio Management & Monitoring, SD-07.3 Liquidity Risk Management.

## Open extensions

- The forecast / budget counterpart — operating records carry actuals; the variance against an underwriting case is what stewardship monitors.
- A finer expense breakdown for operating-expense-ratio analysis.
- The link from a real-estate operating record to the underlying Lease set (RA-03), so portfolio income reconciles to the tenancy schedule.
