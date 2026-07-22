# Prior Art

OpenIM does not exist in a vacuum. This document names the standards, models, and projects adjacent to OpenIM, states honestly what each one is, and explains where OpenIM sits in relation to it. If you are evaluating OpenIM, read this first — your first question is almost certainly answered here.

The short version: **OpenIM is a service-domain and master-data reference model for the buy-side firm.** Every standard below is either a different layer, a different type of artefact, a different industry, or no longer maintained. None of them is a current, open, agent-native service-domain decomposition of an institutional investment manager. That is the gap OpenIM fills.

## The layer picture

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

## What OpenIM relates to, and how

### BIAN — Banking Industry Architecture Network — *precedent, not competitor*

BIAN is an open service-domain reference model for **retail and commercial banking**: ~7 business areas, ~36 business domains, ~280+ service domains, each an atomic, non-overlapping unit of business capability. It is a reference framework for organising capabilities, explicitly not a design blueprint for any particular bank.

OpenIM is, deliberately, "BIAN for the buy-side." BIAN is the structural precedent OpenIM borrows its form from. BIAN does not touch institutional investing — there is no asset-management or allocator content in it. OpenIM does not compete with BIAN; it occupies the equivalent position for a different industry.

### FIBO — Financial Industry Business Ontology — *a lower layer; OpenIM builds on it*

FIBO (EDM Council, standardised through OMG; MIT-licensed) is a formal **ontology** of the *things* of financial business — instruments, legal entities, securities, derivatives, indices. It answers "what is a credit default swap, an equity, a legal entity?"

FIBO is **not a competitor and OpenIM does not replace it.** FIBO is a different layer. FIBO's coverage is rich on the *nouns* of financial business — legal entities (its strongest area, with a full LEI model), instruments, securities, market indices, and — more than is commonly assumed — funds, collective investment vehicles and the GP/LP partnership roles. What FIBO does **not** model is the investment manager's operating layer: the private-markets investment lifecycle (commitments, capital calls, distributions, capital accounts, NAV as a valuation event), the portfolio-mandate and allocation layer, the classification and entity-resolution machinery, and the risk-operating layer (limits, scenarios, breaches, measurements). It also models real estate only as a securitised instrument, never as a directly-held operating asset. OpenIM **uses FIBO for instrument and legal-entity semantics where FIBO already covers them** — the alignment is mapped concept-by-concept in [fibo-alignment.md](model/fibo-alignment.md) — and adds the buy-side operating and master-data layer FIBO does not model. FIBO is OpenIM's most important alignment dependency.

### ISDA CDM — Common Domain Model — *complementary; the transaction layer below OpenIM*

ISDA CDM (now a FINOS project) is a machine-readable, machine-executable model of financial products, the trades in them, and the lifecycle events of those trades — execution, confirmation, settlement, margin, collateral.

CDM models the **transaction grain**. It does not model the portfolio, the fund, the mandate, the LP commitment, or the allocation decision. OpenIM's portfolio and holdings service domains reference CDM for the trade and lifecycle representation rather than re-inventing it. OpenIM models the portfolio, fund, mandate and allocation layer *above* CDM's transaction layer.

### FINOS `glue` — buy-side enterprise data model — *prior art, named honestly; archived*

`glue` was an enterprise data model for the buy-side — Party, Business Relationship, Investment Strategy, Instruments, Portfolios — contributed to FINOS by EPAM Systems in 2020.

