# Service Domain ↔ Entity Ownership Map

The consolidated map of which Service Domain is the **authoritative source** for each entity in the canonical OpenIM entity model. It declares, for each entity that has a non-default ownership pattern, the exact partition, facet or co-ownership structure under which the pattern operates.

This map is the **SSOT for entity ownership.** Each entity file's `Owned by` line is reconciled to it; the Tier-0 validator enforces the consistency. The map answers two questions for every entity: who is the authoritative source (the *system of record* — for agentINVEST, the write-path), and which Service Domains consume it.

The model has 17 Business Domains and 171 Service Domains; the canonical entity model has 86 entities — a generalised core of 38 (`E-NN`) plus five specialisation packs (`PB-NN`, `FO-NN`, `PM-NN`, `DR-NN`, `RA-NN`).

## The four ownership patterns

The model's default is **one entity, one owning Service Domain.** 76 of 86 entities follow this default. The remaining ten are not defects — they are entities whose shape genuinely admits more than one authoritative source. This map declares the pattern that applies to each, so the ownership is *explicit* rather than implicit.

**1. Single owner.** One Service Domain is the authoritative source for every instance. The vast majority (76 of 86 entities). *Example:* SD-13.1 owns E-02 Instrument / Asset.

**2. Key-partitioned ownership.** One entity type whose instances are partitioned by a key attribute — different attribute values are produced by different, co-equal Service Domains. The model's rule generalises naturally: *one authoritative source per (entity, key partition).* The schema is shared; the instance set is partitioned; no Service Domain is subordinate to another. Used where a key attribute determines which Service Domain is the system of record for that instance — most acutely for **E-04 Holding / Position**, where the `book` attribute records two genuinely-different position numbers that are reconciled against each other. Also used for **E-25 Account** (partitioned by `account_type`: safekeeping / cash / register) and **E-29 Allocation Plan** (partitioned by `plan_type`: strategic vs reference-portfolio vs commitment-pacing).

**3. Faceted ownership.** One entity carries two facets, owned by different Service Domains because they are different *kinds of fact* — not different instances. Used only for **E-03 Portfolio / Mandate**: the *portfolio* facet (the live holdings container) and the *mandate* facet (objectives and constraints) live on the same record but answer different questions.

**4. Co-ownership.** One entity, one concept, two co-equal owning Service Domains — neither partitioned by a key nor split into facets, but a single shared concept that two Service Domains are jointly the authoritative source for because they are two views of the same thing. Used for **E-27 Liability Profile**: the pension-scheme view (SD-01.7) and the insurance-book view (SD-01.8) of the same kind of actuarially-projected liability stream; and **E-34 Investment Authorisation**: the fund-commitment IC view (SD-03.9) and the direct-investment IC view (SD-04.5) of the same kind of governance record. Distinct from key-partitioned ownership — there is no key attribute that assigns an instance to one owner or the other; the two Service Domains co-own the entity outright.

## The 86 entities

### Generalised core — `model/entities/core/`

