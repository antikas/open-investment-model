# OpenIM — Open Investment Model

> An open, MIT-licensed, vendor-neutral **reference model for institutional investment management** — a service-domain decomposition of the buy-side firm plus a canonical entity model, designed to be consumed by AI agents, with a working agent-native reference implementation. It is to the buy-side what BIAN is to retail banking. It sits above FIBO (which it uses for instrument and legal-entity semantics), is complementary to ISDA CDM (which models the transaction layer below it), and is the maintained, vendor-neutral, agent-native successor in spirit to the archived FINOS `glue` project.

## Why OpenIM exists

AI agents are becoming a real channel into the investment firm, and an agent can only operate a firm it has a model of. The architect designing one needs that model just as much. Both need a shared map of what the firm does and what it knows: its service domains and its canonical entities. A bank-building agent can reach for BIAN; a buy-side agent has had nothing to reach for. OpenIM is that map, and the need for it is sharper now than it would have been five years ago.

Retail and commercial banking has BIAN — an open service-domain reference model that decomposes a bank into discrete, non-overlapping units of capability. The buy-side lacks an open, vendor-neutral equivalent. Asset managers, sovereign wealth funds, LP allocators and institutional investors are served by proprietary vendor capability maps and by consultancy operating-model frameworks, but no *open, maintained, vendor-neutral, agent-native* reference model of what the firm *is* — its service domains, its canonical entities, the operations it performs — is in current circulation. The adjacent standards each solve a different problem (the full mapping is in [PRIOR-ART.md](PRIOR-ART.md)):

- **FIBO** is an ontology of the *things* of financial business — instruments, legal entities, securities, and (more than is commonly assumed) funds and the GP/LP partnership roles. It models funds and partnerships as legal and structural nouns, but not the investment lifecycle above them: commitments, capital calls, distributions, NAV-as-event, the portfolio-mandate and allocation layer, or the risk-operating layer.
- **ISDA CDM** models the *transaction* layer — trades and their lifecycle — not the portfolio, fund or mandate above it.
- **ILPA templates** standardise the *format* of GP-to-LP reporting, not the model beneath it.
- **GIPS** standardises *performance presentation*. **ISO 20022 / FIX / FpML** are *wire formats*.
- **FINOS `glue`** — the one open buy-side data model — was archived in 2023, was a data model rather than a service-domain decomposition, and predates the agent era.

So the precise, defensible gap: **there is no current, open, vendor-neutral, agent-native service-domain and master-data model for institutional investment management.** OpenIM fills it.

## What OpenIM is

Two interlocking layers, in one repository.

### 1. The model — [`model/`](model/README.md)

The reference model itself. Two halves:

- **[Service domains](model/service-domains/INDEX.md)** — *what the firm does.* A decomposition of the buy-side firm into **17 Business Domains and 171 Service Domains**, each a discrete, non-overlapping unit of business capability, decomposed three levels deep: every Service Domain enumerates its Service Operations — roughly 1,030 across the model. This is the OpenIM equivalent of BIAN's Service Landscape, and the part with no existing open equivalent.
- **[Entities](model/entities/INDEX.md)** — *what the firm knows.* A canonical data model of **73 entities**: a **generalised core of 38** (Legal Entity, Instrument / Asset, Portfolio / Mandate, Holding / Position, Transaction, Cash Flow, Valuation, the reference entities and the risk entities — true of every institutional investor) plus four **specialisation packs** that specialise the core by the form a holding takes — private-markets (14 entities), public-markets (11), derivatives (5) and real-assets (5). Built for the no-universal-identifier reality of private markets; aligned to FIBO.

### 2. agentINVEST — the reference implementation — [`reference/`](reference/README.md)

An agent-native implementation built on the model: a typed agent-tool catalogue, an MCP server, an OpenAPI surface, a canonical data layer, an operator UI, and audit and governance binding — the model made executable and agent-consumable.

Build status, stated plainly:

- **Built** — the substrate: a durable-execution engine, a typed tool catalogue, the canonical dbt data layer, MCP and OpenAPI ingress, an operator UI, and a hash-chained audit journal.
- **Built and audited end to end** — the NAV-strike workflow: an LLM planning loop, a human approval gate, and a journaled durable workflow, with crash-replay proven.
- **In build** — the reconciliation capability: the deterministic dual-pipeline engine and the append-only break store are complete and audited; the propose-only AI stage over unexplained breaks is designed but not built; the state-mutating correction workflow is not yet built.

