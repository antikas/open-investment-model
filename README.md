# OpenIM: Open Investment Model

> An open, MIT-licensed, vendor-neutral **reference model for institutional investment management**: a service-domain decomposition of the buy-side firm plus a canonical entity model, designed to be read and used by people, architecture tools and AI agents. It is to the buy-side what BIAN is to retail banking. It sits above FIBO (which it uses for instrument and legal-entity semantics), is complementary to ISDA CDM (which models the transaction layer below it), and is the maintained, vendor-neutral successor in spirit to the archived FINOS `glue` project.

## Why OpenIM exists

AI agents are becoming a real channel into the investment firm, and an agent can only operate a firm it has a model of. The architect designing one needs that model just as much. OpenIM is that model: an open, vendor-neutral map of what a buy-side firm does and what it knows, its service domains and its canonical entities, built to be read and operated by agents.

The buy-side has never had one. Asset managers, sovereign wealth funds, LP allocators and institutional investors run on proprietary vendor capability maps and consultancy operating-model frameworks, with no open, maintained, vendor-neutral, agent-native reference model of what the firm *is* in circulation. Retail banking has had BIAN for years; the buy-side has had nothing to reach for.

The precise gap: there is no current, open, vendor-neutral, agent-native service-domain and master-data model for institutional investment management. OpenIM fills it. How it sits alongside FIBO, ISDA CDM and the other adjacent standards is covered below, and in full in [PRIOR-ART.md](PRIOR-ART.md).

### What a model of the firm makes answerable

The model, and the figures of record produced on top of it, exist for the questions a firm runs on. Today the answers are stitched together by hand across eight to twelve systems. A shared model makes them answerable from one canonical map, with the lineage intact:

- *What is this fund's NAV per unit, and exactly what moved it since the last strike?*
- *What is our AUM, by strategy and by asset class?*
- *What are the investor flows, and the management and performance fee accruals?*
- *What is our counterparty exposure and collateral coverage on the OTC sleeve?*
- *What is the cross-asset look-through exposure?*
- *Where do two systems disagree on a position or a mark, and which is right?*
- *Is this the same counterparty as that one, resolved to a single legal entity across every feed?*

None of these is exotic; every manager asks them daily. The work is in the answer, which lives in fragments across systems that do not share a model. OpenIM supplies the shared map. What you build on top of it, how you compute figures of record, and how you govern action remain implementation choices.

## What OpenIM is

One reference model with two connected parts ([`model/`](model/README.md)):

- **[Service domains](model/service-domains/INDEX.md)**: *what the firm does.* A decomposition of the buy-side firm into **17 Business Domains and 171 Service Domains**, each a discrete, non-overlapping unit of business capability, decomposed three levels deep: every Service Domain enumerates its Service Operations, roughly 1,030 across the model. The service-domain decomposition is the OpenIM equivalent of BIAN's Service Landscape, and the part with no existing open equivalent.
- **[Entities](model/entities/INDEX.md)**: *what the firm knows.* A canonical data model of **86 entities**: a **generalised core of 38** (Legal Entity, Instrument / Asset, Portfolio / Mandate, Holding / Position, Transaction, Cash Flow, Valuation, the reference entities and the risk entities, true of every institutional investor) plus five **specialisation packs** that specialise the core by the form a holding or operation takes: public-markets (11 entities), fund-operations (12), private-markets (15), derivatives (5) and real-assets (5). It serves the firm that *issues* funds (UCITS, mutual funds, hedge funds) as fully as the one that *allocates* into them (sovereign and pension funds, insurers), each activating the subset its mandate needs; entity resolution is first-class (acute in private markets, useful across any cross-feed reconciliation); aligned to FIBO.

OpenIM does not prescribe or endorse a product, runtime, agent framework, data platform or implementation. The model is open for anyone to adopt, adapt and build on under the MIT licence.

The canonical machine-readable identity for the project is [`metadata/openim.json`](metadata/openim.json).

## The model at a glance

**17 Business Domains, 171 Service Domains, ~1,030 Service Operations.** Office tags: Front / Middle / Back / Cross-cutting / Commercial.

