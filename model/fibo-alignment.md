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
| [FO-02 Share / Unit Class](entities/specialisations/fund-operations/FO-02-share-unit-class.md) | No FIBO share-class concept — FIBO's Funds ontology does not define a share / unit class in its published RDF; structural alignment is to `fibo-sec-fund-fund:CollectiveInvestmentVehicle` and `fibo-sec-fund-fund:FundUnit`; `fibo-fbc-fi-fi:FinancialInstrumentIdentifier` (the per-class ISIN) | **Partial — structural and identifier alignment; the class concept itself and the operating and economic layer are OpenIM.** FIBO models the collective investment vehicle and the fund unit an investor holds; it does not model the share / unit class as a named concept, and FO-02's `distribution_policy` enum (accumulation / income) has no FIBO subclass counterpart. FO-02 aligns at the vehicle-and-unit structural level. What FIBO does not model, and what FO-02 adds: the **per-class fee schedule as computation-as-data** (management rate, OCF, performance-fee terms at class grain); the **static hedged-class configuration** (`hedged` flag and `class_currency` that parameterise the SD-11.3 hedge programme); the **dealing lifecycle governance** (minimum investment, investor eligibility categories); and the **class-grain NAV attribution** — the economic fact that accumulation, income and hedged classes of the same fund require the class as the irreducible record grain. |

**Private-markets (PM) — the headline gap, stated precisely.** FIBO's `SEC/Funds` and BE/Partnerships modules are richer than commonly assumed: fund → `fibo-sec-fund-fund:CollectiveInvestmentVehicle` / `PrivateEquityFund`; the GP role → `fibo-be-ptr-ptr:GeneralPartner`; fund administrator → `fibo-sec-fund-fund:FundAdministrator`; legal vehicle → `fibo-be-ptr-ptr:LimitedPartnership` / `fibo-be-le-lp:SpecialPurposeVehicle`. These align cleanly. What FIBO does **not** model is the **fund-investment lifecycle**: LP commitment as a tracked drawable obligation, capital call, distribution, capital account, NAV-as-event, the waterfall, fund terms as computation-as-data, manager-succession events, and the LP allocator's view of its fund investments. ("Commitment", "net asset value", "limited partner" appear only as descriptive text inside other FIBO definitions — there is no `Commitment` or `CapitalCall` class.) That lifecycle-and-allocator layer is OpenIM's headline contribution.

**Derivatives (DR) — strong FIBO alignment.** Listed/OTC derivative → `fibo-fbc-fi-fi:DerivativeInstrument` and DER `DerivativesContracts` (options, futures/forwards, swaps, credit, rate, structured); ISDA master agreement → DER `DerivativesMasterAgreements`. The position / exposure / relationship layer above the contract — margin balance, the clearing *relationship* record — is OpenIM (the CCP itself is `fibo-der-drc-bsc:DerivativesClearingOrganization`). OpenIM remains complementary to ISDA CDM for the transaction grain.

**Real-assets (RA) — near-total FIBO gap.** Direct real asset, operating record, lease / tenancy, development project, appraisal — none in FIBO. FIBO touches real estate only via `RealEstateInvestmentTrust` (a fund wrapper) and mortgage-backed securities — real estate *as a securitised instrument*, never as a directly-held operating asset. The strongest gap after the private-markets lifecycle.

## The identifier story

FIBO models identifiers as first-class, schemed objects — a genuine strength, and the alignment target for OpenIM's [E-14 External Identifier](entities/core/E-14-external-identifier.md):

- **LEI** → `fibo-be-le-lei:LegalEntityIdentifier`, with `LegalEntityIdentifierScheme` and `LEIRegisteredEntity`. FIBO's richest identifier model; aligns directly to OpenIM's use of LEI as a golden-key source for E-01.
- **Instrument identifiers** → `fibo-fbc-fi-fi:FinancialInstrumentIdentifier` — the slot ISIN, CUSIP and FIGI populate.
- **Registration identifiers** → `fibo-be-le-cb:RegistrationIdentifier` / `RegistrationIdentifierScheme`.