The whole implementation — the durable-execution substrate, the typed tool catalogue, the canonical data layer, the orchestrator and its workflows, and the agent ingress — is drawn in the [solution-architecture diagram](reference/docs/architecture/agentinvest-solution-architecture.svg), with a [layer-by-layer walkthrough](reference/docs/architecture/agentinvest-solution-architecture.md).

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

The canonical entity model has a **generalised core of 38 entities** — Legal Entity, Instrument / Asset, Portfolio / Mandate, Holding / Position, Transaction, Cash Flow, Valuation, Price & Market Data, the reference entities, the risk entities, the computed-result and metadata entities, the operational entities and the strategy entities — true of every institutional investor. On top of it sit four **specialisation packs**, organised by the form a holding takes rather than by asset class: the private-markets pack covering the private / illiquid / no-universal-ID shape (14 entities — funds, GPs, commitments, capital calls, distributions, fund terms, investor capital accounts, directly-originated private loans), plus public-markets (11), derivatives (5) and real-assets (5) packs — 35 specialisation entities, 73 with the core. Issuer, counterparty, manager and custodian are *roles* of the one Legal Entity master, not separate masters — the FIBO-faithful shape. Every master carries an internal golden key, an alias set and an external-identifier map, because private markets have no universal identifier and a model that assumes one breaks the moment it meets a GP report.

Asset-class agnostic: public equities, fixed income, cash and money markets, private equity, private credit, real estate, infrastructure, natural resources and commodities, and hedge funds and active strategies — invested through external managers and funds, directly, and through co-investments and secondaries (which are transaction types over the asset classes, not asset classes in their own right).

See [`model/service-domains/INDEX.md`](model/service-domains/INDEX.md) for the full decomposition, [`model/entities/INDEX.md`](model/entities/INDEX.md) for the entity model, the [glossary](model/glossary.md) for the vocabulary, and [`model/diagrams/`](model/diagrams/INDEX.md) for the visual companions.

## Quickstart

Three tiers, in increasing depth. Tier 1 needs only Python; Tier 3 is the full agent demo.

### Tier 1 — explore the model and check its integrity

The model is plain Markdown — readable on GitHub without installing anything. Start at [`model/service-domains/INDEX.md`](model/service-domains/INDEX.md) (what the firm does) and [`model/entities/INDEX.md`](model/entities/INDEX.md) (what the firm knows); the [glossary](model/glossary.md) defines the investment-management vocabulary, and [`model/diagrams/`](model/diagrams/INDEX.md) holds the diagrams.

To run the model's structural-integrity validator locally — counts, identifiers, link resolution, cross-file count agreement — you need Python 3.9 or later, standard library only:

```sh
git clone https://github.com/antikas/open-investment-model.git
cd open-investment-model
python tools/openim-validate/validate.py
```

Exit `0` means the model is structurally clean. What it checks: [`tools/openim-validate/README.md`](tools/openim-validate/README.md).

### Tier 2 — build the canonical data layer locally