| Entity | Owning Service Domain | Pattern |
|---|---|---|
| E-01 Legal Entity | SD-13.2 Entity & Counterparty Master | Single owner |
| E-02 Instrument / Asset | SD-13.1 Instrument & Security Master | Single owner |
| **E-03 Portfolio / Mandate** | **SD-05.2 Portfolio Management & Monitoring** (portfolio facet) **+ SD-01.2 Investment Mandate & Policy Definition** (mandate facet) | **Faceted** |
| **E-04 Holding / Position** | **SD-12.1 IBOR** (`book = ibor` partition) **+ SD-12.2 ABOR** (`book = abor` partition) — co-equal | **Key-partitioned by `book`** |
| E-05 Transaction | SD-12.1 Investment Book of Record (IBOR) | Single owner |
| E-06 Cash Flow Event | SD-12.1 Investment Book of Record (IBOR) | Single owner |
| **E-07 Valuation** | per `method`: **SD-08.1** (`method = observable_price / amortised_cost`), **SD-08.2** (`method = mark_to_model`), **SD-08.3** (`method = manager_mark / appraisal`), **SD-12.9** (operated-vehicle struck NAV, recorded as `method = manager_mark`) | **Key-partitioned by `method`** |
| E-08 Price & Market Data | SD-13.4 Market & Reference Data Management | Single owner |
| E-09 Asset Class | SD-13.4 Market & Reference Data Management | Single owner |
| E-10 Benchmark / Index | SD-13.5 Benchmark & Index Data Management | Single owner |
| E-11 Classification Type & Value | SD-13.7 Data Quality & Governance | Single owner |
| E-12 Classification History | SD-13.7 Data Quality & Governance | Single owner |
| **E-13 Entity Alias** | per master kind: **SD-13.1** (instrument aliases), **SD-13.2** (entity aliases), **SD-13.3** (fund / vehicle aliases) | **Key-partitioned by master kind** |
| **E-14 External Identifier** | per master kind: **SD-13.1** (instrument identifiers), **SD-13.2** (entity identifiers), **SD-13.3** (fund / vehicle identifiers) | **Key-partitioned by master kind** |
| E-15 Document Metadata | SD-13.11 Document & Content Management | Single owner |
| E-16 Risk Limit | SD-07.7 Investment Risk Reporting & Limits Governance | Single owner |
| E-17 Scenario | SD-07.6 Scenario Analysis & Stress Testing | Single owner |
| E-18 Limit Breach | SD-07.7 Investment Risk Reporting & Limits Governance | Single owner |
| **E-19 Risk Measurement** | per `risk_type`: **SD-07.1** (market), **SD-07.2** (credit / counterparty), **SD-07.3** (liquidity), **SD-07.4** (concentration), **SD-07.6** (scenario / stress), **SD-07.8** (climate) | **Key-partitioned by `risk_type`** |
| E-20 Performance Result | SD-09.1 Performance Measurement | Single owner |
| E-21 ESG Measurement | SD-13.9 ESG & Sustainability Data | Single owner |
| E-22 Metric Definition | SD-13.8 Semantic & Metric Layer | Single owner |
| E-23 Extraction Record | SD-13.6 GP & Manager Report Ingestion | Single owner |
| E-24 Reconciliation Break | SD-12.10 Reconciliation | Single owner |
| **E-25 Account** | per `account_type`: **SD-12.5 Custody & Safekeeping Oversight** (`safekeeping`) **+ SD-11.7 Bank Account & Mandate Administration** (`cash`) **+ SD-15.4 Distribution Strategy & Channel Management** (`register`) — co-equal | **Key-partitioned by `account_type`** |
| E-26 Collateral Position | SD-11.5 Collateral Optimisation & Inventory Management | Single owner |
| **E-27 Liability Profile** | **SD-01.7 Liability-Driven & Cash-Flow-Driven Strategy + SD-01.8 Insurance Investment Strategy** — co-equal | **Co-owned** |
| E-28 Risk Budget | SD-01.9 Risk-Capital & Strategy Allocation | Single owner |
| **E-29 Allocation Plan** | per `plan_type`: **SD-01.4 Strategic Asset Allocation** (`strategic`) **+ SD-01.6 Total Portfolio Approach** (`reference_portfolio`) **+ SD-01.10 Commitment Pacing & Deployment Planning** (`commitment_pacing`) — co-equal | **Key-partitioned by `plan_type`** |
| E-30 Goal | SD-01.14 Goals-Based Planning | Single owner |
| E-31 Goal Progress Measurement | SD-09.5 Investment Analytics & Insight | Single owner |
| E-32 Tax Lot | SD-12.17 Tax-Lot Accounting | Single owner |
| E-33 Financial Plan | SD-15.15 Financial & Wealth Planning | Single owner |
| **E-34 Investment Authorisation** | **SD-03.9 Fund-Commitment Approval & Authorisation + SD-04.5 Investment Approval & Authorisation** — co-equal (the BD-04 IC for the direct-investment route) | **Co-owned** |
| E-35 Complaint Record | SD-15.16 Complaint & Client-Case Management | Single owner |
| E-36 Oversight Exception | SD-12.16 Outsourced-Operations Oversight | Single owner |
| E-37 ESG Compliance Result | SD-10.9 ESG & Sustainability Compliance | Single owner |
| E-38 Internal Credit Rating | SD-02.3 Credit Research & Analysis | Single owner |

### Private-markets pack — `model/entities/specialisations/private-markets/`

