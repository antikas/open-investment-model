# PM-12 — Benchmark Cross-Reference

The mapping between an investor's own funds and the external benchmark and peer-universe identifiers used to evaluate them.

**Specialises:** E-10 Benchmark / Index. E-10 is the benchmark *data* — what a benchmark is and (for an index) what is in it. PM-12 is the *mapping* — how an investor's own fund locates itself inside an external provider's private-markets peer universe.

## Why it exists

Private-markets performance is meaningless without a comparison, and the comparison is a peer universe a provider defines — Cambridge Associates, Burgiss / MSCI, Preqin — not a constituent index the investor can replicate. "How does this fund rank against its vintage and strategy peers?" can only be answered if the investor's `fund_id` is mapped to the provider's identifier for the same fund or peer group. PM-12 is that join.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `cross_reference_id` | varchar | Primary key. |
| `fund_id` | varchar (FK → PM-01) | The investor's fund the cross-reference maps. |
| `benchmark_id` | varchar (FK → E-10) | The benchmark / peer universe (an E-10 record of kind `private_peer_universe`). |
| `provider` | varchar | The benchmark provider — Cambridge Associates, Burgiss / MSCI, Preqin. |
| `provider_fund_id` | varchar | The provider's own identifier for the fund or peer group. |
| `asset_class` | varchar (FK → E-09) | For strategy-level peer universes. |
| `vintage_year` | int | For vintage-cohort peer universes. |

## Notes

- A single fund may carry several cross-reference rows — one per provider, and one per peer-universe type (a vintage benchmark and a strategy benchmark are different comparisons).
- The non-trivial resolution case is a fund whose strategy or vintage classification is ambiguous — which peer group does a growth-equity fund with a buyout tilt belong to — resolved through the same steward review the masters use.

## Out of scope

- The benchmark *data* itself — what a benchmark is, its provider, its methodology — that is E-10 Benchmark / Index, which PM-12 specialises; PM-12 is the mapping, not the benchmark.
- The constituents of a replicable market index — that is PB-09 Index Constituent; PM-12 maps a fund into a non-replicable peer universe, the opposite side of the replicable / non-replicable line.
- The investor's fund being mapped — that is PM-01 Fund & Vehicle, referenced through `fund_id`.
- The named vintage / strategy / geography peer cohorts a fund is compared against — a peer-group sub-structure named as an open extension.

## Owned and consumed by

- **Owned by:** SD-13.5 Benchmark & Index Data Management.
- **Consumed by:** SD-09.2 Performance Attribution, SD-09.4 Benchmark Management, SD-09.8 Private-Markets Performance Analytics (vintage benchmarking, PME).

## Open extensions

- A peer-group sub-structure — the named vintage / strategy / geography cohorts a fund is compared against.
- The relationship between PM-12 and E-10 made fully explicit — the mapping versus the benchmark data.