FIBO answers *"what is an LEI, and what scheme governs it."* OpenIM E-14 answers *"which external system's identifier corresponds to this golden key, and with what provenance."* OpenIM **aligns** its identifier *types* to FIBO's identifier classes and **adds** the cross-reference / golden-key / alias layer (E-13, E-14) FIBO does not model — because private markets lack a universal identifier, OpenIM must resolve *across* identifiers, not merely hold them. That resolution layer sits on top of FIBO's identifier vocabulary.

## Relation-verb alignment

The section above aligns OpenIM's entity *classes* to FIBO. This section aligns the [relation vocabulary](relations.md) — the typed edges *between* those entities — to FIBO's **object properties**. Where the class alignment answers *"is this thing the same thing FIBO models,"* this one answers *"is this relationship the same relationship FIBO models."*

**How to read a row.** Each forward relation verb gets one row: the FIBO object property it aligns to (with the FIBO module the property lives in), or `—` when FIBO declares no matching property. The verdict follows the same three-way scheme as the class alignment:

- **Clean** — FIBO declares an object property that models the same relationship with a directly corresponding domain and range. Asserted in the OWL export as `owl:equivalentProperty`.
- **Partial** — FIBO declares a related object property, but broader, narrower, or framed on a different domain/range (e.g. a role class rather than the party master). Asserted as `skos:closeMatch`.
- **OpenIM-only** — FIBO declares no object property for this relationship. No FIBO assertion is made; the edge stands on OpenIM's own vocabulary.

**On the predicate choice.** The OWL export attaches the FIBO alignment to each verb's `openim:<verb>` super-property — `owl:equivalentProperty` for a clean match, `skos:closeMatch` for a partial one — mirroring the class-level `owl:equivalentClass` / `skos:closeMatch` discipline exactly. Alignment is declared on the **forward** verb; the reverse direction is reached through the verb's declared OWL inverse. No verb is asserted as a logical equivalent except where FIBO's property genuinely models the identical relationship — the buy-side relations run on OpenIM's own entity classes (E-01 Legal Entity, E-03 Portfolio / Mandate, PM-01 Fund & Vehicle), not FIBO's role classes, so most matches are honestly *close*, not *equivalent*.

**On verification (non-negotiable).** Every FIBO object-property curie asserted below was verified against the live FIBO source — the module RDF from the published EDM Council FIBO ontology, confirmed to declare that `owl:ObjectProperty`. A relationship for which no matching FIBO object property could be verified is listed **openim-only**, never given an invented curie — the same discipline the class alignment above runs under, applied to the property layer. The FIBO modules confirmed for the aligned set: `FND/Relations/Relations`, `FBC/FinancialInstruments/FinancialInstruments`, `SEC/Funds/Funds`, `FND/Agreements/Contracts`, and `BE/OwnershipAndControl/CorporateControl`.

**The shape of the result — the thesis, restated at the relationship level.** FIBO is rich on the *nouns* of financial business and rich on a handful of *structural* relationships (issuance, sub-fund nesting, corporate subsidiarity, contract counterparties, derivative underliers) — and largely silent on the buy-side's *operating* relationships. The great majority of OpenIM's edges — a portfolio's holdings, a mandate's benchmark, a commitment's capital calls, a limit's breaches, a goal's progress, a document's subject — are the investment manager's operating model, which FIBO does not carry as object properties. That silence is exactly what the relation vocabulary contributes.