This is the one piece of genuine buy-side prior art, and OpenIM names it openly. `glue` matters because it proves the *idea* of an open buy-side model is not novel. But: `glue` is **archived** — the FINOS repository has been read-only since 2023. It was a *data model*, not a *service-domain decomposition* — it modelled what data the buy-side stores, not what service domains a buy-side firm operates. It carried a single-vendor lineage (EPAM's "Wave" ecosystem) rather than being vendor-neutral by design. And it predates the agent era entirely.

OpenIM is, in spirit, the maintained, vendor-neutral, service-domain-first, agent-native successor to what `glue` attempted. Pretending `glue` never existed would be the dishonest move; citing it is the honest one.

### Quadra — a current, open buy-side effort converging independently — *the closest living adjacent work*

Where `glue` proves the idea is not novel, Quadra proves it is happening again, now, and independently. Quadra is a new open buy-side platform from Stuart Plane, the founder of Cadis and Matrix and a long-standing practitioner in buy-side enterprise data management and security mastering. It starts from an open, git-native data model with the operating engines built on top of it, and like OpenIM it treats that model as the foundation its agents run on, with the deterministic core kept out of the numbers-of-record.

Quadra is the closest current, credible, adjacent prior art OpenIM has found, and the convergence is the substance of the point. Two efforts, arrived at separately, have landed on the same core convictions: open and git-native, model-first, agent-native, an institutional operating layer that spans public and private markets, and entity resolution taken seriously rather than assumed away. Independent agreement of that kind is evidence the open buy-side model thesis is right, not a threat to it.

The difference is one of kind, not of camp. Quadra is a platform, a runnable system built to operate a firm. OpenIM is a vendor-neutral reference model, a service-domain and master-data decomposition published under MIT and meant to be read and built on by anyone, platforms included. A reference model and an implementing platform sit at different layers and can share a vocabulary rather than compete for one. Naming Quadra, and naming it as convergent rather than rival, is the honest posture.

### Open-source retail quant platforms — *a different scope, and a different kind of artefact*

A class of open-source projects assembles quantitative-finance libraries — portfolio optimisation, volatility modelling, backtesting, broker execution — into an end-to-end workflow for retail investors and independent quants. A current example is [`menonf/InvestmentManagement`](https://github.com/menonf/InvestmentManagement): a Python toolkit over SQL Server / Databricks that loads public market data, backtests strategies, constructs and executes portfolios, measures performance and risk, and adds an LLM layer for natural-language querying and strategy generation.

These are **code toolkits, not reference models**, and they cover the **public-markets front office** — data, signal, optimisation, execution — not the institutional middle and back office (fund accounting, NAV, capital calls, LP servicing, custody) and not private markets. Their security masters assume one clean public-market identifier per instrument, with no entity-resolution or golden-key layer. And where they reach for AI, the model sits in the decision path (strategy generation). OpenIM sits elsewhere on all three axes: a vendor-neutral service-domain and master-data **reference model** for the **institutional** buy-side across **public and private** markets, with the model kept out of the numbers-of-record by design.

### ILPA reporting templates — *consumed by OpenIM's LP service domains*

ILPA's quarterly reporting templates (the 2025 Reporting Template v2.0 and Performance Template) standardise the **format and field-level content** of GP-to-LP reporting in private equity. They standardise what a capital-call notice contains; they do not standardise the *identity* of the entities within it ("is this the same fund as last quarter?"). That identity and master-data gap is exactly OpenIM territory. OpenIM's private-markets service domains consume and produce ILPA-format reporting.

### GIPS — Global Investment Performance Standards — *domain rules OpenIM conforms to*

GIPS (CFA Institute) is a voluntary standard for **calculating and presenting investment performance**. It is a domain-rule standard, not a data or service model. Its concepts — composite, the firm, investment discretion — are useful canonical-model vocabulary. OpenIM's performance and reporting service domains are designed to be consistent with GIPS.

### ISO 20022 / FIX / FpML — *wire formats at the interop edge*

These are messaging and protocol standards — ISO 20022 the broad financial-messaging metamodel, FIX the electronic-trading wire protocol, FpML the XML standard for OTC derivatives. They are a different *type* of artefact from OpenIM. OpenIM's service domains use them as the interoperability formats at their edges. No overlap in kind: these are the wire; OpenIM is the capability and master-data model.

### Identifier standards — LEI, FIGI/OpenFIGI, ISIN, Private CUSIP — *the substrate OpenIM resolves across*

Public markets are well served by ISIN, CUSIP, SEDOL, FIGI, LEI. Private markets historically had almost nothing; Private CUSIPs (CUSIP Global Services with Aumni, a J.P. Morgan company) launched in 2025 but coverage is early. OpenIM does not compete with identifiers — it is the model that must *reference and resolve across* them. Because private markets lack a universal identifier, OpenIM's master-data domains include explicit entity-resolution, golden-key, and alias structures. A model that assumes a shared identifier breaks on private markets; OpenIM is built for the reality that there isn't one.

### FINOS AI Governance Framework — *the governance companion OpenIM aligns to*

The FINOS AI Governance Framework (AIGF v2.0, 2025) carries an agentic-AI risk catalogue cross-referenced to OWASP, MITRE, and the EU AI Act. OpenIM aligns its governance and audit binding to AIGF rather than inventing its own risk taxonomy. AIGF is the natural governance companion to an agent-native buy-side reference model.

## The agent-native prior art

A scan for an existing machine-consumable investment management reference model, equivalent to public banking reference models, found none. Agentic *trading* frameworks and small portfolio MCP servers exist, but they do not decompose the *institutional investment manager as a firm*. OpenIM provides service domains and a canonical model that people, architecture tools and AI agents can adopt independently.

## Where OpenIM might live

FINOS — the Fintech Open Source Foundation — is both the natural long-term home for a project like OpenIM and the place a parallel buy-side modelling effort would most likely emerge (FINOS has a growing buy-side membership). OpenIM launches independently to keep authorship and direction clear; contributing it into FINOS later is a credible path and an open question, not a closed one.

## OpenIM's four differentiators

Stated plainly, against the prior art above:

1. **Service-domain-first** — a capability decomposition of the firm, not only a data model. This is the differentiator against `glue`.
2. **Machine-consumable:** plain-text source, deterministic validation and model-derived exports for architecture tools, knowledge graphs, retrieval systems and AI agents, with no prescribed runtime.
3. **Private-markets master-data** — explicit entity resolution and golden keys for the no-universal-identifier reality of private markets.
4. **Vendor-neutral and maintained** — open and maintainer-led (see [GOVERNANCE.md](GOVERNANCE.md)), MIT-licensed, not tied to a single vendor's platform. This is the failure mode of `glue` that OpenIM exists to avoid.