| Entity | Owning Service Domain | Pattern |
|---|---|---|
| PM-01 Fund & Vehicle | SD-13.3 Investment Vehicle & Fund Master | Single owner |
| PM-02 GP / Management Company | SD-13.2 Entity & Counterparty Master | Single owner |
| PM-03 Fund Administrator | SD-13.2 Entity & Counterparty Master | Single owner |
| PM-04 Portfolio Company | SD-13.2 Entity & Counterparty Master | Single owner |
| PM-05 Legal Vehicle | SD-13.3 Investment Vehicle & Fund Master | Single owner |
| PM-06 LP Commitment | SD-03.5 Fund Commitment & Subscription | Single owner |
| PM-07 Capital Call | SD-12.8 Capital Call & Distribution Processing | Single owner |
| PM-08 Distribution | SD-12.8 Capital Call & Distribution Processing | Single owner |
| PM-09 Fund Investment | SD-12.1 Investment Book of Record (IBOR) | Single owner |
| PM-10 Fund Terms | SD-13.3 Investment Vehicle & Fund Master | Single owner |
| PM-11 Manager Succession Event | SD-13.2 Entity & Counterparty Master | Single owner |
| PM-12 Benchmark Cross-Reference | SD-13.5 Benchmark & Index Data Management | Single owner |
| PM-13 Investor Capital Account | SD-12.9 Fund Accounting & NAV | Single owner |
| PM-14 Direct Loan | SD-04.12 Loan Monitoring & Workout | Single owner |
| PM-15 Deal / Investment Opportunity | SD-04.1 Deal Origination & Sourcing | Single owner |

### Public-markets pack — `model/entities/specialisations/public-markets/`

| Entity | Owning Service Domain | Pattern |
|---|---|---|
| PB-01 Listed Equity | SD-13.1 Instrument & Security Master | Single owner |
| PB-02 Debt Instrument | SD-13.1 Instrument & Security Master | Single owner |
| PB-03 Order | SD-06.1 Order Management | Single owner |
| PB-04 Execution | SD-06.2 Trade Execution | Single owner |
| PB-05 Allocation | SD-06.5 Trade Allocation | Single owner |
| PB-06 Settlement Instruction | SD-12.4 Trade Settlement | Single owner |
| PB-07 Corporate Action | SD-12.6 Corporate Actions Processing | Single owner |
| PB-08 Income Schedule | SD-13.1 Instrument & Security Master | Single owner |
| PB-09 Index Constituent | SD-13.5 Benchmark & Index Data Management | Single owner |
| PB-10 Securities Loan | SD-12.13 Securities Lending Operations | Single owner |
| PB-11 Proxy Vote | SD-12.12 Proxy Voting & Stewardship Operations | Single owner |

### Derivatives pack — `model/entities/specialisations/derivatives/`

| Entity | Owning Service Domain | Pattern |
|---|---|---|
| DR-01 Listed Derivative | SD-13.1 Instrument & Security Master | Single owner |
| DR-02 OTC Derivative | SD-13.1 Instrument & Security Master | Single owner |
| DR-03 Master Agreement | SD-14.9 Legal & Contract Management | Single owner |
| DR-04 Margin & Collateral Balance | SD-11.4 Margin & Collateral Operations | Single owner |
| DR-05 Clearing Relationship | SD-14.9 Legal & Contract Management | Single owner |

### Real-assets pack — `model/entities/specialisations/real-assets/`

| Entity | Owning Service Domain | Pattern |
|---|---|---|
| RA-01 Direct Real Asset | SD-13.1 Instrument & Security Master | Single owner |
| RA-02 Asset Operating Record | SD-04.10 Direct Real-Asset Management | Single owner |
| RA-03 Lease / Tenancy | SD-04.10 Direct Real-Asset Management | Single owner |
| RA-04 Development Project | SD-04.11 Development & Construction Management | Single owner |
| RA-05 Asset Appraisal | SD-08.3 Private-Asset Valuation | Single owner |

### Fund-operations pack — `model/entities/specialisations/fund-operations/`

