# OpenIM — The Model

This directory holds the OpenIM model: the open, vendor-neutral reference model for institutional investment management. It has two interlocking halves.

## [`service-domains/`](service-domains/INDEX.md) — what the firm does

A service-domain decomposition of the buy-side firm — **17 Business Domains, 171 Service Domains**. Each Service Domain is a discrete, non-overlapping unit of business capability. This is the OpenIM equivalent of BIAN's Service Landscape, and it is the part of OpenIM with no existing open equivalent.

Start at [`service-domains/INDEX.md`](service-domains/INDEX.md).

## [`entities/`](entities/INDEX.md) — what the firm knows

The canonical data model — the *things* an institutional investor keeps records about. It has two layers:

- A **generalised core** (`entities/core/`, 38 entities) — Legal Entity, Instrument / Asset, Portfolio / Mandate, Holding / Position, Transaction, Cash Flow, Valuation, the reference entities, the risk entities, the computed-result and metadata entities, the operational entities and the strategy entities. True of every institutional investor, whatever it invests in.
- **Specialisation packs** (`entities/specialisations/`) — four packs that specialise the core by the form a holding takes (instrument family and access route), orthogonal to the asset-class taxonomy: private-markets (the private / illiquid / no-universal-ID shape — the fund route plus directly-originated private credit, 14 entities), public-markets (listed securities, 11), derivatives (the derivative instrument family, 5) and real-assets (directly-held physical assets, 5) — 35 specialisation entities, 73 with the core.

Designed for the no-universal-identifier reality of private markets, and aligned to FIBO for legal-entity and instrument semantics.

Start at [`entities/INDEX.md`](entities/INDEX.md).

## How the two halves interlock

The service-domain model decomposes *capability*; the entity model decomposes *data*. They join through ownership: each Service Domain owns a small set of entities (it is their authoritative source) and consumes others. The full ownership map is in [`ownership-map.md`](ownership-map.md).

## Positioning

The model is a **reference model, not a standard** — a reference framework, in BIAN's own language, not a design blueprint. It sits above FIBO, is complementary to ISDA CDM, and is the maintained, vendor-neutral, service-domain-first successor in spirit to the archived FINOS `glue` project. The full positioning is in [`../PRIOR-ART.md`](../PRIOR-ART.md).

## Reader's references

- [`glossary.md`](glossary.md) — plain-English definitions of the investment-management vocabulary the model uses (LP/GP, capital call, distribution, J-curve, IRR / TVPI / DPI / RVPI / MOIC / PME, four-lens NAV, IBOR / ABOR, LEI / FIGI / ISIN, golden key, side letter, MFN, waterfall, hurdle, carry, and the rest). Read first if a term is unfamiliar.
- [`diagrams/`](diagrams/INDEX.md) — the visual companion to the model: a layer stack of OpenIM's position in the standards landscape, the Business Domain map, and the conceptual ERD of the core entities.