The agentINVEST canonical data layer is a dbt project on an in-process DuckDB backend — synthetic seed data, no external services, no credentials. Prerequisites: Node 22+, [pnpm](https://pnpm.io) and [uv](https://docs.astral.sh/uv/); on Windows the Python/dbt toolchain runs inside WSL2.

```sh
cd reference/python
uv sync --group dbt        # one-time: create the Python env with the dbt toolchain (inside WSL2 on Windows)
cd ..
pnpm dbt:build             # dbt build — seed + run + test against a local DuckDB file
```

A green run ends with dbt's `PASS=… ERROR=0` summary. The full runbook — where the DuckDB file lands, recovery from a stale database, the dev-to-prod path — is [`reference/dbt/README.md`](reference/dbt/README.md).

### Tier 3 — run the full agentINVEST demo

The end-to-end demo — the durable-execution substrate, the typed tool surface, the NAV-strike workflow with its LLM planning loop and human approval gate, the operator UI — additionally needs the Restate dev server, the pnpm workspace installed, and an Anthropic API key. The setup and run sequence is in [`reference/README.md`](reference/README.md).

## How OpenIM relates to existing standards

OpenIM is a *layer*, and it is honest about which layer. It does not replace FIBO; it does not compete with ISDA CDM; it is not a wire format.

```
  Agent channel        MCP server / typed tool surface   ← OpenIM defines (agentINVEST)
  ──────────────────────────────────────────────────────────────────────────
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

Your first question is probably "what about FIBO?" or "what about CDM?" — it is answered in full in **[PRIOR-ART.md](PRIOR-ART.md)**. That document names every adjacent standard, states what it is, and explains the layer relationship. It is the project's credibility artefact; read it before forming a view. The entity-by-entity FIBO mapping is [`model/fibo-alignment.md`](model/fibo-alignment.md).

## What makes OpenIM different

1. **Service-domain-first.** A capability decomposition of the firm, not only a data model. This is the differentiator against the archived `glue`.
2. **Agent-native.** A typed tool surface, an MCP server, and audit binding as first-class concerns — the buy-side parallel to the AI-native bank reference architectures.
3. **Private-markets master-data, made runnable.** Explicit entity resolution and golden keys for the reality that private markets have no universal identifier — a model that assumes a shared identifier breaks the moment it meets a GP report. Not only modelled: implemented and demonstrated in agentINVEST as a deterministic three-tier resolver with golden-record survivorship, scored by a labelled evaluation that holds **zero mis-merges**, with no model in the of-record decision. See [the entity-resolution capability](reference/docs/capabilities/entity-resolution.md).
4. **Vendor-neutral and maintained.** Open and maintainer-led (see [GOVERNANCE.md](GOVERNANCE.md)), MIT-licensed, tied to no vendor's platform. This is the failure mode of `glue` that OpenIM exists to avoid.

## Declared scope

Stated plainly, so nobody over-reads the project:

- **The model is a reference model, not a design blueprint.** Like BIAN's Service Landscape, it decomposes a generic firm; an implementation activates the subset its mandate requires. The model is the union of capability; an implementation is a subset.
- **The reference implementation is demonstration-grade.** agentINVEST exists to prove the model is executable and agent-consumable, not to be deployed as production software.
- **All data is synthetic.** No real fund, portfolio, position or counterparty data appears anywhere in this repository.
- **The autonomy ceiling is supervised.** Every state mutation passes a human approval gate. The LLM plans, drafts and explains; it never computes a figure of record — every figure of record comes from the deterministic data layer. That is the deterministic spine: the model stays out of the truth path.

## Repository layout

```
open-investment-model/
├── README.md                    This file
├── PRIOR-ART.md                 How OpenIM relates to BIAN, FIBO, CDM, glue, ILPA, GIPS, ...
├── CONTRIBUTING.md              How to contribute
├── CODE_OF_CONDUCT.md           Community standards
├── GOVERNANCE.md                How the project is governed
├── LICENSE                      MIT
├── model/                       OpenIM — the reference model
│   ├── README.md
│   ├── service-domains/         The 17 Business Domain / 171 Service Domain decomposition
│   ├── entities/                The canonical entity model — 38-entity core + four specialisation packs
│   ├── diagrams/                Layer stack, Business Domain map, conceptual ERD, asset-class × form-of-holding matrix
│   ├── glossary.md              Plain-English definitions of the vocabulary the model uses
│   ├── ownership-map.md         Which Service Domain owns which entity
│   └── fibo-alignment.md        The entity-by-entity FIBO alignment
├── reference/                   agentINVEST — the agent-native reference implementation
│   └── README.md
└── tools/
    ├── openim-validate/         Structural-integrity validator for the model (Tier 1 above)
    └── diagrams/                Generator for the rendered static-site view of the model
```

## Status

Model version 0.1 — the service-domain decomposition and the canonical entity model are complete at this version. agentINVEST is in active build; its status is stated honestly under *What OpenIM is* above.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute, [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards, and [GOVERNANCE.md](GOVERNANCE.md) for how the project is governed.

If you maintain or know of prior art OpenIM has not named in [PRIOR-ART.md](PRIOR-ART.md), that is among the most valuable feedback the project can receive.

## Licence

MIT — see [LICENSE](LICENSE).

## Author

[Georgios Antikatzidis](https://github.com/antikas) — enterprise architect, financial services. OpenIM is built from two and a half decades of practitioner experience across trading systems, data platforms and enterprise architecture in financial services.
