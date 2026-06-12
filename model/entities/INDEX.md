# OpenIM Canonical Entity Model

The canonical data model for the buy-side firm — the *things* an institutional investment manager keeps records about. Where the [service-domain model](../service-domains/INDEX.md) decomposes what the firm *does*, this entity model decomposes what the firm *knows*.

> Vocabulary not familiar? The [glossary](../glossary.md) defines the investment-management terms used here (NAV, IBOR / ABOR, the IRR / TVPI / DPI / RVPI family, four-lens NAV, golden key, LEI / FIGI / ISIN, and the rest).
>
> Visual: the [conceptual ERD](../diagrams/03-conceptual-erd.md) renders the core and its key relationships at a glance.

## Structure — a generalised core, plus specialisation packs

The entity model has two layers:

- **[`core/`](core/)** — the entities true of *every* institutional investor, whatever it invests in. A long-only equity manager, a fixed-income manager, a hedge fund, a multi-asset sovereign fund — all of them hold positions, in instruments, in portfolios, against counterparties, generating cash flows, valued over time. Identifier scheme `E-NN`.
- **[`specialisations/`](specialisations/)** — the entities specific to one *form* an investment takes. Each pack specialises the core by the instrument family and the access route — not by asset class: the fund-investing route (`private-markets/`), listed securities (`public-markets/`), the derivative instrument family (`derivatives/`), and directly-held physical assets (`real-assets/`). A fund is a kind of instrument, a capital call is a kind of transaction, a fund NAV is a kind of valuation. Identifier scheme is the pack prefix — `PM-NN`, `PB-NN`, `DR-NN`, `RA-NN`.

This is the BIAN-faithful shape — a general model, specialised — and it is what makes OpenIM serve institutional investment management broadly rather than the private-markets LP alone.

**The packs are orthogonal to the asset-class taxonomy.** [E-09 Asset Class](core/E-09-asset-class.md) is the *what* — the nine-class economic-exposure taxonomy (public equities, fixed income, cash, private equity, private credit, real estate, infrastructure, natural resources / commodities, hedge funds). The specialisation packs are the *how* — the form the holding takes. The two axes cross, they do not mirror each other: a private-equity exposure is held through the fund route (private-markets) or directly; a fixed-income exposure is held directly (public-markets) or referenced by a swap (derivatives); a natural-resources exposure is held directly (real-assets), through a fund (private-markets), or via an exchange-traded commodity. E-09 is the single asset-class spine the model reconciles to; the four packs are a deliberately coarser, orthogonal structuring by form of holding — which is why there are four packs and nine asset classes, and why that is not a mismatch.

## Design stance

- **Built for the no-universal-identifier reality of private markets.** Public markets have ISIN, CUSIP, SEDOL, FIGI, LEI; private markets have almost nothing. Every OpenIM master carries an internal golden key, an alias set (E-13) and an external-identifier map (E-14), and assumes entity resolution rather than a shared key.
- **Aligns to FIBO.** Where FIBO already models a concept — a legal entity, an equity, a bond — OpenIM references FIBO semantics rather than re-defining them. The core Legal Entity (E-01) and Instrument / Asset (E-02) are the alignment spine. See [PRIOR-ART.md](../../PRIOR-ART.md).
- **Bi-temporal.** Attributes that change over time are modelled with effective-time and record-time (E-12), so the model can answer "what did we believe, and as of when."
- **Roles, not duplicate masters.** Issuer, counterparty, manager, custodian, administrator, portfolio company are *roles* a Legal Entity plays — one party master, not six.

---

## The core — `core/`

The universal entities. Thirty-eight, in six groups: primary core, reference and identity core, risk core, computed-result and metadata core, operational core, strategy core.

### Primary core

