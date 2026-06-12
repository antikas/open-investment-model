# E-09 — Asset Class

The asset-class taxonomy — the reference structure that classifies what an institutional investor invests in, across public and private markets.

## Purpose

An asset-class-agnostic institutional investor allocates across a wide span of asset classes, each with different data characteristics, valuation conventions, liquidity profiles and operating mechanics. The Asset Class entity is the controlled taxonomy those distinctions hang from. It is referenced by Instrument / Asset (E-02), by Portfolio / Mandate (E-03), and by the strategy classification (E-11 / E-12), and it is a primary slicing dimension for allocation, exposure and performance reporting.

## The taxonomy

A three-level structure — asset class → strategy → sub-strategy:

| Asset class | Markets | Example strategies |
|---|---|---|
| Public Equities | Public | Developed markets, emerging markets |
| Fixed Income | Public | Government, credit, securitised |
| Cash & Money Markets | Public | Treasury bills, commercial paper, money-market funds, deposits |
| Private Equity | Private | Buyout, growth equity, venture capital |
| Private Credit | Private | Direct lending, mezzanine, distressed, special situations |
| Real Estate | Private | Core, core-plus, value-add, opportunistic |
| Infrastructure | Private | Core, core-plus, value-add; greenfield / brownfield |
| Natural Resources / Commodities | Both | Direct timberland, farmland, energy and mining assets (private); exchange-traded commodities and energy (public) |
| Hedge Funds / Active Strategies | Public | Macro, systematic, market-neutral, event-driven, hedged equity |

These nine classes are the asset-class spine the OpenIM service-domain model is checked against under the asset-class balance review — E-09 and the capability model are kept reconciled to one taxonomy.

- **Cash & money markets** is a discrete class — a governed asset-owner allocation segment, not a residual of fixed income.
- **Natural resources / commodities** spans both markets: directly-held timberland, farmland and mining assets are private; exchange-traded commodities and energy are among the most liquid public markets. The class is therefore tagged `both`, not `private`.
- **Secondaries, co-investment and fund-of-funds** are *transaction types* and structuring choices over these classes — how an exposure is acquired or wrapped — not asset classes in their own right. They are modelled as such in the service-domain model and are not E-09 entries.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `asset_class_key` | int | Primary key. |
| `asset_class_code` | varchar | The asset-class code. |
| `asset_class_label` | varchar | The display label. |
| `strategy_code` | varchar | The strategy within the asset class. |
| `sub_strategy_code` | varchar | The sub-strategy, where applicable. |
| `markets` | varchar | `public` / `private` / `both` — the asset class's dominant market structure. `both` is used where a class is genuinely traded in both (e.g. natural resources / commodities), pairing with the `BOTH` applicability tag on the service-domain model. |
| `effective_from` | date | When this taxonomy entry became valid. |
| `effective_to` | date | When it was retired; null while active. |

## Notes

- The **integer surrogate `asset_class_key` is the primary key and the FK target.** Entities that reference an asset class — Instrument / Asset (E-02), Portfolio / Mandate (E-03) — carry `asset_class` as an integer FK to `asset_class_key`, so the reference type matches the key type. `asset_class_code` is the stable human-readable natural key (e.g. `PUB_EQ`), used in reporting and as the durable cross-effective-dating handle; it is not the FK target. The surrogate key is preferred as the join key because it is the effective-dated identity that survives a code relabelling.
- Effective-dated, like all OpenIM reference data — a strategy classification that is renamed or retired must not corrupt historical reporting.
- The `markets` attribute is the model's single cleanest public-versus-private split, and it pairs with the `PUB` / `PRIV` / `BOTH` applicability tagging on the service-domain model.
- **Orthogonal to the specialisation packs.** E-09 is the *asset-class* axis — *what* the investor is exposed to. The entity model's specialisation packs (`private-markets`, `public-markets`, `derivatives`, `real-assets`) are the *form-of-holding* axis — *how* the exposure is held and instrumented. The two are orthogonal and do not mirror each other: a private-equity exposure (an E-09 class) is held through the fund route (private-markets pack) or directly; an interest-rate swap (derivatives pack) references a fixed-income exposure (an E-09 class). E-09 is the single asset-class spine both the entity model and the service-domain model reconcile to; the packs are a coarser, orthogonal structuring — there are nine asset classes and four packs, and that is not a mismatch.

## Out of scope

- The classification of an *individual* instrument, portfolio or mandate against this taxonomy — that is E-11 Classification Type & Value applying E-09, not E-09 itself.
- The strategy / style classifier history for managers and funds — E-12 Classification History.
- Secondaries, co-investment and fund-of-funds — these are transaction types and structuring choices over the asset classes, not asset classes, and are not E-09 entries.

## Owned and consumed by

- **Owned by:** SD-13.4 Market & Reference Data Management.
- **Consumed by:** E-02 Instrument / Asset, E-03 Portfolio / Mandate, SD-01.4 Strategic Asset Allocation, SD-09 Performance & Analytics, and exposure reporting across BD-07.

## Open extensions

- Reconciliation of the strategy / sub-strategy levels against the strategy classifier in E-11.
- Alignment notes where an asset-class boundary is genuinely contested (e.g. infrastructure debt straddling private credit and infrastructure).