| Entity | Owning Service Domain | Pattern |
|---|---|---|
| FO-01 Fund Product | SD-13.3 Investment Vehicle & Fund Master | Single owner |
| FO-02 Share / Unit Class | SD-13.3 Investment Vehicle & Fund Master | Single owner |
| FO-03 Investor Unitholding | SD-12.15 Transfer Agency & Investor Dealing | Single owner |
| FO-04 Dealing Order | SD-12.15 Transfer Agency & Investor Dealing | Single owner |
| FO-05 Fund Distribution Event | SD-12.7 Income & Distribution Processing | Single owner |
| FO-06 Fee Accrual | SD-12.11 Expense, Fee & Carry Processing | Single owner |
| FO-07 Investor Tax Statement | SD-17.4 Investment & Portfolio Tax | Single owner |
| FO-08 Service-Provider Appointment | SD-17.8 Vendor, Outsourcing & Service-Provider Oversight | Single owner |
| FO-09 Omnibus Account | SD-15.4 Distribution Strategy & Channel Management | Single owner |
| FO-10 ETF Creation/Redemption Order | SD-12.15 Transfer Agency & Investor Dealing | Single owner |
| FO-11 ETF Creation Basket (Portfolio Composition File) | SD-12.9 Fund Accounting & NAV | Single owner |
| FO-12 ETF Authorised-Participant Agreement | SD-12.15 Transfer Agency & Investor Dealing | Single owner |

## The ten non-default cases — in detail

### E-04 Holding / Position — key-partitioned by `book`

**Resolution.** E-04 is **one entity type**. The `book` attribute is part of its **identity** — every position record is inherently *a position in a named book*. Ownership is partitioned on `book` and is **co-equal**: SD-12.1 IBOR is the sole authoritative source for every instance with `book = ibor`; SD-12.2 ABOR is the sole authoritative source for every instance with `book = abor`. Neither Service Domain holds schema authority over the other; the schema is the model's, defined here. Consumers must declare which book they consume.

**Why this, not a split.** IBOR and ABOR are two genuinely different position numbers for the same logical holding — that disagreement is the point, and SD-12.10 reconciles them. Reconciliation is by definition the matching of two records of *the same thing*; it is evidence the two books are one concept, two records — not two entities. The two books also share an identical schema (instrument, portfolio, quantity, value, as-of), and two schema-identical types is a modelling anti-pattern. The `book` dimension also takes more than two values in practice (the operated-fund's NAV book is SD-12.9's), and a dimension that takes N values is a key attribute, not N types.

**Why this, not "type-owner over a subordinate."** Earlier framings put SD-12.1 over SD-12.2 as a schema-authority holder. That hierarchy is artificial — the two books are peers operationally and in the capability model (two separately-decomposed Service Domains, reconciled against each other). Co-equal key-partition ownership removes the hierarchy and matches the operational reality.

**Why this is not "muddying" the operational separation.** A genuine challenge: in practice IBOR and ABOR are *entirely different systems*, operated by different functions, sometimes by an external fund administrator — and modelling them as one entity feels alien. The challenge is well-founded as a signal of *physical* separateness, but OpenIM is the *conceptual* / capability layer (vendor-neutral, capabilities-not-systems); the physical landscape is an agentINVEST / implementation concern. The model deliberately keeps E-07 Valuation as one entity across radically different provenance — an observable price, a mark-to-model mark, an appraisal, a manager mark — including external producers; E-04 key-partitioned is consistent with that precedent. To honour the operational separateness, the model is explicit: `book` is *in the key*, every consuming Service Domain *names its book*, and the two Service Domains stand here as two separate, co-equal owners. The separation is loud and visible — it is not duplicated as schema-identical types.

**Consumers must declare which book.** Front office consumes `book = ibor`; SD-12.9 Fund Accounting & NAV, SD-09 Performance & Analytics (the realised-return series), the BD-16 reporting Service Domains (SD-16.2 owner & investor reporting, SD-16.3 regulatory filings, SD-16.4 financial disclosure) and BD-14's internal-control attestation (SD-14.7) consume `book = abor`; BD-07 Investment Risk consumes ibor for intraday measures and abor for period-end. SD-12.10 Reconciliation operates across the two.

### E-07 Valuation — key-partitioned by `method`

One entity. A given holding at a given as-of has one valuation, recorded with a `method` value — drawn from the attribute schema's enum (`observable_price` / `mark_to_model` / `manager_mark` / `appraisal` / `amortised_cost`) — that determines the producing Service Domain. **SD-08.1** Security Pricing for `method = observable_price` (a quoted market price) and `method = amortised_cost` (the rule-based amortised-cost carrying price of a held-to-maturity debt instrument). **SD-08.2** Independent / Mark-to-Model Valuation for `method = mark_to_model` (a quant-modelled mark). **SD-08.3** Private-Asset Valuation for `method = manager_mark` (the manager- or administrator-reported mark of a private fund, private-credit or directly-held private interest) and `method = appraisal` (the real-asset appraisal RA-05 specialises). **SD-12.9** Fund Accounting & NAV produces the official struck NAV of a vehicle the institution *operates*, recorded as `method = manager_mark`: it shares the method value with SD-08.3 because both are manager/administrator-struck marks, but the producing capability differs — SD-12.9 strikes the NAV of an operated vehicle (the source side, with its PM-13 investor capital accounts), where SD-08.3 records the mark the institution consumes as an investor in an externally-managed interest. Holding-level marks and the operated-vehicle NAV are different *kinds* of valuation, intentionally one entity to keep the value-trajectory same-shape across kinds — the BD-08 design.