| ID | Entity | Role |
|---|---|---|
| E-01 | [Legal Entity](core/E-01-legal-entity.md) | The universal party master — issuer, counterparty, manager, custodian, administrator, portfolio company all as roles of it. |
| E-02 | [Instrument / Asset](core/E-02-instrument-asset.md) | The universal holdable thing — listed equity, debt, derivatives, fund interests, loans, real assets, cash — with asset-class subtyping. |
| E-03 | [Portfolio / Mandate](core/E-03-portfolio-mandate.md) | The container — the investor's capital organised into portfolios, mandates, sleeves, accounts. |
| E-04 | [Holding / Position](core/E-04-holding-position.md) | What is owned — a position in an instrument, in a portfolio, at a point in time. IBOR and ABOR grain. |
| E-05 | [Transaction](core/E-05-transaction.md) | The universal investment event — trade, subscription, capital call, distribution, corporate action, transfer. |
| E-06 | [Cash Flow Event](core/E-06-cash-flow-event.md) | A dated movement of cash — the granular cash record performance is computed from. |
| E-07 | [Valuation](core/E-07-valuation.md) | A point-in-time value of a holding, and how it was arrived at — observable price or mark-to-model. Append-only. |
| E-08 | [Price & Market Data](core/E-08-price-market-data.md) | Observed market data — prices, yields, rates, FX — the observable inputs that value liquid holdings. |

### Reference and identity core

| ID | Entity | Role |
|---|---|---|
| E-09 | [Asset Class](core/E-09-asset-class.md) | The asset-class taxonomy across public and private markets. |
| E-10 | [Benchmark / Index](core/E-10-benchmark-and-index.md) | A benchmark or index and its constituents, as managed reference data. |
| E-11 | [Classification Type & Value](core/E-11-classification-type-and-value.md) | The extensible taxonomy behind time-varying classifications, defined as data not schema. |
| E-12 | [Classification History](core/E-12-classification-history.md) | The bi-temporal record of time-varying classifications — the P5 worked example. |
| E-13 | [Entity Alias](core/E-13-entity-alias.md) | A name a master record has been seen under — the structure that makes entity resolution work. |
| E-14 | [External Identifier](core/E-14-external-identifier.md) | A cross-reference from a golden key to an external system's identifier. |
| E-15 | [Document Metadata](core/E-15-document-metadata.md) | The metadata and provenance of a source document. |

### Risk core

The artefacts the risk function owns and produces. Risk *measurement* as a capability is the service-domain model's BD-07; these are the entities that capability is configured by and records into.

| ID | Entity | Role |
|---|---|---|
| E-16 | [Risk Limit](core/E-16-risk-limit.md) | A configured, versioned constraint on risk — the threshold a measured risk must stay within. |
| E-17 | [Scenario](core/E-17-scenario.md) | A defined stress or hypothetical scenario — a named set of market shocks a stress test runs against. |
| E-18 | [Limit Breach](core/E-18-limit-breach.md) | The event record of a measured risk crossing a Risk Limit — escalation and resolution. |
| E-19 | [Risk Measurement](core/E-19-risk-measurement.md) | A point-in-time risk result — VaR, exposure, sensitivity, stress loss — stored with its method and provenance. Append-only. |

### Computed-result and metadata core

Stored, provenance-bearing results and the definitions and provenance behind them. A computed or parsed figure becomes an entity where governance or audit needs a record that recomputation may not reproduce — the principle E-07 and E-19 already embody, extended here to performance, ESG, and parsed manager data.

| ID | Entity | Role |
|---|---|---|
| E-20 | [Performance Result](core/E-20-performance-result.md) | A stored point-in-time return figure with its inputs, methodology version and basis. The performance analogue of Valuation and Risk Measurement. Append-only. |
| E-21 | [ESG Measurement](core/E-21-esg-measurement.md) | A multi-provider, multi-pillar ESG / emissions data point — the ESG analogue of Price & Market Data, surfacing provider divergence. |
| E-22 | [Metric Definition](core/E-22-metric-definition.md) | The governed, versioned definition of a metric — formula, inputs, conventions — that stored results (E-20, E-19) reference. |
| E-23 | [Extraction Record](core/E-23-extraction-record.md) | The versioned record of what was parsed from a source manager document, with its confidence and validation. The provenance of captured data. |
| E-37 | [ESG Compliance Result](core/E-37-esg-compliance-result.md) | A stored point-in-time ESG-compliance result — SFDR Article classification, Taxonomy alignment, PAI indicators, mandate-screen pass / fail — for a portfolio, fund or composite. The SFDR / Taxonomy audit trail. Append-only. |
| E-38 | [Internal Credit Rating](core/E-38-internal-credit-rating.md) | The firm's own methodology-driven internal credit rating on an issuer or instrument — versioned through rating-change events, distinct from and cross-checked against the external rating agencies. |

