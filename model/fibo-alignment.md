# FIBO Alignment

OpenIM builds on the [Financial Industry Business Ontology (FIBO)](https://spec.edmcouncil.org/fibo/) for the semantics FIBO already carries, and adds the layer FIBO does not model. This document is the concept-by-concept alignment: for every OpenIM core entity, the FIBO concept it corresponds to — or an explicit statement that FIBO does not model it, because those silences are what OpenIM contributes.

FIBO is a **lower layer**. It is a formal OWL ontology of the *things* of financial business — legal entities, instruments, securities, funds, indices — maintained by the EDM Council and standardised through OMG, published MIT-licensed. OpenIM is a service-domain decomposition plus a canonical operating model of the buy-side firm. The alignment below is exactly that — an alignment, not a contest. FIBO is OpenIM's most important alignment dependency.

**On the identifiers below.** Curies follow FIBO's own ontology-prefix convention (e.g. `fibo-fbc-fi-fi:FinancialInstrument`) and resolve under `https://spec.edmcouncil.org/fibo/ontology/`. One boundary matters for accuracy: FIBO's most foundational classes — `LegalEntity`, `LegalPerson` and similar — are defined in the **OMG Commons Ontology Library (`cmns-*`)**, which FIBO imports and refines. Where a class is canonically a Commons class, it is cited as `cmns-*`, not `fibo-*`.

## What FIBO covers, and where it stops

FIBO's coverage is **rich on the nouns of financial business**:

- **Legal entities** — its strongest area: corporations, partnerships, branches, trusts, sole proprietorships, and a full Legal Entity Identifier (LEI) model.
- **Financial instruments** — a deep `FinancialInstrument` hierarchy: equity, debt, derivative, cash, commodity, currency.
- **Securities, funds and collective investment vehicles** — including, *more than is commonly assumed*, private-equity funds, hedge funds, sovereign wealth funds, funds-of-funds, fund managers and administrators, and the GP/LP partnership roles.
- **Market indices, interest rates and FX**, corporate actions, loans, and derivatives master agreements.

What FIBO **does not** model is the **investment manager's operating layer**:

- the **private-markets investment lifecycle** — commitments as drawable obligations, capital calls, distributions, capital accounts, NAV as a valuation *event*, the waterfall;
- the **portfolio-mandate and allocation layer** — the discretionary mandate an asset manager runs on behalf of an asset owner;
- the **classification and entity-resolution machinery** — extensible time-varying classification, aliases, the golden-key cross-reference that the no-universal-identifier reality of private markets demands;
- the entire **risk-operating layer** — configured risk limits, scenarios, limit breaches, point-in-time risk measurements;
- **directly-held real assets** — FIBO touches real estate only as a securitised instrument (REITs, mortgage-backed securities), never as a directly-held operating asset with leases, development and appraisal.

That operating-and-master-data layer is OpenIM's contribution. FIBO models the funds and the partnerships *as legal and structural objects*; OpenIM models *how an institutional investor operates against them*.

## FIBO domains referenced

| Domain | Abbrev. | What OpenIM aligns to it |
|---|---|---|
| Foundations | FND | Parties, organisations, contracts, currency amounts; a provisional Cash Flows ontology (2025) |
| Business Entities | BE | Legal entities, partnerships, the LEI model — OpenIM's E-01 spine |
| Financial Business & Commerce | FBC | The `FinancialInstrument` hierarchy (E-02); clients and accounts (E-03 account facet) |
| Securities | SEC | Equities, debt, and the funds / collective-investment-vehicle module (the private-markets and public-markets packs) |
| Derivatives | DER | Derivative contracts and master agreements (the derivatives pack) |
| Indices & Indicators | IND | Market indices (E-10), interest rates and FX (E-08 rate/FX slice) |
| Corporate Actions & Events | CAE | Corporate actions (E-05 corporate-action facet; the public-markets corporate-action entity) |
| Market Data | MD | Market-data provenance and temporal snapshots (E-08 provenance) |
| Loans | LOAN | Loan instruments (debt-instrument alignment) |

## Core-entity alignment

| Entity | FIBO concept (module · curie) | Alignment |
|---|---|---|
| [E-01 Legal Entity](entities/core/E-01-legal-entity.md) | `cmns-org:LegalEntity`, `cmns-org:LegalPerson` (OMG Commons base); FIBO BE refinements `fibo-be-le-cb:Corporation`, `fibo-be-le-lei:LEIRegisteredEntity`, `fibo-be-ptr-ptr:Partnership` / `GeneralPartner` / `LimitedPartner`; roles `fibo-fbc-fi-fi:Issuer`, `fibo-sec-eq-eq:Custodian`, `fibo-sec-fund-fund:FundManager` | **Clean (rich).** FIBO's strongest area. OpenIM's "roles of one Legal Entity master" is an alignment-with-interpretation: FIBO sometimes reifies the role as a class, sometimes as a relationship. OpenIM consolidates them onto one party master. |
| [E-02 Instrument / Asset](entities/core/E-02-instrument-asset.md) | `fibo-fbc-fi-fi:FinancialInstrument` (apex); subclasses `EquityInstrument`, `DebtInstrument`, `DerivativeInstrument`, `CashInstrument`, `CommodityInstrument`, `CurrencyInstrument` | **Clean (rich).** OpenIM E-02 *is* `fibo-fbc-fi-fi:FinancialInstrument`. The asset-class subtyping aligns to FIBO's instrument subclasses. |
| [E-03 Portfolio / Mandate](entities/core/E-03-portfolio-mandate.md) | Account facet: `fibo-fbc-pas-caa:Account`, `CustomerAccount`, `AccountHolder`. Fund-portfolio facet: `fibo-sec-fund-fund` fund-portfolio concepts | **Partial.** FIBO models the *account* and the *fund's own portfolio*. It does not model the **investment mandate** — the discretionary brief (objectives, constraints, benchmark, permitted universe) an asset manager runs on behalf of an asset owner. The mandate-as-governing-instrument is OpenIM. |
| [E-04 Holding / Position](entities/core/E-04-holding-position.md) | `fibo-sec-fund-fund:FundHolding`, `FundPosition`; `fibo-sec-sec-pls:PoolConstituent` | **Partial.** FIBO has holding/position as a *fund's* constituent, not the general bi-temporal "position of any portfolio in any instrument at time T" OpenIM needs. OpenIM generalises and time-stamps it (IBOR/ABOR grain). |
| [E-05 Transaction](entities/core/E-05-transaction.md) | Corporate-action facet: `fibo-cae-...:CorporateAction` (CAE). Accounting movement: `fibo-fbc-pas-caa:AccountingTransaction` | **Partial / split.** FIBO has corporate actions and accounting transactions, but no unified buy-side transaction type spanning trade / subscription / capital call / distribution. The transaction *lifecycle* sits in ISDA CDM, the layer below OpenIM. |
| [E-06 Cash Flow Event](entities/core/E-06-cash-flow-event.md) | FND `CashFlows` (provisional, 2025); `fibo-fnd-acc-cur:MonetaryAmount`; `fibo-der-drc-bsc:CashflowTerms` | **Partial — newly present.** FIBO gained a provisional Cash Flows ontology in 2025 modelling cash-flow *patterns / expressions*, not OpenIM's dated, posted, reconcilable cash-flow *event record*. A moving target worth tracking. |
| [E-07 Valuation](entities/core/E-07-valuation.md) | — | **OpenIM-only.** FIBO has `MonetaryAmount` and "net asset value" as a label inside fund definitions, but no Valuation class carrying method, source and as-of provenance. Valuation-as-an-evented, methodology-bearing record (the four-lens NAV) is core OpenIM. |
| [E-08 Price & Market Data](entities/core/E-08-price-market-data.md) | `fibo-ind-ir-ir` (interest rates), `fibo-ind-fx-fx` (FX); MD provenance/temporal machinery | **Partial.** FIBO models rates, FX and indicators well, and has market-data provenance machinery, but not a general observed-price/quote tick record. The rate/FX/index slice aligns to IND; the observed-price record is OpenIM. |
| [E-09 Asset Class](entities/core/E-09-asset-class.md) | — | **OpenIM-only.** FIBO has instrument subclasses and a fund-strategy "asset class" label, but no extensible asset-class classification *scheme*. OpenIM's governed nine-class taxonomy has no FIBO counterpart. |
| [E-10 Benchmark / Index](entities/core/E-10-benchmark-and-index.md) | IND `fibo-ind-mkt-bas` — `EquityIndex`, `CreditIndex`, `ReferenceIndex`, basket indices, with constituents | **Clean.** Map E-10 to IND market indices. (Benchmark-*as-mandate-target* is the E-03 mandate facet, which is OpenIM.) |
| [E-11 Classification Type & Value](entities/core/E-11-classification-type-and-value.md) | — | **OpenIM-only.** FIBO uses SKOS-style schemes for specific things (legal-form scheme, fund-classification scheme) but has no generic, extensible classification-type/value framework. |
| [E-12 Classification History](entities/core/E-12-classification-history.md) | — | **OpenIM-only.** FIBO is largely a-temporal at instance level. Bi-temporal classification history is an OpenIM master-data discipline. |
| [E-13 Entity Alias](entities/core/E-13-entity-alias.md) | — | **OpenIM-only.** FIBO has alternative-name slots but no entity-resolution alias structure. The no-universal-identifier reality is OpenIM's to solve. |
| [E-14 External Identifier](entities/core/E-14-external-identifier.md) | `fibo-be-le-lei:LegalEntityIdentifier` (LEI), `fibo-fbc-fi-fi:FinancialInstrumentIdentifier`, `fibo-be-le-cb:RegistrationIdentifier` | **Partial.** FIBO models the identifier *types* well (see below). OpenIM aligns its identifier types to FIBO and adds the golden-key ↔ external-id cross-reference layer FIBO does not model. |
| [E-15 Document Metadata](entities/core/E-15-document-metadata.md) | — | **OpenIM-only.** FIBO carries ontology-level metadata and some document classes, not a general source-document provenance record. |
| [E-16 Risk Limit](entities/core/E-16-risk-limit.md) | — | **OpenIM-only.** FIBO has a fund-rule "investment limitations" label, not a general configurable, versioned risk-limit object. |
| [E-17 Scenario](entities/core/E-17-scenario.md) | — | **OpenIM-only.** |
| [E-18 Limit Breach](entities/core/E-18-limit-breach.md) | — | **OpenIM-only.** |
| [E-19 Risk Measurement](entities/core/E-19-risk-measurement.md) | — | **OpenIM-only.** |

**Tally:** 3 clean/rich (E-01, E-02, E-10) · 6 partial, FIBO has the noun and OpenIM adds the operating/temporal facet (E-03, E-04, E-05, E-06, E-08, E-14) · 10 OpenIM-only (E-07, E-09, E-11, E-12, E-13, E-15, E-16–E-19).

The shape of the result is the thesis: FIBO is rich on the **nouns of financial business** and silent on the **investment manager's operating model**.

## Specialisation packs

**Public-markets (PB) — strong FIBO alignment.** Listed equity → `fibo-sec-eq-eq:CommonShare` / `PreferredShare` (apex `fibo-fbc-fi-fi:EquityInstrument`); debt instrument → `fibo-fbc-fi-fi:DebtInstrument` (SEC/Debt has bonds, asset-backed securities, CDOs); corporate action → CAE `CorporateAction`; income schedule → `fibo-sec-eq-eq:DividendSchedule` (equity) and SEC/Debt coupon terms; index constituent → IND market/basket index constituents. The **trade-lifecycle entities** (order, execution, allocation, settlement instruction) are not in FIBO — that grain is ISDA CDM, the layer below OpenIM.

**Fund-operations (FO) — partial FIBO alignment.** FO-01 Fund Product partially aligns to FIBO's fund and collective-investment-vehicle model, with a significant operating-layer gap:

| Entity | FIBO concept (module · curie) | Alignment |
|---|---|---|
| [FO-01 Fund Product](entities/specialisations/fund-operations/FO-01-fund-product.md) | `fibo-sec-fund-fund:CollectiveInvestmentVehicle` (apex); `fibo-sec-fund-fund:FundManager` (manager entity role); `fibo-be-le-lei:LegalEntityIdentifier` (LEI field) | **Partial.** FIBO models the fund as a legal and structural noun — the collective investment vehicle as a `FinancialInstrument` with a legal form. FO-01 aligns at the structural level. What FIBO does not model, and what FO-01 adds: the **product lifecycle** (authorisation status, regulatory-wrapper enum, lifecycle states); the **dealing-terms governance layer** (dealing frequency, cut-off, pricing basis, settlement cycle, lock-up, gate, swing-pricing flag); the **manager-side issued-product view** distinct from the allocator's PM-01 view. The operating / product-management layer is OpenIM's contribution on top of FIBO's structural / legal noun. |
| [FO-02 Share / Unit Class](entities/specialisations/fund-operations/FO-02-share-unit-class.md) | `fibo-sec-fund-fund:FundShareClassUnit` (the class-level concept within a collective investment vehicle — the legal structure in which an investor purchases part of an investment pool, defined by investor type, minimum size, distribution type, fee and currency); `fibo-fbc-fi-fi:FinancialInstrumentIdentifier` (the per-class ISIN) | **Partial — structural and identifier alignment; operating and economic layer is OpenIM.** FIBO's `FundShareClassUnit` captures the class as a structural concept within a fund, with `AccumulatingShareClass` and `DistributingShareClass` subclasses that map directly onto FO-02's `distribution_policy` enum. FO-02 aligns at that structural level. What FIBO does not model, and what FO-02 adds: the **per-class fee schedule as computation-as-data** (management rate, OCF, performance-fee terms at class grain); the **static hedged-class configuration** (`hedged` flag and `class_currency` that parameterise the SD-11.3 hedge programme); the **dealing lifecycle governance** (minimum investment, investor eligibility categories); and the **class-grain NAV attribution** — the economic fact that accumulation, income and hedged classes of the same fund require the class as the irreducible record grain. |

**Private-markets (PM) — the headline gap, stated precisely.** FIBO's `SEC/Funds` and BE/Partnerships modules are richer than commonly assumed: fund → `fibo-sec-fund-fund:CollectiveInvestmentVehicle` / `PrivateEquityFund`; the GP role → `fibo-be-ptr-ptr:GeneralPartner`; fund administrator → `fibo-sec-fund-fund:FundAdministrator`; legal vehicle → `fibo-be-ptr-ptr:LimitedPartnership` / `fibo-be-le-lp:SpecialPurposeVehicle`. These align cleanly. What FIBO does **not** model is the **fund-investment lifecycle**: LP commitment as a tracked drawable obligation, capital call, distribution, capital account, NAV-as-event, the waterfall, fund terms as computation-as-data, manager-succession events, and the LP allocator's view of its fund investments. ("Commitment", "net asset value", "limited partner" appear only as descriptive text inside other FIBO definitions — there is no `Commitment` or `CapitalCall` class.) That lifecycle-and-allocator layer is OpenIM's headline contribution.

**Derivatives (DR) — strong FIBO alignment.** Listed/OTC derivative → `fibo-fbc-fi-fi:DerivativeInstrument` and DER `DerivativesContracts` (options, futures/forwards, swaps, credit, rate, structured); ISDA master agreement → DER `DerivativesMasterAgreements`. The position / exposure / relationship layer above the contract — margin balance, the clearing *relationship* record — is OpenIM (the CCP itself is `fibo-der-drc-bsc:DerivativesClearingOrganization`). OpenIM remains complementary to ISDA CDM for the transaction grain.

**Real-assets (RA) — near-total FIBO gap.** Direct real asset, operating record, lease / tenancy, development project, appraisal — none in FIBO. FIBO touches real estate only via `RealEstateInvestmentTrust` (a fund wrapper) and mortgage-backed securities — real estate *as a securitised instrument*, never as a directly-held operating asset. The strongest gap after the private-markets lifecycle.

## The identifier story

FIBO models identifiers as first-class, schemed objects — a genuine strength, and the alignment target for OpenIM's [E-14 External Identifier](entities/core/E-14-external-identifier.md):

- **LEI** → `fibo-be-le-lei:LegalEntityIdentifier`, with `LegalEntityIdentifierScheme` and `LEIRegisteredEntity`. FIBO's richest identifier model; aligns directly to OpenIM's use of LEI as a golden-key source for E-01.
- **Instrument identifiers** → `fibo-fbc-fi-fi:FinancialInstrumentIdentifier` — the slot ISIN, CUSIP and FIGI populate.
- **Registration identifiers** → `fibo-be-le-cb:RegistrationIdentifier` / `RegistrationIdentifierScheme`.

FIBO answers *"what is an LEI, and what scheme governs it."* OpenIM E-14 answers *"which external system's identifier corresponds to this golden key, and with what provenance."* OpenIM **aligns** its identifier *types* to FIBO's identifier classes and **adds** the cross-reference / golden-key / alias layer (E-13, E-14) FIBO does not model — because private markets lack a universal identifier, OpenIM must resolve *across* identifiers, not merely hold them. That resolution layer sits on top of FIBO's identifier vocabulary.

## Maintaining this alignment

FIBO moves — modules are revised and added each quarter (the Cash Flows ontology and the expanded derivatives master agreements both arrived in 2025). When a cited FIBO concept is revised, renamed or relocated (the Commons migration of foundational classes is the live example), this alignment is re-verified against the current FIBO source. The alignment is to a moving standard, deliberately.

See [`../PRIOR-ART.md`](../PRIOR-ART.md) for how OpenIM relates to FIBO, ISDA CDM, the identifier standards, and the other adjacent standards.
