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
- **Orthogonal to the specialisation packs.** E-09 is the *asset-class* axis — *what* the investor is exposed to. The entity model's specialisation packs (`public-markets`, `fund-operations`, `private-markets`, `derivatives`, `real-assets`) are the *form-of-holding or form-of-operation* axis — *how* the exposure is held, instrumented, or issued. The two are orthogonal and do not mirror each other: a private-equity exposure (an E-09 class) is held through the fund route (private-markets pack) or directly; an interest-rate swap (derivatives pack) references a fixed-income exposure (an E-09 class); an institution that issues funds across any asset class inhabits the fund-operations pack. E-09 is the single asset-class spine both the entity model and the service-domain model reconcile to; the packs are a coarser, orthogonal structuring — there are nine asset classes and five packs, and that is not a mismatch.
- **Taxonomy note — Hedge Funds / Active Strategies `markets = Public`.** This tag was set deliberately, to agree with SD-09.9 and SD-05.9, and is defended, not settled by default: institutional allocators commonly bucket hedge funds inside an "alternatives" sleeve, not a public-markets one. Reviewed against external taxonomy practice: Preqin's asset-class taxonomy groups hedge funds together with private equity, real estate, infrastructure and private debt under one "alternative assets" heading; GIPS's *Guidance Statement on Alternative Investment Strategies and Structures* treats hedge funds, for GIPS purposes, as "limited distribution pooled funds" alongside private equity and real estate, and permits side-pocket and less-frequent-valuation treatment on that basis; AIMA describes its own remit as covering "the more liquid side of alternative investing" — still inside the alternative-investment family, distinguished from private equity/real estate by degree, not by being outside it; and the CAIA curriculum needs a distinct term, "liquid alternatives," for the '40 Act / UCITS-wrapped subset of hedge-fund strategies that are publicly distributed and redeemable — implying the un-wrapped hedge fund's default distribution profile is not itself treated as public. ILPA, checked as a candidate source, does not classify hedge funds at all — its Reporting Template and Performance Template are scoped to closed-end private funds; that silence is consistent with hedge funds sitting outside the private-fund LP-reporting family ILPA governs, not inside it. Weighed against that evidence, the tag holds: `markets` in this taxonomy is an **instrument/holding-tradability axis**, not a fund-vehicle-distribution axis — the same axis that puts directly-held timberland and farmland in `Private` while exchange-traded commodities and energy sit in `Public`, above. On that axis, hedge-fund strategies (per HFR's own hedge-fund strategy-classification system — Equity Hedge, Event-Driven, Macro, Relative Value) are built from continuously-priced public-market instruments — listed and OTC equities, fixed income, currencies and derivatives — not the privately-negotiated, non-traded ownership stakes that make private equity and direct real estate `Private`. The allocator-alternatives view is real, but it is describing a *different*, already-modelled axis: the fund vehicle's distribution and redemption terms (lock-ups, gates, side pockets, limited-distribution-pooled-fund treatment) — which OpenIM already carries on the orthogonal form-of-holding axis (the asset-class × form-of-holding matrix's hedge-fund-of-funds cell routes a hedge-fund-class exposure through the private-markets closed-end-fund-vehicle form — PM-01/PM-06/PM-09/PM-13 — regardless of the class's `Public` tag; see `model/diagrams/04-asset-class-form-of-holding-matrix.md`). Retagging `markets` to satisfy the vehicle-liquidity view would conflate the two axes the model deliberately keeps separate.

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