### Operational core

The owned, lifecycle-bearing artefacts of the operations function — the break, the account structure, the collateral position, the tax lot, the governance authorisation, the complaint record, the oversight exception.

| ID | Entity | Role |
|---|---|---|
| E-24 | [Reconciliation Break](core/E-24-reconciliation-break.md) | An aged, owned reconciliation difference with a resolution lifecycle — the two sides, the difference, its cause and state. |
| E-25 | [Account](core/E-25-account.md) | The shared custody / safekeeping and bank / cash account master portfolios are held and settled through. Key-partitioned by `account_type`. |
| E-26 | [Collateral Position](core/E-26-collateral-position.md) | The generic posted / received collateral record — asset, direction, valuation, haircut, eligibility — that derivatives margin (DR-04) and securities lending (PB-10) both reference. |
| E-32 | [Tax Lot](core/E-32-tax-lot.md) | The per-(client, instrument, acquisition-tranche) lot record — cost basis, acquisition date, lot-relief method, wash-sale adjustment, link to the originating transaction. Append-only on the lot grain. |
| E-34 | [Investment Authorisation](core/E-34-investment-authorisation.md) | The Investment Committee's authorisation record — the IC memorandum, the decision, the conditions, the authority and mandate verification, the dissent. Co-owned by the fund-commitment IC and the direct-investment IC. |
| E-35 | [Complaint Record](core/E-35-complaint-record.md) | The regulated complaint record — the complaint, the acknowledgement, the investigation, the final response, the FOS-referral note, the redress, the root-cause categorisation. FCA DISP and Consumer-Duty evidence. |
| E-36 | [Oversight Exception](core/E-36-oversight-exception.md) | The structured exception record from the firm's oversight of an outsourced administrator — shadow-NAV difference, fee-calculation variance, reconciliation-process gap — with investigation and resolution. |

### Strategy core

The artefacts a strategy is built against and allocated through — the liability it targets, the risk pool it shares, the plan it follows, the goal it serves and the measured progress toward it.

| ID | Entity | Role |
|---|---|---|
| E-27 | [Liability Profile](core/E-27-liability-profile.md) | The actuarially-projected benefit / claim cash-flow stream a liability-driven or insurance strategy is built against, with its rate and inflation sensitivities. |
| E-28 | [Risk Budget](core/E-28-risk-budget.md) | A risk allowance allocated to a strategy, pod or manager — the allocated amount and its allocation lifecycle. Distinct from a Risk Limit. |
| E-29 | [Allocation Plan](core/E-29-allocation-plan.md) | A versioned allocation plan — strategic, reference-portfolio, or commitment-pacing — so a decision traces to the plan in force. Key-partitioned by `plan_type`. |
| E-30 | [Goal](core/E-30-goal.md) | A client's investment objective — target value, target date, priority layer, required probability of success — the unit the goals-based paradigm allocates against. Distinct from the mandate facet of E-03. |
| E-31 | [Goal Progress Measurement](core/E-31-goal-progress-measurement.md) | A stored point-in-time probability of meeting a goal, with the assumptions and methodology version behind it. The goals-based analogue of Risk Measurement and Performance Result. Append-only. |
| E-33 | [Financial Plan](core/E-33-financial-plan.md) | The structured, versioned multi-year financial plan a wealth manager builds for a household — cash-flow model, retirement / decumulation strategy, insurance and estate strategy, with the goal hierarchy inside. The suitability and Consumer-Duty fair-value-evidencing record. |