| Verb (LPG) | FIBO object property (module · curie) | Alignment |
|---|---|---|
| `ACQUIRED_VIA` | — | **OpenIM-only.** The tax-lot-to-acquisition-transaction edge is buy-side accounting; FIBO has no acquisition-transaction object property. |
| `ADMINISTERED_BY` | — | **OpenIM-only.** FIBO models an administrator as a role class but declares no record-to-administrator object property. |
| `AGAINST_COMMITMENT` | — | **OpenIM-only.** Capital-call-against-commitment is the private-markets lifecycle, the headline FIBO gap — no `Commitment` object property. |
| `ANNEXED_TO` | — | **OpenIM-only.** FIBO's contract subordination properties do not model a collateral annex to a master agreement at this grain. |
| `APPLIES_TO_PORTFOLIO` | — | **OpenIM-only.** The allocation-plan-governs-a-portfolio edge is the mandate/allocation layer FIBO does not model. |
| `AT_MEETING` | — | **OpenIM-only.** Proxy-vote-at-a-meeting is stewardship operations; no FIBO object property. |
| `BELONGS_TO_FUND_PRODUCT` | — | **OpenIM-only.** The share-class-to-fund-product composition is the fund-operations product layer; FIBO has no such object property. |
| `BENCHMARKED_TO` | — | **OpenIM-only.** Benchmark-as-mandate-target is the mandate layer (OpenIM); FIBO models the index as a noun, not the portfolio→benchmark edge. |
| `BOOKED_AS` | — | **OpenIM-only.** Order-booked-as-a-transaction is trade-lifecycle operations (the ISDA CDM layer below OpenIM); no FIBO object property. |
| `BREACH_OF_LIMIT` | — | **OpenIM-only.** The risk-operating layer (limits, breaches) is entirely OpenIM; FIBO carries no risk-limit object property. |
| `CHILD_ORDER_OF` | — | **OpenIM-only.** Parent/child order decomposition is execution operations; no FIBO object property. |
| `CLASSIFIED_AS` | — | **OpenIM-only.** OpenIM's extensible classification machinery has no FIBO object-property counterpart. |
| `CLASSIFIED_AS_ASSET_CLASS` | — | **OpenIM-only.** The governed asset-class taxonomy is OpenIM; FIBO has no instrument→asset-class object property. |
| `CLEARED_THROUGH` | — | **OpenIM-only.** FIBO models the clearing organisation as a class but declares no cleared-through object property. |
| `COLLATERALISED_BY` | — | **OpenIM-only.** The securities-loan-to-collateral-position edge is buy-side operations; no FIBO object property. |
| `COMPUTED_PER_METRIC` | — | **OpenIM-only.** The result-per-metric-definition edge is OpenIM's performance/metric machinery; no FIBO object property. |
| `CONSTITUENT_OF` | — | **OpenIM-only.** FIBO models index constituents as a structural feature of the index noun, not as a constituent→index object property at OpenIM's grain. |
| `CORRECTS` | — | **OpenIM-only.** Tax-statement correction lineage is fund-operations; no FIBO object property. |
| `DELEGATES_TO` | — | **OpenIM-only.** Service-provider sub-delegation is fund-operations governance; no FIBO object property. |
| `DETECTED_BY_MEASUREMENT` | — | **OpenIM-only.** Breach-detected-by-a-risk-measurement is the risk-operating layer; no FIBO object property. |
| `EXTRACTED_FROM` | — | **OpenIM-only.** The extraction-record-to-source-document edge is OpenIM's document-provenance layer; no FIBO object property. |
| `FOR_ALLOCATION` | — | **OpenIM-only.** Settlement-for-an-allocation is trade-lifecycle operations; no FIBO object property. |
| `FOR_INVESTMENT` | — | **OpenIM-only.** The legal-vehicle-held-for-a-fund-investment edge is the private-markets allocator view; no FIBO object property. |
| `FOR_ORDER` | — | **OpenIM-only.** Execution-for-an-order is trade-lifecycle operations; no FIBO object property. |
| `FOR_PARTY` | — | **OpenIM-only.** The household/client-party edge is the wealth-operating layer; FIBO has no such object property. |
| `FROM_TRANSACTION` | `fibo-fnd-rel-rel:isGeneratedBy` (FND/Relations) | **Partial.** A cash-flow event arises from a transaction; aligns to FIBO's generic `isGeneratedBy` relation, which is broader (any generated thing). |
| `FUNDED_BY_PORTFOLIO` | — | **OpenIM-only.** Goal-funded-by-a-portfolio is the goals-based operating layer; no FIBO object property. |
| `GOVERNED_BY_PLAN` | — | **OpenIM-only.** The portfolio-governed-by-the-in-force-allocation-plan edge is the mandate/allocation layer; no FIBO object property. |
| `HAS_AUTHORISED_PARTICIPANT` | — | **OpenIM-only.** The ETF authorised-participant edge is fund-operations; no FIBO object property. |
| `HAS_BORROWER` | — | **OpenIM-only.** FIBO models a borrower as a role but declares no securities-loan→borrower object property. |
| `HAS_CLASSIFICATION_TYPE` | — | **OpenIM-only.** OpenIM's classification-history machinery has no FIBO object-property counterpart. |
| `HAS_CLASSIFICATION_VALUE` | — | **OpenIM-only.** OpenIM's classification-history machinery has no FIBO object-property counterpart. |
| `HAS_CLEARING_BROKER` | — | **OpenIM-only.** FIBO models the clearing broker as a role but declares no clearing-relationship→broker object property. |
| `HAS_CONCESSION_GRANTOR` | — | **OpenIM-only.** The infrastructure concession-grantor edge is the real-assets operating layer, a near-total FIBO gap. |
| `HAS_CONTRACTOR` | — | **OpenIM-only.** The development-project contractor edge is the real-assets operating layer, a near-total FIBO gap. |
| `HAS_COUNTERPARTY` | `fibo-fnd-agr-ctr:hasCounterparty` (FND/Agreements/Contracts) | **Partial.** The OTC-derivative-faces-a-counterparty edge aligns to FIBO's contract `hasCounterparty`, whose range is the Counterparty role rather than OpenIM's Legal Entity master. |
| `HAS_CUSTODIAN` | — | **OpenIM-only.** FIBO models the custodian as a role class but declares no settlement/allocation→custodian object property. |
| `HAS_DOCUMENT` | — | **OpenIM-only.** The record-to-governing-document edge is OpenIM's document layer; no FIBO object property at this grain. |
| `HAS_FUND_ADMINISTRATOR` | — | **OpenIM-only.** FIBO models the fund administrator as a role class but the Funds module declares no fund→administrator object property. |
| `HAS_INVESTOR` | — | **OpenIM-only.** The record-held-for-an-investor edge is the buy-side operating view; no FIBO object property. |
| `HAS_PREDECESSOR_GP` | — | **OpenIM-only.** Manager-succession events are the private-markets lifecycle; no FIBO object property. |
| `HAS_SUBJECT` | — | **OpenIM-only.** The document→subject-entity bridge (the structured↔unstructured link) is OpenIM's; no FIBO object property. |
| `HAS_SUCCESSOR_GP` | — | **OpenIM-only.** Manager-succession events are the private-markets lifecycle; no FIBO object property. |
| `HAS_TARGET_PARTY` | — | **OpenIM-only.** The deal→target-company edge is the private-markets deal layer; no FIBO object property. |
| `HAS_TENANT` | — | **OpenIM-only.** The lease→tenant edge is the real-assets operating layer, a near-total FIBO gap. |
| `HELD_BY` | `fibo-fnd-rel-rel:isHeldBy` (FND/Relations) | **Partial.** The account-held-by-a-legal-entity edge aligns to FIBO's generic `isHeldBy` relation, which is broader (any held thing). |
| `HELD_THROUGH_VEHICLE` | — | **OpenIM-only.** The real-asset-held-through-a-legal-vehicle edge is the private-markets holding structure; no FIBO object property. |
| `HOLDS_INTEREST_IN` | — | **OpenIM-only.** The fund-investment→held-company/fund edge (fund-of-funds look-through) is the allocator view; no FIBO object property. |
| `INCLUDES_GOAL` | — | **OpenIM-only.** The financial-plan→goal-set edge is the goals-based operating layer; no FIBO object property. |
| `IN_FUND_FAMILY` | — | **OpenIM-only.** The vehicle→fund-family composition is an OpenIM master-data grouping; FIBO models legal fund structure, not this family edge. |
| `IN_PORTFOLIO` | — | **OpenIM-only.** The holding-belongs-to-a-portfolio edge is the core operating relationship FIBO does not model as an object property. |
| `ISSUED_BY` | `fibo-fnd-rel-rel:isIssuedBy` (FND/Relations) | **Partial.** The instrument-issued-by-a-legal-entity edge aligns to FIBO's `isIssuedBy` relation, which is broader (any issued thing, not only a financial instrument). |
| `LENDS_POSITION` | — | **OpenIM-only.** The securities-loan-lends-a-held-position edge is buy-side operations; no FIBO object property. |
| `LINKED_TO_PORTFOLIO` | — | **OpenIM-only.** The account↔portfolio link is the operating layer; no FIBO object property. |
| `LISTED_ON` | — | **OpenIM-only.** FIBO models the exchange as a noun but declares no listed-derivative→exchange object property at this grain. |
| `MANAGED_BY` | — | **OpenIM-only.** The portfolio/fund-managed-by-a-legal-entity edge is the mandate layer; FIBO models the manager role, not this object property. |
| `MANAGED_BY_GP` | — | **OpenIM-only.** FIBO models the general partner as a role class but the Funds module declares no fund→GP object property. |
| `MEASURES_GOAL` | — | **OpenIM-only.** The progress-measurement→goal edge is the goals-based operating layer; no FIBO object property. |
| `OF_FUND` | — | **OpenIM-only.** The commitment/call/distribution→fund edge is the private-markets lifecycle, the headline FIBO gap. |
| `OF_SHARE_CLASS` | — | **OpenIM-only.** The valuation/holding→share-class composition is the fund-operations class-grain layer; no FIBO object property. |
| `ON_INSTRUMENT` | — | **OpenIM-only.** The record-is-about-an-instrument edge is a generic operating pointer OpenIM types; FIBO models the instrument noun, not this edge. |
| `ON_REAL_ASSET` | — | **OpenIM-only.** The operating-record→real-asset edge is the real-assets operating layer, a near-total FIBO gap. |
| `ON_UNITHOLDING` | — | **OpenIM-only.** The dealing/statement→investor-unitholding edge is fund-operations; no FIBO object property. |
| `ORIGINATED_BY` | — | **OpenIM-only.** The direct-loan→originator edge is the private-credit operating layer; no FIBO object property. |
| `POSITION_IN` | — | **OpenIM-only.** The holding-is-a-position-in-an-instrument edge is the core IBOR/ABOR operating relationship; FIBO has no general position→instrument object property at this grain. |
| `PROVIDED_BY` | — | **OpenIM-only.** FIBO models a service provider as a role but declares no appointment→provider object property. |
| `REFERENCES_BENCHMARK` | — | **OpenIM-only.** The benchmark-cross-reference→index edge is OpenIM's reference-data mapping; no FIBO object property. |
| `RELATED_TO_PARTY` | `fibo-be-oac-cctl:isAffiliateOf` (BE/OwnershipAndControl/CorporateControl) | **Partial.** The typed party-to-party edge beyond the ownership hierarchy aligns to FIBO's `isAffiliateOf`; affiliation is one kind of related-party (OpenIM's discriminator also names manager-of / guarantor-of). |
| `RESULTS_IN_INSTRUMENT` | — | **OpenIM-only.** The corporate-action→resulting-instrument edge is corporate-action operations; no FIBO object property at this grain. |
| `SPECIALISES` | — | **OpenIM-only (by construction).** Specialisation is an *is-a* edge, modelled at the class level as `rdfs:subClassOf`, not as an object property — so it has no object-property counterpart to align. |
| `SUBFUND_OF` | `fibo-sec-fund-fund:isSubFundOf` (SEC/Funds) | **Clean.** The fund-product-is-a-sub-fund-of-an-umbrella edge models exactly FIBO's `isSubFundOf` (pooled-fund to pooled-fund sub-fund nesting). |
| `SUBSIDIARY_OF` | `fibo-be-oac-cctl:isSubsidiaryOf` (BE/OwnershipAndControl/CorporateControl) | **Partial.** The legal-entity-subsidiary-of-a-parent edge aligns to FIBO's `isSubsidiaryOf`, whose domain is the Subsidiary role rather than OpenIM's Legal Entity master. |
| `SUB_PORTFOLIO_OF` | — | **OpenIM-only.** Portfolio/mandate hierarchy is the operating layer; FIBO models fund sub-funds, not a portfolio sub-portfolio edge. |
| `SUCCEEDED_BY` | — | **OpenIM-only.** Portfolio-company succession is the private-markets deal layer; no FIBO object property. |
| `SUPERSEDED_BY` | — | **OpenIM-only.** OpenIM's bi-temporal classification-value supersession has no FIBO object property (FIBO's contract `supersedes` is a different domain — contracts, not classification values). |
| `UNDERLYING_INDEX_IS` | — | **OpenIM-only.** The derivative→underlying-index edge is modelled as an index reference; FIBO carries the index noun, not this edge at OpenIM's grain. |
| `UNDERLYING_IS` | `fibo-fbc-fi-fi:hasUnderlier` (FBC/FinancialInstruments) | **Partial.** The derivative-underlying-is-an-instrument edge aligns to FIBO's `hasUnderlier`, whose range is the broader Underlier concept. |
| `UNDER_AP_AGREEMENT` | — | **OpenIM-only.** The ETF creation-order→AP-agreement edge is fund-operations; no FIBO object property. |
| `UNDER_CLEARING_RELATIONSHIP` | — | **OpenIM-only.** The margin-balance→clearing-relationship edge is the derivatives operating layer above the contract; no FIBO object property. |
| `UNDER_MASTER_AGREEMENT` | — | **OpenIM-only.** FIBO models master agreements as nouns; the OTC-derivative→master-agreement edge at OpenIM's grain has no FIBO object property. |
| `UNDER_SCENARIO` | — | **OpenIM-only.** The risk-measurement→scenario edge is the risk-operating layer; no FIBO object property. |
| `UNDER_TERMS_VERSION` | — | **OpenIM-only.** The fund-terms versioning edge is the private-markets terms-as-data layer; no FIBO object property. |
| `USES_BASKET` | — | **OpenIM-only.** The ETF creation-order→creation-basket edge is fund-operations; no FIBO object property. |
| `VALUATION_OF` | — | **OpenIM-only.** Valuation-as-an-evented-record is OpenIM's (the four-lens NAV); FIBO has no valuation→position object property. |
| `VALUED_BY` | — | **OpenIM-only.** The appraisal→valuer edge is the real-assets operating layer, a near-total FIBO gap. |
| `VALUE_OF_TYPE` | — | **OpenIM-only.** The classification-value→classification-type composition is OpenIM's classification machinery; no FIBO object property. |
| `VIA_BROKER` | — | **OpenIM-only.** FIBO models a broker as a role but declares no order/execution→broker object property. |
| `VIA_INTERMEDIARY` | — | **OpenIM-only.** The omnibus-account→intermediary edge is fund-operations; no FIBO object property. |

**Tally.** 1 clean (`SUBFUND_OF`) · 7 partial (`FROM_TRANSACTION`, `HAS_COUNTERPARTY`, `HELD_BY`, `ISSUED_BY`, `RELATED_TO_PARTY`, `SUBSIDIARY_OF`, `UNDERLYING_IS`) · the remaining verbs openim-only. FIBO carries a handful of structural relationships as object properties; the buy-side operating relationships are OpenIM's contribution — the same shape the class alignment shows, now at the edge level.

## Maintaining this alignment

FIBO moves — modules are revised and added each quarter (the Cash Flows ontology and the expanded derivatives master agreements both arrived in 2025). When a cited FIBO concept is revised, renamed or relocated (the Commons migration of foundational classes is the live example), this alignment is re-verified against the current FIBO source. The alignment is to a moving standard, deliberately.

See [`../PRIOR-ART.md`](../PRIOR-ART.md) for how OpenIM relates to FIBO, ISDA CDM, the identifier standards, and the other adjacent standards.