**Share/unit-class grain (the NAV-per-unit variant).** E-07 also accommodates a third grain: the `unit_class_id` FK → FO-02 (Share / Unit Class) populates when the valuation is at the per-class NAV-per-unit level, with `units_in_issue` carried as the divisor at the moment of the strike. These records use `method = manager_mark` and are produced exclusively by **SD-12.9** Fund Accounting & NAV — the class-level NAV-per-unit that SD-12.9 strikes from the fund-level NAV, the hedge P&L (SD-11.3, for currency-hedged classes), and the securities-lending revenue (SD-12.13). The `unit_class_id` is null for position-grain and instrument-grain valuations; the class-grain rows are discriminated by a non-null `unit_class_id`.

### E-13 Entity Alias and E-14 External Identifier — key-partitioned by master kind

An alias or external identifier always attaches to a master record. The master kind is part of its identity. **SD-13.1** Instrument & Security Master is the authoritative source for aliases / identifiers of instruments and assets. **SD-13.2** Entity & Counterparty Master for legal entities (including issuers, counterparties, managers, custodians in their role facets). **SD-13.3** Investment Vehicle & Fund Master for funds and vehicles. The same shape — one record set, partitioned by which master the alias/identifier resolves against; each master's owning Service Domain is the authoritative source for its partition.

### E-19 Risk Measurement — key-partitioned by `risk_type`

A point-in-time risk result, append-only. `risk_type` is part of its identity — a market-risk measure and a credit-risk measure are different instances, produced by different Service Domains. **SD-07.1** Market Risk Management produces `risk_type = market`. **SD-07.2** Credit & Counterparty Risk Management — `credit` / `counterparty`. **SD-07.3** Liquidity Risk Management — `liquidity` (this partition holds both the liquidity risk measures and the per-holding liquidity tier classification SD-07.3 produces by applying the SD-01.11 tier taxonomy; SD-05.6 and SD-11.2 consume the classification). **SD-07.4** Concentration & Exposure Risk — `concentration`. **SD-07.6** Scenario Analysis & Stress Testing — `scenario` / `stress`. **SD-07.8** Climate Risk Analytics — `climate`. SD-07.7 Investment Risk Reporting & Limits Governance is the *consumer* of E-19 (the consolidated reporting and limits-breach detection); it is not a producing source. The schema is the model's, common across measurement types.

### E-03 Portfolio / Mandate — faceted

E-03 carries two facets that are different *kinds of fact*, not different instances. The **portfolio facet** — the live holdings container, the constraint-monitoring subject, the report subject — is owned by **SD-05.2 Portfolio Management & Monitoring** (the ongoing system of record for the operative portfolio). The **mandate facet** — the objectives, return target, risk appetite, time horizon and constraints the portfolio is run to — is owned by **SD-01.2 Investment Mandate & Policy Definition** (which already explicitly declares this). SD-05.1 Portfolio Construction is *not* a co-owner — it *constructs* the initial target portfolio from the SD-05.2 record and the SD-01.2 mandate; SD-05.2 is the ongoing owner. The faceted split here is *not* key-partitioned: every E-03 instance carries both facets simultaneously, but each facet's authoritative source is a different Service Domain. A faceted entity is rarer than a key-partitioned one and is reserved for cases where one entity record is genuinely the joint product of two different authoring capabilities. E-03 is the only one.

### E-25 Account — key-partitioned by `account_type`