---

## The specialisations — `specialisations/`

All four specialisation packs are built. **35 specialisation entities** across the four (14 + 11 + 5 + 5); with the 38 core entities, the OpenIM entity model is **73 entities**.

| Pack | Entities | What it covers |
|---|---|---|
| **[private-markets/](specialisations/private-markets/README.md)** (`PM-NN`) | 14 | The private / illiquid / no-universal-identifier shape: the closed-end-fund-vehicle form of holding in full depth (funds, GPs, administrators, portfolio companies, legal vehicles, commitments, capital calls, distributions, fund investments, fund terms, manager succession, benchmark cross-reference, investor capital account) — the form used by GP/LP private-asset funds and by hedge-fund LPA structures alike — and directly-originated private credit (direct loans). |
| **[public-markets/](specialisations/public-markets/README.md)** (`PB-NN`) | 11 | Listed equities and fixed income: listed equity, debt instrument, the trade lifecycle (order, execution, allocation, settlement instruction), corporate action, income schedule, index constituent, securities loan, proxy vote. |
| **[derivatives/](specialisations/derivatives/README.md)** (`DR-NN`) | 5 | Listed and OTC derivatives, the ISDA master-agreement and collateral framework, margin balances, clearing relationships. Complementary to ISDA CDM — models the position / exposure / relationship layer above CDM's transaction grain. |
| **[real-assets/](specialisations/real-assets/README.md)** (`RA-NN`) | 5 | Directly-held real estate, infrastructure and natural-resource assets: the direct asset, its operating record, leases / tenancy, development projects, appraisals. The directly-held route — the fund route is private-markets. |

Each pack specialises the core: a fund is a kind of Instrument, a capital call is a kind of Transaction, a fund NAV is a kind of Valuation, a directly-held real asset is an Instrument valued by appraisal. Every specialisation entity declares the core entity it specialises.

---

## How the entity model relates to the service-domain model

The two halves of the OpenIM model interlock. Each [Service Domain](../service-domains/INDEX.md) **owns** a small number of entities (it is the authoritative source for them) and **consumes** others. Every entity file names its owning and consuming Service Domains; the full ownership map is consolidated in [`../ownership-map.md`](../ownership-map.md) — the single source of truth for entity ownership.

### Pack-size asymmetry — a defended design property

The four specialisation packs are unevenly sized — **private-markets 14, public-markets 11, derivatives 5, real-assets 5** — and the asymmetry is a deliberate design property. Three reasons:

- **The private-markets pack has more genuinely-distinct concepts.** Fund, capital call, distribution, fund administrator, GP, fund terms, manager-succession event, fund investment, LP commitment, legal vehicle, benchmark cross-reference, investor capital account, directly-originated private loan — these are all materially-distinct first-class entities. The liquid-markets analogues compress to fewer (an instrument plus its lifecycle events sit in the public-markets and derivatives packs).
- **The derivatives pack defers to ISDA CDM.** OpenIM's derivatives pack carries the *position / exposure / relationship* layer above CDM's transaction grain — 5 entities is sufficient because the transaction model lives in CDM. Carrying CDM's transaction entities verbatim would duplicate the standard OpenIM defers to.
- **The real-assets pack is a directly-held route, not the fund route.** The directly-held real-asset is an Instrument (RA-01) with an operating record (RA-02), a lease (RA-03), a development project where applicable (RA-04) and an appraisal (RA-05) — the entities are the durable artefacts of the operating mode. Fund-route real-assets (real-estate funds, infra funds, NR funds) are private-markets PM-pack entities; the RA pack is deliberately narrower in scope, not skewed.

See [PRIOR-ART.md](../../PRIOR-ART.md) for how this entity model relates to FIBO, ISDA CDM, the identifier standards, and the archived FINOS `glue` data model.