| # | Business Domain | Office | Service domains |
|---|---|---|---|
| BD-01 | Investment Strategy & Allocation | Front | 14 |
| BD-02 | Securities Research & Selection | Front | 8 |
| BD-03 | Manager & Fund Investment | Front | 9 |
| BD-04 | Direct & Co-Investment | Front | 12 |
| BD-05 | Portfolio Management | Front | 13 |
| BD-06 | Trading & Execution | Front | 6 |
| BD-07 | Investment Risk | Middle | 8 |
| BD-08 | Valuation & Pricing | Middle | 6 |
| BD-09 | Performance & Analytics | Middle | 9 |
| BD-10 | Investment Compliance & Guideline Monitoring | Middle | 9 |
| BD-11 | Treasury, Cash & Collateral | Middle | 8 |
| BD-12 | Investment Operations & Servicing | Back | 17 |
| BD-13 | Investment Data & Reporting | Cross-cutting (data) | 12 |
| BD-14 | Enterprise Risk, Control & Assurance | Cross-cutting (corporate) | 9 |
| BD-15 | Distribution, Product & Client Management | Commercial | 16 |
| BD-16 | Enterprise Governance & Accountability | Cross-cutting (corporate) | 5 |
| BD-17 | Corporate Services & Resources | Cross-cutting (corporate) | 10 |

The canonical entity model has a **generalised core of 38 entities** (Legal Entity, Instrument / Asset, Portfolio / Mandate, Holding / Position, Transaction, Cash Flow, Valuation, Price & Market Data, the reference entities, the risk entities, the computed-result and metadata entities, the operational entities and the strategy entities), true of every institutional investor. On top of it sit five **specialisation packs**, organised by the form a holding or operation takes rather than by asset class: public-markets (11 entities: listed equity, debt, the full order-to-settlement trade lifecycle, corporate actions, income schedules, index constituents, securities lending and proxy voting), fund-operations (12: the fund as an issued product, the share or unit class, the investor unitholding, the dealing order, the income distribution event, the computed fee figure of record, the issued investor tax statement, the service-provider appointment record, the omnibus account, and the ETF primary-market path of the creation/redemption order, the daily portfolio composition file and the authorised-participant agreement), the private-markets pack covering the private / illiquid / no-universal-ID shape (15: deals, funds, GPs, commitments, capital calls, distributions, fund terms, investor capital accounts, directly-originated private loans), derivatives (5) and real-assets (5), for 48 specialisation entities, 86 with the core. Issuer, counterparty, manager and custodian are *roles* of the one Legal Entity master, not separate masters. That is the FIBO-faithful shape. The model serves the firm that *issues* funds (a UCITS or mutual-fund manager, a hedge fund) as fully as the sovereign, pension or insurance *allocator* that invests in them, each lighting up the subset its mandate needs. Every master carries an internal golden key, an alias set and an external-identifier map, because private markets have no universal identifier and a model that assumes one breaks the moment it meets a GP report, and the same resolution carries any reconciliation across custodian, administrator and counterparty feeds.

Asset-class agnostic: public equities, fixed income, cash and money markets, private equity, private credit, real estate, infrastructure, natural resources and commodities, and hedge funds and active strategies, invested through external managers and funds, directly, and through co-investments and secondaries (which are transaction types over the asset classes, not asset classes in their own right).

See [`model/service-domains/INDEX.md`](model/service-domains/INDEX.md) for the full decomposition, [`model/entities/INDEX.md`](model/entities/INDEX.md) for the entity model, the [glossary](model/glossary.md) for the vocabulary, and [`model/diagrams/`](model/diagrams/INDEX.md) for the visual companions.

## Quickstart

The model is plain Markdown, readable on GitHub without installing anything. Start at [`model/service-domains/INDEX.md`](model/service-domains/INDEX.md) (what the firm does) and [`model/entities/INDEX.md`](model/entities/INDEX.md) (what the firm knows); the [glossary](model/glossary.md) defines the investment-management vocabulary, and [`model/diagrams/`](model/diagrams/INDEX.md) holds the diagrams.

To run the model's structural-integrity validator locally (counts, identifiers, link resolution, cross-file count agreement), you need Python 3.9 or later, standard library only:

```sh
git clone https://github.com/antikas/open-investment-model.git
cd open-investment-model
python tools/openim-validate/validate.py
```

Exit `0` means the model is structurally clean. What it checks: [`tools/openim-validate/README.md`](tools/openim-validate/README.md). Machine-readable exports for architecture tools, graphs and AI retrieval are published under [`exports/`](exports/).

## How OpenIM relates to existing standards

OpenIM is a *layer*, and it is honest about which layer. It does not replace FIBO or compete with ISDA CDM, and it is not a wire format.

