# PB-09 — Index Constituent

A membership of an instrument in a market index — the instrument, its weight, and the period that membership and weight were effective, as the index rebalances and reconstitutes.

**Specialises:** E-10 Benchmark / Index. E-10 carries the benchmark *header* — what the index is, its provider, its methodology. PB-09 is the constituent sub-structure E-10 names but leaves to the public-markets pack: the effective-dated membership and weight rows that make a `market_index` benchmark actually replicable.

## Purpose

A market index is meaningless as a comparator unless its composition is known through time. PB-09 is the entity that holds it: one row per (index, instrument, effective period). It exists because index membership and weight **change** — quarterly rebalances adjust weights, periodic reconstitutions add and drop constituents — and a portfolio measured against an index needs the index's composition *as it was* on any date, not just today. The constituent rows are also what a passive or index-aware mandate replicates, and what performance attribution (SD-09.2) decomposes return against. The weight is most often float-adjusted market capitalisation, but the methodology is the index provider's, so PB-09 records the resulting weight rather than re-deriving it.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `index_constituent_id` | varchar | Primary key — one row per (index, instrument, effective period). |
| `benchmark_id` | varchar (FK → E-10) | The index this is a constituent of — an E-10 record of kind `market_index`. |
| `instrument_id` | varchar (FK → E-02) | The constituent instrument — a PB-01 listed equity or PB-02 debt instrument. |
| `effective_from` | date | The date this membership and weight became effective (a rebalance / reconstitution effective date). |
| `effective_to` | date | The date the membership or weight was superseded; null for the currently-effective row. |
| `index_weight` | float | The constituent's weight in the index over the effective period. |
| `weight_basis` | varchar | How the weight is set — `float_market_cap` / `full_market_cap` / `price` / `equal` / `fundamental` / `capped`. |
| `shares_in_index` | decimal | The constituent's index share count — the divisor-adjusted quantity the weight is built from. |
| `capping_applied` | boolean | Whether a methodology weight cap (e.g. a single-name or aggregate cap) bound this constituent's weight. |
| `inclusion_event` | varchar | What put the row in effect — `rebalance` / `reconstitution` / `corporate_action` / `initial`. |
| `provider` | varchar | The index provider whose methodology set the weight (e.g. the index family operator). |

## Notes

- PB-09 is **bi-temporally honest by construction**: the `effective_from` / `effective_to` pair records when a weight *was true in the index*, which is exactly the E-12 effective-time pattern. A date-ranged query reconstructs the index as it stood on any past date.
- Index weights are the index provider's output, computed from its own methodology (float-adjusted market cap, capping rules, buffer zones). OpenIM **records** the constituent and weight; it does not re-run the provider's methodology — consistent with referencing FIBO and external standards rather than reinventing them.
- A corporate action on a constituent (a split, a merger) can trigger an off-cycle weight change; `inclusion_event = corporate_action` distinguishes it from a scheduled rebalance.
- PB-09 is the public-markets counterpart of PM-12 Benchmark Cross-Reference: PB-09 is the *constituents* of a replicable index; PM-12 is the *mapping* of a private fund into a non-replicable peer universe. Both specialise E-10, on opposite sides of the replicable / non-replicable line.
- The sum of `index_weight` across an index's currently-effective constituents is 1.0 — a validation invariant.

## Out of scope

- The index header — what the index is, its provider, its methodology — that is E-10 Benchmark / Index, which PB-09 specialises; PB-09 is the constituent sub-structure E-10 leaves to the pack.
- The provider's weighting methodology — float-adjustment, capping, buffer zones — OpenIM *records* the resulting weight, it does not re-run the provider's methodology.
- The mapping of a private fund into a non-replicable peer universe — that is PM-12 Benchmark Cross-Reference, the opposite side of the replicable / non-replicable line.
- The constituent instrument itself — that is PB-01 Listed Equity or PB-02 Debt Instrument, referenced through `instrument_id`.

## Owned and consumed by

- **Owned by:** SD-13.5 Benchmark & Index Data Management.
- **Populated via:** SD-13.4 Market & Reference Data Management (index-provider constituent feeds).
- **Consumed by:** SD-09.2 Performance Attribution, SD-09.4 Benchmark Management, SD-05.1 Portfolio Construction, SD-05.7 Model Portfolio & Sleeve Management, SD-07.4 Concentration & Exposure Risk (active-weight vs index).

## Open extensions

- The relationship between PB-09 and PB-01 / PB-02 for constituent-level look-through of index exposure.
- The pending-rebalance state — announced future composition before its effective date.
- Multi-currency and total-return / price-return index variants on the same constituent set.