One entity. A custody / safekeeping account, a bank / cash account, and a fund-register / nominee account are the same kind of thing — an account structure portfolios are held and settled through — distinguished by `account_type`, which is part of the account's identity. Ownership is partitioned and co-equal: **SD-12.5 Custody & Safekeeping Oversight** is the sole authoritative source for every instance with `account_type = safekeeping`; **SD-11.7 Bank Account & Mandate Administration** for every instance with `account_type = cash`; **SD-15.4 Distribution Strategy & Channel Management** for every instance with `account_type = register` (the fund-register / nominee account held by an intermediary or distributor at the transfer agent, as specialised by FO-09 Omnibus Account). No partition holds schema authority over any other; the schema is the model's. The key-partitioned pattern (the same shape E-04 uses on `book`) gives the three co-equal owners one schema rather than three schema-identical entities. The entity aligns to the FIBO `fibo-fbc-pas-caa:Account` concept rather than re-defining what an account is.

### E-27 Liability Profile — co-owned

One entity, one concept, two co-equal owners. A liability profile — an actuarially-projected benefit / claim cash-flow stream with its rate and inflation sensitivities — is the subject a liability-relative strategy is built against. **SD-01.7 Liability-Driven & Cash-Flow-Driven Strategy** (the pension-scheme view) and **SD-01.8 Insurance Investment Strategy** (the insurance-book view) are jointly the authoritative source for it: it is the same kind of liability stream seen from two strategies, and both surfaced it as a shared gap. This is co-ownership, not key-partition: there is no key attribute that assigns a given liability profile to one owner or the other — the two Service Domains co-own the entity outright, as two views of the same concept. It is the first co-owned entity in the model; a fourth ownership pattern, distinct from single, key-partitioned and faceted.

### E-34 Investment Authorisation — co-owned

One entity, one concept, two co-equal owners. An Investment Authorisation — the IC memorandum, the decision, the conditions, the authority verification, the dissent — is the governance record any subsequent execution depends on. **SD-03.9 Fund-Commitment Approval & Authorisation** (the IC gate for the fund-commitment route in BD-03) and **SD-04.5 Investment Approval & Authorisation** (the IC gate for the direct-investment route in BD-04) are jointly the authoritative source for it: a real firm may operate one IC body across both routes or two separate bodies, but the model carries the capability as one entity with the `investment_route` field naming which IC route an authorisation came from. The `investment_route` is **not a partition key** — there is no schema authority either route holds over the other, and either route's authorisation is a complete instance in its own right. It is co-ownership outright, in the E-27 pattern: two views of the same kind of governance record, jointly the authoritative source for it. The second co-owned entity in the model.

### E-29 Allocation Plan — key-partitioned by `plan_type`

One entity. A strategic asset allocation, a total-portfolio reference and factor budget, and a commitment-pacing plan are the same kind of artefact — a versioned, approved plan capital is allocated against — distinguished by `plan_type`, which is part of the plan's identity. Ownership is partitioned and co-equal: **SD-01.4 Strategic Asset Allocation** is the authoritative source for `plan_type = strategic`; **SD-01.6 Total Portfolio Approach** for `plan_type = reference_portfolio`; **SD-01.10 Commitment Pacing & Deployment Planning** for `plan_type = commitment_pacing`. Three Service Domains each surfaced the same versioning gap — the need to trace a decision to the plan in force when it was taken — and the key-partitioned pattern gives them one schema with co-equal owners rather than three near-identical plan entities. SAA and TPA are mutually-exclusive operating models in practice (an institution runs one or the other on a given pool), so the partition rarely populates more than two of its three values on one pool.

## How this map is maintained

- Every entity file's `Owned by` line states the owner(s) per the pattern in this map and links back here.
- Every Service Domain file's `Owns` line names the entity (or the entity partition / facet) it owns; the map is consistent with the SD-side declarations.
- Changes to ownership go through the model's standard route — an ADR — and update this map *and* the entity file(s) *and* the SD `Owns` line(s) atomically. The Tier-0 validator's ownership-consistency check (see `tools/openim-validate/`) catches drift.
- The patterns themselves — single owner, key-partitioned, faceted — are the documented vocabulary. A new entity that does not fit one of these patterns is itself a finding to surface.

## Open extensions

- A first-class `Ownership` declaration in the entity-model schema (frontmatter / structured table) so the map is generated, not maintained by hand.
- The boundary with **consumption** — every entity records its consumers; a future extension surfaces the full consumes graph alongside the ownership map.
- A possible refinement of E-19's pattern if a *consolidated Risk Measurement record entity* — a steward-owned roll-up — becomes warranted alongside the per-type producing partitions.