```
  Service domains      OpenIM service-domain model       ← OpenIM (new)
  Master data          OpenIM canonical model:
                       funds, portfolios, mandates,
                       GP/LP, commitments, allocations,
                       entity resolution / golden keys   ← OpenIM (new)
  ──────────────────────────────────────────────────────────────────────────
  Transaction layer    ISDA CDM                          ← reuse
  Concept ontology     FIBO                              ← align to / build on
  Identifiers          LEI · FIGI · ISIN · Private CUSIP  ← reference / resolve across
  Wire / messaging     ISO 20022 · FIX · FpML            ← interop edge
  Reporting / perf     ILPA templates · GIPS             ← consume / conform to
  Governance           FINOS AI Governance Framework     ← align to
```

Your first question is probably "what about FIBO?" or "what about CDM?". It is answered in full in **[PRIOR-ART.md](PRIOR-ART.md)**. That document names every adjacent standard, states what it is, and explains the layer relationship. It is the project's credibility artefact; read it before forming a view. The entity-by-entity FIBO mapping is [`model/fibo-alignment.md`](model/fibo-alignment.md).

## What makes OpenIM different

1. **Service-domain-first.** A capability decomposition of the firm, not only a data model. It is the differentiator against the archived `glue`.
2. **Machine-consumable.** Plain-text source, deterministic validation and published machine-readable exports make the model usable by architecture tools, knowledge graphs, retrieval systems and AI agents without requiring a particular runtime.
3. **Private-markets master-data.** Explicit entity resolution and golden keys address the reality that private markets have no universal identifier. A model that assumes a shared identifier breaks the moment it meets a GP report.
4. **Vendor-neutral and maintained.** Open and maintainer-led (see [GOVERNANCE.md](GOVERNANCE.md)), MIT-licensed, tied to no vendor's platform. Vendor-dependence and abandonment were the failure mode of `glue`; OpenIM exists to avoid both.

## Declared scope

Stated plainly, so nobody over-reads the project:

- **The model is a reference model, not a design blueprint.** Like BIAN's Service Landscape, it decomposes a generic firm; an implementation activates the subset its mandate requires. The model is the union of capability; an implementation is a subset.
- **The model is implementation-neutral.** OpenIM does not define a preferred product, agent, protocol, data platform or operating architecture. Implementations may use all, part or none of it.
- **The public repository contains the model and model-derived exports.** It does not contain operational investment data or claim that a particular implementation is part of OpenIM.
- **Use is open.** Commercial and non-commercial implementations may adopt, adapt and extend OpenIM under the MIT licence without endorsement from the project.

## Repository layout

```
open-investment-model/
├── README.md                    This file
├── PRIOR-ART.md                 How OpenIM relates to BIAN, FIBO, CDM, glue, ILPA, GIPS, ...
├── CONTRIBUTING.md              How to contribute
├── CODE_OF_CONDUCT.md           Community standards
├── GOVERNANCE.md                How the project is governed
├── CITATION.cff                 Machine-readable citation metadata
├── LICENSE                      MIT
├── metadata/                    Canonical machine-readable project identity
├── model/                       OpenIM, the reference model
│   ├── README.md
│   ├── service-domains/         The 17 Business Domain / 171 Service Domain decomposition
│   ├── entities/                The canonical entity model: 38-entity core + five specialisation packs
│   ├── diagrams/                Layer stack, Business Domain map, conceptual ERD, asset-class × form-of-holding matrix
│   ├── glossary.md              Plain-English definitions of the vocabulary the model uses
│   ├── ownership-map.md         Which Service Domain owns which entity
│   └── fibo-alignment.md        The entity-by-entity FIBO alignment
└── tools/
    ├── openim-validate/         Structural-integrity validator for the model
    └── diagrams/                Generator for the rendered static-site view of the model
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute, [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards, and [GOVERNANCE.md](GOVERNANCE.md) for how the project is governed.

If you maintain or know of prior art OpenIM has not named in [PRIOR-ART.md](PRIOR-ART.md), that is among the most valuable feedback the project can receive.

## Licence

MIT. See [LICENSE](LICENSE).

## Author

[Georgios Antikatzidis](https://github.com/antikas), enterprise architect, financial services. OpenIM is built from two and a half decades of practitioner experience across trading systems, data platforms and enterprise architecture in financial services.
