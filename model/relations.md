# Entity Relation Vocabulary

The typed, named set of **relationships** between the entities of the OpenIM canonical model — the edges that turn the entity model from a data dictionary into a graph an agent, an analyst or a warehouse can traverse. Where the [entity model](entities/INDEX.md) says *what a firm knows* and the [ownership map](ownership-map.md) says *who is the authoritative source*, this vocabulary says *how the things a firm knows connect*.

Every foreign-key column and every specialisation line in the entity model is an edge. This document names each of those edges with a **relationship verb** carrying a meaning — `ISSUED_BY`, `MANAGED_BY`, `POSITION_IN`, `HAS_SUBJECT` — rather than the raw column that implements it. Each verb is directed, has a declared inverse, and carries the cardinality and kind of the relationship. The [mapping table](#the-mapping) at the end binds every edge in the model to exactly one verb.

## How to read a relation

Each verb is declared once, in the block below, and reused wherever the same relationship holds. A verb carries:

- **Two names, one meaning.** An **LPG name** in `UPPER_SNAKE` (`ISSUED_BY`) — the labelled-property-graph relationship type, the openCypher / graph-engine idiom — and an **OWL name** in `lower-kebab` (`issued-by`) — the same relationship as an ontology super-property. One vocabulary, two serialisation casings.
- **A direction.** Every edge runs *source &rarr; target*, following the foreign key: the entity that carries the column points to the entity the column resolves to.
- **An inverse.** The named relationship in the other direction, so the graph is traversable both ways (`ISSUED_BY` &harr; `ISSUER_OF`). No two verbs share an inverse.
- **A kind.** `is-a` (specialisation), `composition` (a part of a whole that does not stand alone), `role` (the target plays a named role — issuer, custodian, counterparty), or `reference` (a plain typed pointer).
- **A cardinality.** The source-to-target multiplicity — `n-to-1` for a normal foreign key (many rows point to one target), `n-to-n` where the column holds a set.

## The relation verbs

### Specialisation

#### `SPECIALISES` — `specialises`
- **Direction:** pack entity &rarr; core entity
- **Kind:** is-a
- **Cardinality:** n-to-1
- **Inverse:** `SPECIALISED_BY`
- **Meaning:** The pack entity specialises a core entity (the Specialises line).
- **Example:** `DR-01` **SPECIALISES** `E-02` (Listed Derivative specialises Instrument / Asset).

### Party and counterparty roles

#### `ISSUED_BY` — `issued-by`
- **Direction:** E-02 Instrument / Asset &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `ISSUER_OF`
- **Meaning:** The instrument is issued by a legal entity.
- **Example:** `E-02.issuer_entity_id` &rarr; `E-01` reads *E-02 Instrument / Asset* **ISSUED_BY** *E-01 Legal Entity*.

#### `MANAGED_BY` — `managed-by`
- **Direction:** E-03 Portfolio / Mandate &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `MANAGES`
- **Meaning:** The portfolio or fund is managed by a legal entity.
- **Example:** `E-03.managed_by_entity_id` &rarr; `E-01` reads *E-03 Portfolio / Mandate* **MANAGED_BY** *E-01 Legal Entity*.

#### `MANAGED_BY_GP` — `managed-by-gp`
- **Direction:** PM-01 Fund & Vehicle &rarr; PM-02 GP / Management Company
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `GP_MANAGES`
- **Meaning:** The fund is managed by a GP / management company.
- **Example:** `PM-01.gp_id` &rarr; `PM-02` reads *PM-01 Fund & Vehicle* **MANAGED_BY_GP** *PM-02 GP / Management Company*.

#### `HAS_COUNTERPARTY` — `has-counterparty`
- **Direction:** DR-02 OTC Derivative &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `COUNTERPARTY_IN`
- **Meaning:** The record faces a legal entity as its counterparty.
- **Example:** `DR-02.counterparty_entity_id` &rarr; `E-01` reads *DR-02 OTC Derivative* **HAS_COUNTERPARTY** *E-01 Legal Entity*.

#### `HAS_INVESTOR` — `has-investor`
- **Direction:** DR-03 Master Agreement & Collateral Terms &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `INVESTOR_IN`
- **Meaning:** The record is held for / subscribed by an investor legal entity.
- **Example:** `DR-03.investor_entity_id` &rarr; `E-01` reads *DR-03 Master Agreement & Collateral Terms* **HAS_INVESTOR** *E-01 Legal Entity*.

#### `HELD_BY` — `held-by`
- **Direction:** E-25 Account &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `HOLDER_OF`
- **Meaning:** The account is held by a legal entity.
- **Example:** `E-25.holder_entity_id` &rarr; `E-01` reads *E-25 Account* **HELD_BY** *E-01 Legal Entity*.

#### `CLEARED_THROUGH` — `cleared-through`
- **Direction:** DR-01 Listed Derivative &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `CLEARS`
- **Meaning:** The instrument or relationship clears through a central counterparty.
- **Example:** `DR-01.ccp_entity_id` &rarr; `E-01` reads *DR-01 Listed Derivative* **CLEARED_THROUGH** *E-01 Legal Entity*.

#### `LISTED_ON` — `listed-on`
- **Direction:** DR-01 Listed Derivative &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `LISTS`
- **Meaning:** The listed derivative is listed on an exchange.
- **Example:** `DR-01.exchange_entity_id` &rarr; `E-01` reads *DR-01 Listed Derivative* **LISTED_ON** *E-01 Legal Entity*.

#### `HAS_CLEARING_BROKER` — `has-clearing-broker`
- **Direction:** DR-05 Clearing Relationship &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `CLEARING_BROKER_FOR`
- **Meaning:** The clearing relationship runs through a clearing broker.
- **Example:** `DR-05.clearing_broker_entity_id` &rarr; `E-01` reads *DR-05 Clearing Relationship* **HAS_CLEARING_BROKER** *E-01 Legal Entity*.

#### `ADMINISTERED_BY` — `administered-by`
- **Direction:** E-36 Oversight Exception &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `ADMINISTERS`
- **Meaning:** The oversight record names the administrator legal entity.
- **Example:** `E-36.administrator_entity_id` &rarr; `E-01` reads *E-36 Oversight Exception* **ADMINISTERED_BY** *E-01 Legal Entity*.

#### `HAS_FUND_ADMINISTRATOR` — `has-fund-administrator`
- **Direction:** PM-01 Fund & Vehicle &rarr; PM-03 Fund Administrator
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `FUND_ADMINISTRATOR_OF`
- **Meaning:** The fund names its fund administrator.
- **Example:** `PM-01.administrator_id` &rarr; `PM-03` reads *PM-01 Fund & Vehicle* **HAS_FUND_ADMINISTRATOR** *PM-03 Fund Administrator*.

#### `FOR_PARTY` — `for-party`
- **Direction:** E-30 Goal &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `PARTY_OF`
- **Meaning:** The record belongs to the household or client party it concerns.
- **Example:** `E-30.household_entity_id` &rarr; `E-01` reads *E-30 Goal* **FOR_PARTY** *E-01 Legal Entity*.

#### `PROVIDED_BY` — `provided-by`
- **Direction:** FO-08 Service-Provider Appointment &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `PROVIDES`
- **Meaning:** The service-provider appointment names the provider legal entity.
- **Example:** `FO-08.provider_entity_id` &rarr; `E-01` reads *FO-08 Service-Provider Appointment* **PROVIDED_BY** *E-01 Legal Entity*.

#### `DELEGATES_TO` — `delegates-to`
- **Direction:** FO-08 Service-Provider Appointment &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `DELEGATED_FROM`
- **Meaning:** The appointment delegates to a sub-provider legal entity.
- **Example:** `FO-08.delegates_to_entity_id` &rarr; `E-01` reads *FO-08 Service-Provider Appointment* **DELEGATES_TO** *E-01 Legal Entity*.

#### `VIA_INTERMEDIARY` — `via-intermediary`
- **Direction:** FO-09 Omnibus Account &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `INTERMEDIARY_FOR`
- **Meaning:** The omnibus account is held through an intermediary legal entity.
- **Example:** `FO-09.intermediary_entity_id` &rarr; `E-01` reads *FO-09 Omnibus Account* **VIA_INTERMEDIARY** *E-01 Legal Entity*.

#### `HAS_AUTHORISED_PARTICIPANT` — `has-authorised-participant`
- **Direction:** FO-10 ETF Creation/Redemption Order &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `AUTHORISED_PARTICIPANT_FOR`
- **Meaning:** The ETF record names an authorised-participant legal entity.
- **Example:** `FO-10.ap_entity_id` &rarr; `E-01` reads *FO-10 ETF Creation/Redemption Order* **HAS_AUTHORISED_PARTICIPANT** *E-01 Legal Entity*.

#### `VIA_BROKER` — `via-broker`
- **Direction:** PB-03 Order &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `BROKER_FOR`
- **Meaning:** The order or execution is routed through a broker legal entity.
- **Example:** `PB-03.broker_entity_id` &rarr; `E-01` reads *PB-03 Order* **VIA_BROKER** *E-01 Legal Entity*.

#### `HAS_CUSTODIAN` — `has-custodian`
- **Direction:** PB-05 Allocation &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `CUSTODIAN_FOR`
- **Meaning:** The settlement or allocation names the custodian legal entity.
- **Example:** `PB-05.custodian_entity_id` &rarr; `E-01` reads *PB-05 Allocation* **HAS_CUSTODIAN** *E-01 Legal Entity*.

#### `HAS_BORROWER` — `has-borrower`
- **Direction:** PB-10 Securities Loan &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `BORROWER_IN`
- **Meaning:** The loan or securities-loan names the borrower legal entity.
- **Example:** `PB-10.borrower_entity_id` &rarr; `E-01` reads *PB-10 Securities Loan* **HAS_BORROWER** *E-01 Legal Entity*.

#### `ORIGINATED_BY` — `originated-by`
- **Direction:** PM-14 Direct Loan &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `ORIGINATED`
- **Meaning:** The direct loan was originated by a legal entity.
- **Example:** `PM-14.originator_entity_id` &rarr; `E-01` reads *PM-14 Direct Loan* **ORIGINATED_BY** *E-01 Legal Entity*.

#### `HAS_TARGET_PARTY` — `has-target-party`
- **Direction:** PM-15 Deal / Investment Opportunity &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `TARGET_PARTY_IN`
- **Meaning:** The deal names its target company as a legal entity.
- **Example:** `PM-15.target_entity_id` &rarr; `E-01` reads *PM-15 Deal / Investment Opportunity* **HAS_TARGET_PARTY** *E-01 Legal Entity*.

#### `HAS_TENANT` — `has-tenant`
- **Direction:** RA-03 Lease / Tenancy &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `TENANT_OF`
- **Meaning:** The lease names the tenant legal entity.
- **Example:** `RA-03.tenant_entity_id` &rarr; `E-01` reads *RA-03 Lease / Tenancy* **HAS_TENANT** *E-01 Legal Entity*.

#### `HAS_CONTRACTOR` — `has-contractor`
- **Direction:** RA-04 Development Project &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `CONTRACTOR_FOR`
- **Meaning:** The development project names the contractor legal entity.
- **Example:** `RA-04.contractor_entity_id` &rarr; `E-01` reads *RA-04 Development Project* **HAS_CONTRACTOR** *E-01 Legal Entity*.

#### `HAS_CONCESSION_GRANTOR` — `has-concession-grantor`
- **Direction:** RA-04 Development Project &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `CONCESSION_GRANTOR_FOR`
- **Meaning:** The development project names the concession-granting legal entity.
- **Example:** `RA-04.concession_grantor_id` &rarr; `E-01` reads *RA-04 Development Project* **HAS_CONCESSION_GRANTOR** *E-01 Legal Entity*.

#### `VALUED_BY` — `valued-by`
- **Direction:** RA-05 Asset Appraisal &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `VALUER_OF`
- **Meaning:** The appraisal names the valuer legal entity.
- **Example:** `RA-05.valuer_entity_id` &rarr; `E-01` reads *RA-05 Asset Appraisal* **VALUED_BY** *E-01 Legal Entity*.

#### `HAS_PREDECESSOR_GP` — `has-predecessor-gp`
- **Direction:** PM-11 Manager Succession Event &rarr; PM-02 GP / Management Company
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `PREDECESSOR_GP_IN`
- **Meaning:** The succession event names the predecessor GP.
- **Example:** `PM-11.predecessor_gp_id` &rarr; `PM-02` reads *PM-11 Manager Succession Event* **HAS_PREDECESSOR_GP** *PM-02 GP / Management Company*.

#### `HAS_SUCCESSOR_GP` — `has-successor-gp`
- **Direction:** PM-11 Manager Succession Event &rarr; PM-02 GP / Management Company
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `SUCCESSOR_GP_IN`
- **Meaning:** The succession event names the successor GP.
- **Example:** `PM-11.successor_gp_id` &rarr; `PM-02` reads *PM-11 Manager Succession Event* **HAS_SUCCESSOR_GP** *PM-02 GP / Management Company*.

### Instruments and positions

#### `POSITION_IN` — `position-in`
- **Direction:** E-04 Holding / Position &rarr; E-02 Instrument / Asset
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `HAS_POSITION`
- **Meaning:** The holding is a position in an instrument.
- **Example:** `E-04.instrument_id` &rarr; `E-02` reads *E-04 Holding / Position* **POSITION_IN** *E-02 Instrument / Asset*.

#### `ON_INSTRUMENT` — `on-instrument`
- **Direction:** DR-01 Listed Derivative &rarr; E-02 Instrument / Asset
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `INSTRUMENT_IN`
- **Meaning:** The record is about an instrument.
- **Example:** `DR-01.instrument_id` &rarr; `E-02` reads *DR-01 Listed Derivative* **ON_INSTRUMENT** *E-02 Instrument / Asset*.

#### `UNDERLYING_IS` — `underlying-is`
- **Direction:** DR-01 Listed Derivative &rarr; E-02 Instrument / Asset
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `UNDERLYING_INSTRUMENT_OF`
- **Meaning:** The derivative's underlying is an instrument.
- **Example:** `DR-01.underlying_instrument_id` &rarr; `E-02` reads *DR-01 Listed Derivative* **UNDERLYING_IS** *E-02 Instrument / Asset*.

#### `UNDERLYING_INDEX_IS` — `underlying-index-is`
- **Direction:** DR-01 Listed Derivative &rarr; E-10 Benchmark / Index
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `UNDERLYING_INDEX_OF`
- **Meaning:** The derivative's underlying reference is an index.
- **Example:** `DR-01.underlying_reference` &rarr; `E-10` reads *DR-01 Listed Derivative* **UNDERLYING_INDEX_IS** *E-10 Benchmark / Index*.

#### `RESULTS_IN_INSTRUMENT` — `results-in-instrument`
- **Direction:** PB-07 Corporate Action &rarr; E-02 Instrument / Asset
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `RESULT_INSTRUMENT_OF`
- **Meaning:** The corporate action results in an instrument.
- **Example:** `PB-07.resulting_instrument_id` &rarr; `E-02` reads *PB-07 Corporate Action* **RESULTS_IN_INSTRUMENT** *E-02 Instrument / Asset*.

#### `VALUATION_OF` — `valuation-of`
- **Direction:** E-07 Valuation &rarr; E-04 Holding / Position
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `HAS_VALUATION`
- **Meaning:** The valuation is of a holding or position.
- **Example:** `E-07.position_id` &rarr; `E-04` reads *E-07 Valuation* **VALUATION_OF** *E-04 Holding / Position*.

#### `LENDS_POSITION` — `lends-position`
- **Direction:** PB-10 Securities Loan &rarr; E-04 Holding / Position
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `POSITION_LENT_AS`
- **Meaning:** The securities loan lends a held position.
- **Example:** `PB-10.position_id` &rarr; `E-04` reads *PB-10 Securities Loan* **LENDS_POSITION** *E-04 Holding / Position*.

#### `COLLATERALISED_BY` — `collateralised-by`
- **Direction:** PB-10 Securities Loan &rarr; E-26 Collateral Position
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `COLLATERAL_FOR`
- **Meaning:** The securities loan is collateralised by a collateral position.
- **Example:** `PB-10.collateral_position_id` &rarr; `E-26` reads *PB-10 Securities Loan* **COLLATERALISED_BY** *E-26 Collateral Position*.

### Portfolios, mandates and benchmarks

#### `IN_PORTFOLIO` — `in-portfolio`
- **Direction:** E-04 Holding / Position &rarr; E-03 Portfolio / Mandate
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `PORTFOLIO_INCLUDES`
- **Meaning:** The record belongs to a portfolio or mandate.
- **Example:** `E-04.portfolio_id` &rarr; `E-03` reads *E-04 Holding / Position* **IN_PORTFOLIO** *E-03 Portfolio / Mandate*.

#### `LINKED_TO_PORTFOLIO` — `linked-to-portfolio`
- **Direction:** E-25 Account &rarr; E-03 Portfolio / Mandate
- **Kind:** reference
- **Cardinality:** n-to-n
- **Inverse:** `PORTFOLIO_LINKED_TO`
- **Meaning:** The account is linked to one or more portfolios.
- **Example:** `E-25.portfolio_links` &rarr; `E-03` reads *E-25 Account* **LINKED_TO_PORTFOLIO** *E-03 Portfolio / Mandate*.

#### `APPLIES_TO_PORTFOLIO` — `applies-to-portfolio`
- **Direction:** E-29 Allocation Plan &rarr; E-03 Portfolio / Mandate
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `HAS_ALLOCATION_PLAN`
- **Meaning:** The allocation plan governs a portfolio or pool.
- **Example:** `E-29.subject_id` &rarr; `E-03` reads *E-29 Allocation Plan* **APPLIES_TO_PORTFOLIO** *E-03 Portfolio / Mandate*.

#### `GOVERNED_BY_PLAN` — `governed-by-plan`
- **Direction:** E-03 Portfolio / Mandate &rarr; E-29 Allocation Plan
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `PLAN_GOVERNS`
- **Meaning:** The portfolio is governed by the allocation-plan version currently in force. The reverse of `APPLIES_TO_PORTFOLIO`/`HAS_ALLOCATION_PLAN` in meaning but a distinct edge: `E-29.subject_id` is carried on every plan *version* (traversing it yields the full version history), whereas `E-03.governing_plan_id` points only at the single *in-force* version.
- **Example:** `E-03.governing_plan_id` &rarr; `E-29` reads *E-03 Portfolio / Mandate* **GOVERNED_BY_PLAN** *E-29 Allocation Plan*.

#### `FUNDED_BY_PORTFOLIO` — `funded-by-portfolio`
- **Direction:** E-30 Goal &rarr; E-03 Portfolio / Mandate
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `FUNDS_GOAL`
- **Meaning:** The goal is funded by a portfolio.
- **Example:** `E-30.funding_portfolio_id` &rarr; `E-03` reads *E-30 Goal* **FUNDED_BY_PORTFOLIO** *E-03 Portfolio / Mandate*.

#### `BENCHMARKED_TO` — `benchmarked-to`
- **Direction:** E-03 Portfolio / Mandate &rarr; E-10 Benchmark / Index
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `BENCHMARK_FOR`
- **Meaning:** The portfolio is benchmarked to an index.
- **Example:** `E-03.benchmark_id` &rarr; `E-10` reads *E-03 Portfolio / Mandate* **BENCHMARKED_TO** *E-10 Benchmark / Index*.

### Transactions and cash

#### `FROM_TRANSACTION` — `from-transaction`
- **Direction:** E-06 Cash Flow Event &rarr; E-05 Transaction
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `GENERATES`
- **Meaning:** The record arises from a transaction.
- **Example:** `E-06.transaction_id` &rarr; `E-05` reads *E-06 Cash Flow Event* **FROM_TRANSACTION** *E-05 Transaction*.

#### `ACQUIRED_VIA` — `acquired-via`
- **Direction:** E-32 Tax Lot &rarr; E-05 Transaction
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `ACQUIRES`
- **Meaning:** The tax lot was opened by an acquisition transaction.
- **Example:** `E-32.acquisition_transaction_id` &rarr; `E-05` reads *E-32 Tax Lot* **ACQUIRED_VIA** *E-05 Transaction*.

#### `BOOKED_AS` — `booked-as`
- **Direction:** PB-03 Order &rarr; E-05 Transaction
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `BOOKS`
- **Meaning:** The order is booked as a transaction.
- **Example:** `PB-03.transaction_id` &rarr; `E-05` reads *PB-03 Order* **BOOKED_AS** *E-05 Transaction*.

### Reference data and classification

#### `CLASSIFIED_AS_ASSET_CLASS` — `classified-as-asset-class`
- **Direction:** E-02 Instrument / Asset &rarr; E-09 Asset Class
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `ASSET_CLASS_OF`
- **Meaning:** The record is classified into an asset class.
- **Example:** `E-02.asset_class` &rarr; `E-09` reads *E-02 Instrument / Asset* **CLASSIFIED_AS_ASSET_CLASS** *E-09 Asset Class*.

#### `CONSTITUENT_OF` — `constituent-of`
- **Direction:** PB-09 Index Constituent &rarr; E-10 Benchmark / Index
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `HAS_CONSTITUENT`
- **Meaning:** The constituent belongs to an index.
- **Example:** `PB-09.benchmark_id` &rarr; `E-10` reads *PB-09 Index Constituent* **CONSTITUENT_OF** *E-10 Benchmark / Index*.

#### `REFERENCES_BENCHMARK` — `references-benchmark`
- **Direction:** PM-12 Benchmark Cross-Reference &rarr; E-10 Benchmark / Index
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `BENCHMARK_REFERENCED_BY`
- **Meaning:** The cross-reference maps to a benchmark index.
- **Example:** `PM-12.benchmark_id` &rarr; `E-10` reads *PM-12 Benchmark Cross-Reference* **REFERENCES_BENCHMARK** *E-10 Benchmark / Index*.

#### `HAS_CLASSIFICATION_TYPE` — `has-classification-type`
- **Direction:** E-12 Classification History &rarr; E-11 Classification Type & Value
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `CLASSIFICATION_TYPE_OF`
- **Meaning:** The history row records a classification type.
- **Example:** `E-12.classification_type` &rarr; `E-11` reads *E-12 Classification History* **HAS_CLASSIFICATION_TYPE** *E-11 Classification Type & Value*.

#### `HAS_CLASSIFICATION_VALUE` — `has-classification-value`
- **Direction:** E-12 Classification History &rarr; E-11 Classification Type & Value
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `CLASSIFICATION_VALUE_OF`
- **Meaning:** The history row records a classification value.
- **Example:** `E-12.classification_value` &rarr; `E-11` reads *E-12 Classification History* **HAS_CLASSIFICATION_VALUE** *E-11 Classification Type & Value*.

#### `CLASSIFIED_AS` — `classified-as`
- **Direction:** PB-01 Listed Equity &rarr; E-11 Classification Type & Value
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `CLASSIFIES`
- **Meaning:** The instrument is classified by a classification value.
- **Example:** `PB-01.gics_sector` &rarr; `E-11` reads *PB-01 Listed Equity* **CLASSIFIED_AS** *E-11 Classification Type & Value*.

### Documents, metrics, risk and goals

#### `EXTRACTED_FROM` — `extracted-from`
- **Direction:** E-23 Extraction Record &rarr; E-15 Document Metadata
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `HAS_EXTRACTION_RECORD`
- **Meaning:** The extraction record was parsed from a document.
- **Example:** `E-23.document_id` &rarr; `E-15` reads *E-23 Extraction Record* **EXTRACTED_FROM** *E-15 Document Metadata*.

#### `HAS_DOCUMENT` — `has-document`
- **Direction:** E-34 Investment Authorisation &rarr; E-15 Document Metadata
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `DOCUMENT_FOR`
- **Meaning:** The record references a governing document.
- **Example:** `E-34.ic_memorandum_ref` &rarr; `E-15` reads *E-34 Investment Authorisation* **HAS_DOCUMENT** *E-15 Document Metadata*.

#### `HAS_SUBJECT` — `has-subject`
- **Direction:** E-15 Document Metadata &rarr; E-01 / E-02 / E-03 / E-04 / PM-01 / PM-09
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `SUBJECT_OF`
- **Meaning:** The document concerns a subject entity (6-way polymorphic).
- **Example:** `E-15.subject_id` &rarr; `E-01 / E-02 / E-03 / E-04 / PM-01 / PM-09` reads *E-15 Document Metadata* **HAS_SUBJECT** *E-01 / E-02 / E-03 / E-04 / PM-01 / PM-09*.

#### `BREACH_OF_LIMIT` — `breach-of-limit`
- **Direction:** E-18 Limit Breach &rarr; E-16 Risk Limit
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `HAS_BREACH`
- **Meaning:** The breach is against a risk limit.
- **Example:** `E-18.limit_id` &rarr; `E-16` reads *E-18 Limit Breach* **BREACH_OF_LIMIT** *E-16 Risk Limit*.

#### `UNDER_SCENARIO` — `under-scenario`
- **Direction:** E-19 Risk Measurement &rarr; E-17 Scenario
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `SCENARIO_FOR`
- **Meaning:** The risk measurement is computed under a scenario.
- **Example:** `E-19.scenario_id` &rarr; `E-17` reads *E-19 Risk Measurement* **UNDER_SCENARIO** *E-17 Scenario*.

#### `DETECTED_BY_MEASUREMENT` — `detected-by-measurement`
- **Direction:** E-18 Limit Breach &rarr; E-19 Risk Measurement
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `MEASUREMENT_TRIGGERS`
- **Meaning:** The breach was detected by a risk measurement.
- **Example:** `E-18.measurement_id` &rarr; `E-19` reads *E-18 Limit Breach* **DETECTED_BY_MEASUREMENT** *E-19 Risk Measurement*.

#### `COMPUTED_PER_METRIC` — `computed-per-metric`
- **Direction:** E-20 Performance Result &rarr; E-22 Metric Definition
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `METRIC_FOR`
- **Meaning:** The result is computed per a metric definition.
- **Example:** `E-20.metric_definition_id` &rarr; `E-22` reads *E-20 Performance Result* **COMPUTED_PER_METRIC** *E-22 Metric Definition*.

#### `MEASURES_GOAL` — `measures-goal`
- **Direction:** E-31 Goal Progress Measurement &rarr; E-30 Goal
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `HAS_PROGRESS_MEASUREMENT`
- **Meaning:** The progress measurement measures a goal.
- **Example:** `E-31.goal_id` &rarr; `E-30` reads *E-31 Goal Progress Measurement* **MEASURES_GOAL** *E-30 Goal*.

#### `INCLUDES_GOAL` — `includes-goal`
- **Direction:** E-33 Financial Plan &rarr; E-30 Goal
- **Kind:** reference
- **Cardinality:** n-to-n
- **Inverse:** `GOAL_IN_PLAN`
- **Meaning:** The financial plan includes a set of goals.
- **Example:** `E-33.goal_set` &rarr; `E-30` reads *E-33 Financial Plan* **INCLUDES_GOAL** *E-30 Goal*.

### Funds, commitments and real assets

#### `OF_FUND` — `of-fund`
- **Direction:** PM-06 LP Commitment &rarr; PM-01 Fund & Vehicle
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `FUND_INCLUDES`
- **Meaning:** The record concerns a fund or vehicle.
- **Example:** `PM-06.fund_id` &rarr; `PM-01` reads *PM-06 LP Commitment* **OF_FUND** *PM-01 Fund & Vehicle*.

#### `HELD_THROUGH_VEHICLE` — `held-through-vehicle`
- **Direction:** RA-01 Direct Real Asset &rarr; PM-05 Legal Vehicle / SPV
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `VEHICLE_HOLDS`
- **Meaning:** The real asset is held through a legal vehicle.
- **Example:** `RA-01.holding_vehicle_id` &rarr; `PM-05` reads *RA-01 Direct Real Asset* **HELD_THROUGH_VEHICLE** *PM-05 Legal Vehicle / SPV*.

#### `AGAINST_COMMITMENT` — `against-commitment`
- **Direction:** PM-07 Capital Call &rarr; PM-06 LP Commitment
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `COMMITMENT_HAS`
- **Meaning:** The capital call or distribution is against an LP commitment.
- **Example:** `PM-07.commitment_id` &rarr; `PM-06` reads *PM-07 Capital Call* **AGAINST_COMMITMENT** *PM-06 LP Commitment*.

#### `FOR_INVESTMENT` — `for-investment`
- **Direction:** PM-05 Legal Vehicle / SPV &rarr; PM-09 Fund Investment
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `INVESTMENT_HELD_VIA`
- **Meaning:** The legal vehicle is held for a fund investment.
- **Example:** `PM-05.investment_id` &rarr; `PM-09` reads *PM-05 Legal Vehicle / SPV* **FOR_INVESTMENT** *PM-09 Fund Investment*.

#### `HOLDS_INTEREST_IN` — `holds-interest-in`
- **Direction:** PM-09 Fund Investment &rarr; PM-04 / PM-01
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `HELD_VIA_INVESTMENT`
- **Meaning:** The fund investment holds an interest in a company or fund (2-way polymorphic).
- **Example:** `PM-09.target_id` &rarr; `PM-04 / PM-01` reads *PM-09 Fund Investment* **HOLDS_INTEREST_IN** *PM-04 / PM-01*.

#### `ON_REAL_ASSET` — `on-real-asset`
- **Direction:** RA-02 Asset Operating Record &rarr; RA-01 Direct Real Asset
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `REAL_ASSET_HAS`
- **Meaning:** The operating record, lease, project or appraisal is on a real asset.
- **Example:** `RA-02.real_asset_id` &rarr; `RA-01` reads *RA-02 Asset Operating Record* **ON_REAL_ASSET** *RA-01 Direct Real Asset*.

### Fund products, share classes and dealing

#### `BELONGS_TO_FUND_PRODUCT` — `belongs-to-fund-product`
- **Direction:** FO-02 Share / Unit Class &rarr; FO-01 Fund Product
- **Kind:** composition
- **Cardinality:** n-to-1
- **Inverse:** `FUND_PRODUCT_INCLUDES`
- **Meaning:** The record belongs to an issued fund product.
- **Example:** `FO-02.fund_product_id` &rarr; `FO-01` reads *FO-02 Share / Unit Class* **BELONGS_TO_FUND_PRODUCT** *FO-01 Fund Product*.

#### `OF_SHARE_CLASS` — `of-share-class`
- **Direction:** E-07 Valuation &rarr; FO-02 Share / Unit Class
- **Kind:** composition
- **Cardinality:** n-to-1
- **Inverse:** `SHARE_CLASS_INCLUDES`
- **Meaning:** The record belongs to a share or unit class.
- **Example:** `E-07.unit_class_id` &rarr; `FO-02` reads *E-07 Valuation* **OF_SHARE_CLASS** *FO-02 Share / Unit Class*.

#### `ON_UNITHOLDING` — `on-unitholding`
- **Direction:** FO-04 Dealing Order &rarr; FO-03 Investor Unitholding
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `UNITHOLDING_HAS`
- **Meaning:** The dealing or statement is on an investor unitholding.
- **Example:** `FO-04.unitholding_id` &rarr; `FO-03` reads *FO-04 Dealing Order* **ON_UNITHOLDING** *FO-03 Investor Unitholding*.

#### `USES_BASKET` — `uses-basket`
- **Direction:** FO-10 ETF Creation/Redemption Order &rarr; FO-11 ETF Creation Basket (Portfolio Composition File)
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `BASKET_FOR`
- **Meaning:** The creation order uses an ETF creation basket.
- **Example:** `FO-10.basket_id` &rarr; `FO-11` reads *FO-10 ETF Creation/Redemption Order* **USES_BASKET** *FO-11 ETF Creation Basket (Portfolio Composition File)*.

#### `UNDER_AP_AGREEMENT` — `under-ap-agreement`
- **Direction:** FO-10 ETF Creation/Redemption Order &rarr; FO-12 ETF Authorised-Participant Agreement
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `AP_AGREEMENT_FOR`
- **Meaning:** The creation order is placed under an AP agreement.
- **Example:** `FO-10.ap_agreement_id` &rarr; `FO-12` reads *FO-10 ETF Creation/Redemption Order* **UNDER_AP_AGREEMENT** *FO-12 ETF Authorised-Participant Agreement*.

### Orders, execution and voting

#### `FOR_ORDER` — `for-order`
- **Direction:** PB-04 Execution &rarr; PB-03 Order
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `ORDER_FULFILLED_BY`
- **Meaning:** The execution or allocation is for an order.
- **Example:** `PB-04.order_id` &rarr; `PB-03` reads *PB-04 Execution* **FOR_ORDER** *PB-03 Order*.

#### `FOR_ALLOCATION` — `for-allocation`
- **Direction:** PB-06 Settlement Instruction &rarr; PB-05 Allocation
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `ALLOCATION_SETTLED_BY`
- **Meaning:** The settlement instruction is for an allocation.
- **Example:** `PB-06.allocation_id` &rarr; `PB-05` reads *PB-06 Settlement Instruction* **FOR_ALLOCATION** *PB-05 Allocation*.

#### `AT_MEETING` — `at-meeting`
- **Direction:** PB-11 Proxy Vote &rarr; PB-07 Corporate Action
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `MEETING_HAS_VOTE`
- **Meaning:** The proxy vote is cast at a meeting corporate-action.
- **Example:** `PB-11.meeting_id` &rarr; `PB-07` reads *PB-11 Proxy Vote* **AT_MEETING** *PB-07 Corporate Action*.

### Derivative agreements

#### `UNDER_MASTER_AGREEMENT` — `under-master-agreement`
- **Direction:** DR-02 OTC Derivative &rarr; DR-03 Master Agreement & Collateral Terms
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `MASTER_AGREEMENT_GOVERNS`
- **Meaning:** The OTC derivative or margin balance sits under a master agreement.
- **Example:** `DR-02.master_agreement_id` &rarr; `DR-03` reads *DR-02 OTC Derivative* **UNDER_MASTER_AGREEMENT** *DR-03 Master Agreement & Collateral Terms*.

#### `UNDER_CLEARING_RELATIONSHIP` — `under-clearing-relationship`
- **Direction:** DR-04 Margin & Collateral Balance &rarr; DR-05 Clearing Relationship
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `CLEARING_RELATIONSHIP_COVERS`
- **Meaning:** The margin balance sits under a clearing relationship.
- **Example:** `DR-04.clearing_relationship_id` &rarr; `DR-05` reads *DR-04 Margin & Collateral Balance* **UNDER_CLEARING_RELATIONSHIP** *DR-05 Clearing Relationship*.

#### `ANNEXED_TO` — `annexed-to`
- **Direction:** DR-03 Master Agreement & Collateral Terms &rarr; DR-03 Master Agreement & Collateral Terms
- **Kind:** composition
- **Cardinality:** n-to-1
- **Inverse:** `HAS_ANNEX`
- **Meaning:** The CSA is annexed to the master agreement (intra-entity self).
- **Example:** `DR-03.master_agreement_id` &rarr; `DR-03` reads *DR-03 Master Agreement & Collateral Terms* **ANNEXED_TO** *DR-03 Master Agreement & Collateral Terms*.

### Self-referential, hierarchy and versioning

#### `SUBSIDIARY_OF` — `subsidiary-of`
- **Direction:** E-01 Legal Entity &rarr; E-01 Legal Entity
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `PARENT_ENTITY_OF`
- **Meaning:** The legal entity is a subsidiary of a parent legal entity (self).
- **Example:** `E-01.parent_entity_id` &rarr; `E-01` reads *E-01 Legal Entity* **SUBSIDIARY_OF** *E-01 Legal Entity*.

#### `RELATED_TO_PARTY` — `related-to-party`
- **Direction:** E-01 Legal Entity &rarr; E-01 Legal Entity
- **Kind:** role
- **Cardinality:** n-to-1
- **Inverse:** `RELATED_PARTY_OF`
- **Meaning:** The legal entity has a typed party-to-party relationship to another legal entity *beyond* the corporate parent hierarchy (self). The `E-01.party_relationship_type` discriminator names the relationship — `manager_of` / `successor_of` / `guarantor_of`. Distinct from `SUBSIDIARY_OF`, which carries only the ownership hierarchy.
- **Example:** `E-01.related_entity_id` &rarr; `E-01` reads *E-01 Legal Entity* **RELATED_TO_PARTY** *E-01 Legal Entity*.

#### `SUB_PORTFOLIO_OF` — `sub-portfolio-of`
- **Direction:** E-03 Portfolio / Mandate &rarr; E-03 Portfolio / Mandate
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `PARENT_PORTFOLIO_OF`
- **Meaning:** The portfolio is a sub-portfolio of a parent portfolio (self).
- **Example:** `E-03.parent_portfolio_id` &rarr; `E-03` reads *E-03 Portfolio / Mandate* **SUB_PORTFOLIO_OF** *E-03 Portfolio / Mandate*.

#### `SUPERSEDED_BY` — `superseded-by`
- **Direction:** E-11 Classification Type & Value &rarr; E-11 Classification Type & Value
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `SUPERSEDES`
- **Meaning:** The classification value is superseded by a newer value (self).
- **Example:** `E-11.superseded_by_key` &rarr; `E-11` reads *E-11 Classification Type & Value* **SUPERSEDED_BY** *E-11 Classification Type & Value*.

#### `SUBFUND_OF` — `subfund-of`
- **Direction:** FO-01 Fund Product &rarr; FO-01 Fund Product
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `UMBRELLA_OF`
- **Meaning:** The fund product is a sub-fund of an umbrella fund (self).
- **Example:** `FO-01.umbrella_fund_id` &rarr; `FO-01` reads *FO-01 Fund Product* **SUBFUND_OF** *FO-01 Fund Product*.

#### `CORRECTS` — `corrects`
- **Direction:** FO-07 Investor Tax Statement &rarr; FO-07 Investor Tax Statement
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `CORRECTED_BY`
- **Meaning:** The tax statement corrects a prior statement (self).
- **Example:** `FO-07.corrects_statement_id` &rarr; `FO-07` reads *FO-07 Investor Tax Statement* **CORRECTS** *FO-07 Investor Tax Statement*.

#### `CHILD_ORDER_OF` — `child-order-of`
- **Direction:** PB-03 Order &rarr; PB-03 Order
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `PARENT_ORDER_OF`
- **Meaning:** The order is a child of a parent order (self).
- **Example:** `PB-03.parent_order_id` &rarr; `PB-03` reads *PB-03 Order* **CHILD_ORDER_OF** *PB-03 Order*.

#### `SUCCEEDED_BY` — `succeeded-by`
- **Direction:** PM-04 Portfolio Company &rarr; PM-04 Portfolio Company
- **Kind:** reference
- **Cardinality:** n-to-1
- **Inverse:** `SUCCEEDS`
- **Meaning:** The portfolio company is succeeded by another (self).
- **Example:** `PM-04.successor_company_id` &rarr; `PM-04` reads *PM-04 Portfolio Company* **SUCCEEDED_BY** *PM-04 Portfolio Company*.

#### `VALUE_OF_TYPE` — `value-of-type`
- **Direction:** E-11 Classification Type & Value &rarr; E-11 Classification Type & Value
- **Kind:** composition
- **Cardinality:** n-to-1
- **Inverse:** `TYPE_HAS_VALUE`
- **Meaning:** The classification value belongs to a classification type (intra-entity self).
- **Example:** `E-11.classification_type_key` &rarr; `E-11` reads *E-11 Classification Type & Value* **VALUE_OF_TYPE** *E-11 Classification Type & Value*.

#### `IN_FUND_FAMILY` — `in-fund-family`
- **Direction:** PM-01 Fund & Vehicle &rarr; PM-01 Fund & Vehicle
- **Kind:** composition
- **Cardinality:** n-to-1
- **Inverse:** `FAMILY_INCLUDES`
- **Meaning:** The vehicle belongs to a fund family (intra-entity self).
- **Example:** `PM-01.fund_family_id` &rarr; `PM-01` reads *PM-01 Fund & Vehicle* **IN_FUND_FAMILY** *PM-01 Fund & Vehicle*.

#### `UNDER_TERMS_VERSION` — `under-terms-version`
- **Direction:** PM-10 Fund Terms &rarr; PM-10 Fund Terms
- **Kind:** composition
- **Cardinality:** n-to-1
- **Inverse:** `TERMS_VERSION_HAS`
- **Meaning:** The economic term sits under a versioned fund-terms parent (intra-entity self).
- **Example:** `PM-10.terms_id` &rarr; `PM-10` reads *PM-10 Fund Terms* **UNDER_TERMS_VERSION** *PM-10 Fund Terms*.

## The relation verbs at a glance

| Verb (LPG) | OWL super-property | Inverse | Kind | Cardinality |
|---|---|---|---|---|
| `SPECIALISES` | `specialises` | `SPECIALISED_BY` | is-a | n-to-1 |
| `ISSUED_BY` | `issued-by` | `ISSUER_OF` | role | n-to-1 |
| `MANAGED_BY` | `managed-by` | `MANAGES` | role | n-to-1 |
| `MANAGED_BY_GP` | `managed-by-gp` | `GP_MANAGES` | role | n-to-1 |
| `HAS_COUNTERPARTY` | `has-counterparty` | `COUNTERPARTY_IN` | role | n-to-1 |
| `HAS_INVESTOR` | `has-investor` | `INVESTOR_IN` | role | n-to-1 |
| `HELD_BY` | `held-by` | `HOLDER_OF` | role | n-to-1 |
| `CLEARED_THROUGH` | `cleared-through` | `CLEARS` | role | n-to-1 |
| `LISTED_ON` | `listed-on` | `LISTS` | role | n-to-1 |
| `HAS_CLEARING_BROKER` | `has-clearing-broker` | `CLEARING_BROKER_FOR` | role | n-to-1 |
| `ADMINISTERED_BY` | `administered-by` | `ADMINISTERS` | role | n-to-1 |
| `HAS_FUND_ADMINISTRATOR` | `has-fund-administrator` | `FUND_ADMINISTRATOR_OF` | role | n-to-1 |
| `FOR_PARTY` | `for-party` | `PARTY_OF` | role | n-to-1 |
| `PROVIDED_BY` | `provided-by` | `PROVIDES` | role | n-to-1 |
| `DELEGATES_TO` | `delegates-to` | `DELEGATED_FROM` | role | n-to-1 |
| `VIA_INTERMEDIARY` | `via-intermediary` | `INTERMEDIARY_FOR` | role | n-to-1 |
| `HAS_AUTHORISED_PARTICIPANT` | `has-authorised-participant` | `AUTHORISED_PARTICIPANT_FOR` | role | n-to-1 |
| `VIA_BROKER` | `via-broker` | `BROKER_FOR` | role | n-to-1 |
| `HAS_CUSTODIAN` | `has-custodian` | `CUSTODIAN_FOR` | role | n-to-1 |
| `HAS_BORROWER` | `has-borrower` | `BORROWER_IN` | role | n-to-1 |
| `ORIGINATED_BY` | `originated-by` | `ORIGINATED` | role | n-to-1 |
| `HAS_TARGET_PARTY` | `has-target-party` | `TARGET_PARTY_IN` | role | n-to-1 |
| `HAS_TENANT` | `has-tenant` | `TENANT_OF` | role | n-to-1 |
| `HAS_CONTRACTOR` | `has-contractor` | `CONTRACTOR_FOR` | role | n-to-1 |
| `HAS_CONCESSION_GRANTOR` | `has-concession-grantor` | `CONCESSION_GRANTOR_FOR` | role | n-to-1 |
| `VALUED_BY` | `valued-by` | `VALUER_OF` | role | n-to-1 |
| `HAS_PREDECESSOR_GP` | `has-predecessor-gp` | `PREDECESSOR_GP_IN` | role | n-to-1 |
| `HAS_SUCCESSOR_GP` | `has-successor-gp` | `SUCCESSOR_GP_IN` | role | n-to-1 |
| `POSITION_IN` | `position-in` | `HAS_POSITION` | reference | n-to-1 |
| `ON_INSTRUMENT` | `on-instrument` | `INSTRUMENT_IN` | reference | n-to-1 |
| `UNDERLYING_IS` | `underlying-is` | `UNDERLYING_INSTRUMENT_OF` | reference | n-to-1 |
| `UNDERLYING_INDEX_IS` | `underlying-index-is` | `UNDERLYING_INDEX_OF` | reference | n-to-1 |
| `RESULTS_IN_INSTRUMENT` | `results-in-instrument` | `RESULT_INSTRUMENT_OF` | reference | n-to-1 |
| `VALUATION_OF` | `valuation-of` | `HAS_VALUATION` | reference | n-to-1 |
| `LENDS_POSITION` | `lends-position` | `POSITION_LENT_AS` | reference | n-to-1 |
| `COLLATERALISED_BY` | `collateralised-by` | `COLLATERAL_FOR` | reference | n-to-1 |
| `IN_PORTFOLIO` | `in-portfolio` | `PORTFOLIO_INCLUDES` | reference | n-to-1 |
| `LINKED_TO_PORTFOLIO` | `linked-to-portfolio` | `PORTFOLIO_LINKED_TO` | reference | n-to-n |
| `APPLIES_TO_PORTFOLIO` | `applies-to-portfolio` | `HAS_ALLOCATION_PLAN` | reference | n-to-1 |
| `GOVERNED_BY_PLAN` | `governed-by-plan` | `PLAN_GOVERNS` | reference | n-to-1 |
| `FUNDED_BY_PORTFOLIO` | `funded-by-portfolio` | `FUNDS_GOAL` | reference | n-to-1 |
| `BENCHMARKED_TO` | `benchmarked-to` | `BENCHMARK_FOR` | reference | n-to-1 |
| `FROM_TRANSACTION` | `from-transaction` | `GENERATES` | reference | n-to-1 |
| `ACQUIRED_VIA` | `acquired-via` | `ACQUIRES` | reference | n-to-1 |
| `BOOKED_AS` | `booked-as` | `BOOKS` | reference | n-to-1 |
| `CLASSIFIED_AS_ASSET_CLASS` | `classified-as-asset-class` | `ASSET_CLASS_OF` | reference | n-to-1 |
| `CONSTITUENT_OF` | `constituent-of` | `HAS_CONSTITUENT` | reference | n-to-1 |
| `REFERENCES_BENCHMARK` | `references-benchmark` | `BENCHMARK_REFERENCED_BY` | reference | n-to-1 |
| `HAS_CLASSIFICATION_TYPE` | `has-classification-type` | `CLASSIFICATION_TYPE_OF` | reference | n-to-1 |
| `HAS_CLASSIFICATION_VALUE` | `has-classification-value` | `CLASSIFICATION_VALUE_OF` | reference | n-to-1 |
| `CLASSIFIED_AS` | `classified-as` | `CLASSIFIES` | reference | n-to-1 |
| `EXTRACTED_FROM` | `extracted-from` | `HAS_EXTRACTION_RECORD` | reference | n-to-1 |
| `HAS_DOCUMENT` | `has-document` | `DOCUMENT_FOR` | reference | n-to-1 |
| `HAS_SUBJECT` | `has-subject` | `SUBJECT_OF` | reference | n-to-1 |
| `BREACH_OF_LIMIT` | `breach-of-limit` | `HAS_BREACH` | reference | n-to-1 |
| `UNDER_SCENARIO` | `under-scenario` | `SCENARIO_FOR` | reference | n-to-1 |
| `DETECTED_BY_MEASUREMENT` | `detected-by-measurement` | `MEASUREMENT_TRIGGERS` | reference | n-to-1 |
| `COMPUTED_PER_METRIC` | `computed-per-metric` | `METRIC_FOR` | reference | n-to-1 |
| `MEASURES_GOAL` | `measures-goal` | `HAS_PROGRESS_MEASUREMENT` | reference | n-to-1 |
| `INCLUDES_GOAL` | `includes-goal` | `GOAL_IN_PLAN` | reference | n-to-n |
| `OF_FUND` | `of-fund` | `FUND_INCLUDES` | reference | n-to-1 |
| `HELD_THROUGH_VEHICLE` | `held-through-vehicle` | `VEHICLE_HOLDS` | reference | n-to-1 |
| `AGAINST_COMMITMENT` | `against-commitment` | `COMMITMENT_HAS` | reference | n-to-1 |
| `FOR_INVESTMENT` | `for-investment` | `INVESTMENT_HELD_VIA` | reference | n-to-1 |
| `HOLDS_INTEREST_IN` | `holds-interest-in` | `HELD_VIA_INVESTMENT` | reference | n-to-1 |
| `ON_REAL_ASSET` | `on-real-asset` | `REAL_ASSET_HAS` | reference | n-to-1 |
| `BELONGS_TO_FUND_PRODUCT` | `belongs-to-fund-product` | `FUND_PRODUCT_INCLUDES` | composition | n-to-1 |
| `OF_SHARE_CLASS` | `of-share-class` | `SHARE_CLASS_INCLUDES` | composition | n-to-1 |
| `ON_UNITHOLDING` | `on-unitholding` | `UNITHOLDING_HAS` | reference | n-to-1 |
| `USES_BASKET` | `uses-basket` | `BASKET_FOR` | reference | n-to-1 |
| `UNDER_AP_AGREEMENT` | `under-ap-agreement` | `AP_AGREEMENT_FOR` | reference | n-to-1 |
| `FOR_ORDER` | `for-order` | `ORDER_FULFILLED_BY` | reference | n-to-1 |
| `FOR_ALLOCATION` | `for-allocation` | `ALLOCATION_SETTLED_BY` | reference | n-to-1 |
| `AT_MEETING` | `at-meeting` | `MEETING_HAS_VOTE` | reference | n-to-1 |
| `UNDER_MASTER_AGREEMENT` | `under-master-agreement` | `MASTER_AGREEMENT_GOVERNS` | reference | n-to-1 |
| `UNDER_CLEARING_RELATIONSHIP` | `under-clearing-relationship` | `CLEARING_RELATIONSHIP_COVERS` | reference | n-to-1 |
| `ANNEXED_TO` | `annexed-to` | `HAS_ANNEX` | composition | n-to-1 |
| `SUBSIDIARY_OF` | `subsidiary-of` | `PARENT_ENTITY_OF` | reference | n-to-1 |
| `RELATED_TO_PARTY` | `related-to-party` | `RELATED_PARTY_OF` | role | n-to-1 |
| `SUB_PORTFOLIO_OF` | `sub-portfolio-of` | `PARENT_PORTFOLIO_OF` | reference | n-to-1 |
| `SUPERSEDED_BY` | `superseded-by` | `SUPERSEDES` | reference | n-to-1 |
| `SUBFUND_OF` | `subfund-of` | `UMBRELLA_OF` | reference | n-to-1 |
| `CORRECTS` | `corrects` | `CORRECTED_BY` | reference | n-to-1 |
| `CHILD_ORDER_OF` | `child-order-of` | `PARENT_ORDER_OF` | reference | n-to-1 |
| `SUCCEEDED_BY` | `succeeded-by` | `SUCCEEDS` | reference | n-to-1 |
| `VALUE_OF_TYPE` | `value-of-type` | `TYPE_HAS_VALUE` | composition | n-to-1 |
| `IN_FUND_FAMILY` | `in-fund-family` | `FAMILY_INCLUDES` | composition | n-to-1 |
| `UNDER_TERMS_VERSION` | `under-terms-version` | `TERMS_VERSION_HAS` | composition | n-to-1 |

## The mapping

Every foreign-key column and every specialisation line in the entity model, bound to exactly one relation verb. This table is the reconciliation surface: a column that appears in the model but not here is a defect. The **self-referential** edges (a column that resolves to its own entity, in either notation) and the two **polymorphic** edges (one column resolving to several entity types by a discriminator) are bound here too, and explained under [edges that need care](#edges-that-need-care).

| Binding | Target | Verb | Kind |
|---|---|---|---|
| `DR-01.ccp_entity_id` | `E-01` | `CLEARED_THROUGH` | role |
| `DR-01.exchange_entity_id` | `E-01` | `LISTED_ON` | role |
| `DR-01.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `DR-01.underlying_instrument_id` | `E-02` | `UNDERLYING_IS` | reference |
| `DR-01.underlying_reference` | `E-10` | `UNDERLYING_INDEX_IS` | reference |
| `DR-02.counterparty_entity_id` | `E-01` | `HAS_COUNTERPARTY` | role |
| `DR-02.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `DR-02.master_agreement_id` | `DR-03` | `UNDER_MASTER_AGREEMENT` | reference |
| `DR-02.underlying_instrument_id` | `E-02` | `UNDERLYING_IS` | reference |
| `DR-02.underlying_reference` | `E-10` | `UNDERLYING_INDEX_IS` | reference |
| `DR-03.counterparty_entity_id` | `E-01` | `HAS_COUNTERPARTY` | role |
| `DR-03.investor_entity_id` | `E-01` | `HAS_INVESTOR` | role |
| `DR-03.master_agreement_id` | `DR-03` | `ANNEXED_TO` | composition |
| `DR-04.clearing_relationship_id` | `DR-05` | `UNDER_CLEARING_RELATIONSHIP` | reference |
| `DR-04.master_agreement_id` | `DR-03` | `UNDER_MASTER_AGREEMENT` | reference |
| `DR-05.ccp_entity_id` | `E-01` | `CLEARED_THROUGH` | role |
| `DR-05.clearing_broker_entity_id` | `E-01` | `HAS_CLEARING_BROKER` | role |
| `DR-05.investor_entity_id` | `E-01` | `HAS_INVESTOR` | role |
| `E-01.parent_entity_id` | `E-01` | `SUBSIDIARY_OF` | reference |
| `E-01.related_entity_id` | `E-01` | `RELATED_TO_PARTY` | role |
| `E-02.asset_class` | `E-09` | `CLASSIFIED_AS_ASSET_CLASS` | reference |
| `E-02.issuer_entity_id` | `E-01` | `ISSUED_BY` | role |
| `E-03.asset_class` | `E-09` | `CLASSIFIED_AS_ASSET_CLASS` | reference |
| `E-03.benchmark_id` | `E-10` | `BENCHMARKED_TO` | reference |
| `E-03.governing_plan_id` | `E-29` | `GOVERNED_BY_PLAN` | reference |
| `E-03.managed_by_entity_id` | `E-01` | `MANAGED_BY` | role |
| `E-03.parent_portfolio_id` | `E-03` | `SUB_PORTFOLIO_OF` | reference |
| `E-04.instrument_id` | `E-02` | `POSITION_IN` | reference |
| `E-04.portfolio_id` | `E-03` | `IN_PORTFOLIO` | reference |
| `E-05.counterparty_entity_id` | `E-01` | `HAS_COUNTERPARTY` | role |
| `E-05.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `E-05.portfolio_id` | `E-03` | `IN_PORTFOLIO` | reference |
| `E-06.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `E-06.portfolio_id` | `E-03` | `IN_PORTFOLIO` | reference |
| `E-06.transaction_id` | `E-05` | `FROM_TRANSACTION` | reference |
| `E-07.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `E-07.position_id` | `E-04` | `VALUATION_OF` | reference |
| `E-07.unit_class_id` | `FO-02` | `OF_SHARE_CLASS` | composition |
| `E-08.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `E-10.asset_class` | `E-09` | `CLASSIFIED_AS_ASSET_CLASS` | reference |
| `E-11.classification_type_key` | `E-11` | `VALUE_OF_TYPE` | composition |
| `E-11.superseded_by_key` | `E-11` | `SUPERSEDED_BY` | reference |
| `E-12.classification_type` | `E-11` | `HAS_CLASSIFICATION_TYPE` | reference |
| `E-12.classification_value` | `E-11` | `HAS_CLASSIFICATION_VALUE` | reference |
| `E-15.subject_id` | E-01 / E-02 / E-03 / E-04 / PM-01 / PM-09 | `HAS_SUBJECT` | reference |
| `E-18.limit_id` | `E-16` | `BREACH_OF_LIMIT` | reference |
| `E-18.measurement_id` | `E-19` | `DETECTED_BY_MEASUREMENT` | reference |
| `E-19.scenario_id` | `E-17` | `UNDER_SCENARIO` | reference |
| `E-20.metric_definition_id` | `E-22` | `COMPUTED_PER_METRIC` | reference |
| `E-23.document_id` | `E-15` | `EXTRACTED_FROM` | reference |
| `E-25.holder_entity_id` | `E-01` | `HELD_BY` | role |
| `E-25.portfolio_links` | `E-03` | `LINKED_TO_PORTFOLIO` | reference |
| `E-26.collateral_instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `E-26.counterparty_entity_id` | `E-01` | `HAS_COUNTERPARTY` | role |
| `E-29.subject_id` | `E-03` | `APPLIES_TO_PORTFOLIO` | reference |
| `E-30.funding_portfolio_id` | `E-03` | `FUNDED_BY_PORTFOLIO` | reference |
| `E-30.household_entity_id` | `E-01` | `FOR_PARTY` | role |
| `E-31.goal_id` | `E-30` | `MEASURES_GOAL` | reference |
| `E-31.metric_definition_id` | `E-22` | `COMPUTED_PER_METRIC` | reference |
| `E-32.acquisition_transaction_id` | `E-05` | `ACQUIRED_VIA` | reference |
| `E-32.client_entity_id` | `E-01` | `FOR_PARTY` | role |
| `E-32.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `E-33.goal_set` | `E-30` | `INCLUDES_GOAL` | reference |
| `E-33.household_entity_id` | `E-01` | `FOR_PARTY` | role |
| `E-34.ic_memorandum_ref` | `E-15` | `HAS_DOCUMENT` | reference |
| `E-35.client_entity_id` | `E-01` | `FOR_PARTY` | role |
| `E-36.administrator_entity_id` | `E-01` | `ADMINISTERED_BY` | role |
| `E-37.metric_definition_id` | `E-22` | `COMPUTED_PER_METRIC` | reference |
| `E-38.rating_methodology_id` | `E-22` | `COMPUTED_PER_METRIC` | reference |
| `FO-01.asset_class` | `E-09` | `CLASSIFIED_AS_ASSET_CLASS` | reference |
| `FO-01.manager_entity_id` | `E-01` | `MANAGED_BY` | role |
| `FO-01.umbrella_fund_id` | `FO-01` | `SUBFUND_OF` | reference |
| `FO-02.asset_class` | `E-09` | `CLASSIFIED_AS_ASSET_CLASS` | reference |
| `FO-02.fund_product_id` | `FO-01` | `BELONGS_TO_FUND_PRODUCT` | composition |
| `FO-03.investor_entity_id` | `E-01` | `HAS_INVESTOR` | role |
| `FO-03.share_class_id` | `FO-02` | `OF_SHARE_CLASS` | composition |
| `FO-04.investor_entity_id` | `E-01` | `HAS_INVESTOR` | role |
| `FO-04.share_class_id` | `FO-02` | `OF_SHARE_CLASS` | composition |
| `FO-04.unitholding_id` | `FO-03` | `ON_UNITHOLDING` | reference |
| `FO-05.share_class_id` | `FO-02` | `OF_SHARE_CLASS` | composition |
| `FO-06.asset_class` | `E-09` | `CLASSIFIED_AS_ASSET_CLASS` | reference |
| `FO-06.fund_product_id` | `FO-01` | `BELONGS_TO_FUND_PRODUCT` | composition |
| `FO-06.share_class_id` | `FO-02` | `OF_SHARE_CLASS` | composition |
| `FO-07.corrects_statement_id` | `FO-07` | `CORRECTS` | reference |
| `FO-07.fund_product_id` | `FO-01` | `BELONGS_TO_FUND_PRODUCT` | composition |
| `FO-07.investor_entity_id` | `E-01` | `HAS_INVESTOR` | role |
| `FO-07.unitholding_id` | `FO-03` | `ON_UNITHOLDING` | reference |
| `FO-08.delegates_to_entity_id` | `E-01` | `DELEGATES_TO` | role |
| `FO-08.fund_product_id` | `FO-01` | `BELONGS_TO_FUND_PRODUCT` | composition |
| `FO-08.provider_entity_id` | `E-01` | `PROVIDED_BY` | role |
| `FO-09.fund_product_id` | `FO-01` | `BELONGS_TO_FUND_PRODUCT` | composition |
| `FO-09.intermediary_entity_id` | `E-01` | `VIA_INTERMEDIARY` | role |
| `FO-09.share_class_id` | `FO-02` | `OF_SHARE_CLASS` | composition |
| `FO-10.ap_agreement_id` | `FO-12` | `UNDER_AP_AGREEMENT` | reference |
| `FO-10.ap_entity_id` | `E-01` | `HAS_AUTHORISED_PARTICIPANT` | role |
| `FO-10.basket_id` | `FO-11` | `USES_BASKET` | reference |
| `FO-10.share_class_id` | `FO-02` | `OF_SHARE_CLASS` | composition |
| `FO-11.ap_entity_id` | `E-01` | `HAS_AUTHORISED_PARTICIPANT` | role |
| `FO-11.fund_product_id` | `FO-01` | `BELONGS_TO_FUND_PRODUCT` | composition |
| `FO-11.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `FO-11.share_class_id` | `FO-02` | `OF_SHARE_CLASS` | composition |
| `FO-12.ap_entity_id` | `E-01` | `HAS_AUTHORISED_PARTICIPANT` | role |
| `FO-12.fund_product_id` | `FO-01` | `BELONGS_TO_FUND_PRODUCT` | composition |
| `PB-01.gics_sector` | `E-11` | `CLASSIFIED_AS` | reference |
| `PB-01.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `PB-01.issuer_entity_id` | `E-01` | `ISSUED_BY` | role |
| `PB-02.credit_rating` | `E-11` | `CLASSIFIED_AS` | reference |
| `PB-02.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `PB-02.issuer_entity_id` | `E-01` | `ISSUED_BY` | role |
| `PB-03.broker_entity_id` | `E-01` | `VIA_BROKER` | role |
| `PB-03.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `PB-03.parent_order_id` | `PB-03` | `CHILD_ORDER_OF` | reference |
| `PB-03.portfolio_id` | `E-03` | `IN_PORTFOLIO` | reference |
| `PB-03.transaction_id` | `E-05` | `BOOKED_AS` | reference |
| `PB-04.broker_entity_id` | `E-01` | `VIA_BROKER` | role |
| `PB-04.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `PB-04.order_id` | `PB-03` | `FOR_ORDER` | reference |
| `PB-05.custodian_entity_id` | `E-01` | `HAS_CUSTODIAN` | role |
| `PB-05.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `PB-05.order_id` | `PB-03` | `FOR_ORDER` | reference |
| `PB-05.portfolio_id` | `E-03` | `IN_PORTFOLIO` | reference |
| `PB-06.allocation_id` | `PB-05` | `FOR_ALLOCATION` | reference |
| `PB-06.counterparty_entity_id` | `E-01` | `HAS_COUNTERPARTY` | role |
| `PB-06.custodian_entity_id` | `E-01` | `HAS_CUSTODIAN` | role |
| `PB-06.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `PB-06.portfolio_id` | `E-03` | `IN_PORTFOLIO` | reference |
| `PB-07.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `PB-07.resulting_instrument_id` | `E-02` | `RESULTS_IN_INSTRUMENT` | reference |
| `PB-07.transaction_id` | `E-05` | `FROM_TRANSACTION` | reference |
| `PB-08.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `PB-09.benchmark_id` | `E-10` | `CONSTITUENT_OF` | reference |
| `PB-09.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `PB-10.borrower_entity_id` | `E-01` | `HAS_BORROWER` | role |
| `PB-10.collateral_position_id` | `E-26` | `COLLATERALISED_BY` | reference |
| `PB-10.instrument_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `PB-10.position_id` | `E-04` | `LENDS_POSITION` | reference |
| `PB-11.meeting_id` | `PB-07` | `AT_MEETING` | reference |
| `PB-11.portfolio_id` | `E-03` | `IN_PORTFOLIO` | reference |
| `PM-01.administrator_id` | `PM-03` | `HAS_FUND_ADMINISTRATOR` | role |
| `PM-01.asset_class` | `E-09` | `CLASSIFIED_AS_ASSET_CLASS` | reference |
| `PM-01.fund_family_id` | `PM-01` | `IN_FUND_FAMILY` | composition |
| `PM-01.gp_id` | `PM-02` | `MANAGED_BY_GP` | role |
| `PM-04.successor_company_id` | `PM-04` | `SUCCEEDED_BY` | reference |
| `PM-05.investment_id` | `PM-09` | `FOR_INVESTMENT` | reference |
| `PM-06.fund_id` | `PM-01` | `OF_FUND` | reference |
| `PM-06.lp_entity_id` | `E-01` | `HAS_INVESTOR` | role |
| `PM-07.commitment_id` | `PM-06` | `AGAINST_COMMITMENT` | reference |
| `PM-07.fund_id` | `PM-01` | `OF_FUND` | reference |
| `PM-08.commitment_id` | `PM-06` | `AGAINST_COMMITMENT` | reference |
| `PM-08.fund_id` | `PM-01` | `OF_FUND` | reference |
| `PM-09.fund_id` | `PM-01` | `OF_FUND` | reference |
| `PM-09.target_id` | PM-04 / PM-01 | `HOLDS_INTEREST_IN` | reference |
| `PM-10.fund_id` | `PM-01` | `OF_FUND` | reference |
| `PM-10.terms_id` | `PM-10` | `UNDER_TERMS_VERSION` | composition |
| `PM-11.predecessor_gp_id` | `PM-02` | `HAS_PREDECESSOR_GP` | role |
| `PM-11.successor_gp_id` | `PM-02` | `HAS_SUCCESSOR_GP` | role |
| `PM-12.asset_class` | `E-09` | `CLASSIFIED_AS_ASSET_CLASS` | reference |
| `PM-12.benchmark_id` | `E-10` | `REFERENCES_BENCHMARK` | reference |
| `PM-12.fund_id` | `PM-01` | `OF_FUND` | reference |
| `PM-13.fund_id` | `PM-01` | `OF_FUND` | reference |
| `PM-13.investor_entity_id` | `E-01` | `HAS_INVESTOR` | role |
| `PM-14.borrower_entity_id` | `E-01` | `HAS_BORROWER` | role |
| `PM-14.direct_loan_id` | `E-02` | `ON_INSTRUMENT` | reference |
| `PM-14.originator_entity_id` | `E-01` | `ORIGINATED_BY` | role |
| `PM-15.target_entity_id` | `E-01` | `HAS_TARGET_PARTY` | role |
| `RA-01.holding_vehicle_id` | `PM-05` | `HELD_THROUGH_VEHICLE` | reference |
| `RA-02.real_asset_id` | `RA-01` | `ON_REAL_ASSET` | reference |
| `RA-03.real_asset_id` | `RA-01` | `ON_REAL_ASSET` | reference |
| `RA-03.tenant_entity_id` | `E-01` | `HAS_TENANT` | role |
| `RA-04.concession_grantor_id` | `E-01` | `HAS_CONCESSION_GRANTOR` | role |
| `RA-04.contractor_entity_id` | `E-01` | `HAS_CONTRACTOR` | role |
| `RA-04.real_asset_id` | `RA-01` | `ON_REAL_ASSET` | reference |
| `RA-05.real_asset_id` | `RA-01` | `ON_REAL_ASSET` | reference |
| `RA-05.valuer_entity_id` | `E-01` | `VALUED_BY` | role |
| `DR-01` specialises `E-02` | `E-02` | `SPECIALISES` | is-a |
| `DR-02` specialises `E-02` | `E-02` | `SPECIALISES` | is-a |
| `FO-01` specialises `E-02` | `E-02` | `SPECIALISES` | is-a |
| `FO-02` specialises `E-02` | `E-02` | `SPECIALISES` | is-a |
| `FO-03` specialises `E-04` | `E-04` | `SPECIALISES` | is-a |
| `FO-04` specialises `E-05` | `E-05` | `SPECIALISES` | is-a |
| `FO-05` specialises `E-05` | `E-05` | `SPECIALISES` | is-a |
| `FO-06` specialises `E-07` | `E-07` | `SPECIALISES` | is-a |
| `FO-07` specialises `E-15` | `E-15` | `SPECIALISES` | is-a |
| `FO-09` specialises `E-25` | `E-25` | `SPECIALISES` | is-a |
| `FO-10` specialises `E-05` | `E-05` | `SPECIALISES` | is-a |
| `PB-01` specialises `E-02` | `E-02` | `SPECIALISES` | is-a |
| `PB-02` specialises `E-02` | `E-02` | `SPECIALISES` | is-a |
| `PB-03` specialises `E-05` | `E-05` | `SPECIALISES` | is-a |
| `PB-04` specialises `E-05` | `E-05` | `SPECIALISES` | is-a |
| `PB-05` specialises `E-05` | `E-05` | `SPECIALISES` | is-a |
| `PB-06` specialises `E-05` | `E-05` | `SPECIALISES` | is-a |
| `PB-07` specialises `E-05` | `E-05` | `SPECIALISES` | is-a |
| `PB-08` specialises `E-02` | `E-02` | `SPECIALISES` | is-a |
| `PB-09` specialises `E-10` | `E-10` | `SPECIALISES` | is-a |
| `PB-10` specialises `E-04` | `E-04` | `SPECIALISES` | is-a |
| `PB-11` specialises `E-05` | `E-05` | `SPECIALISES` | is-a |
| `PM-01` specialises `E-02` | `E-02` | `SPECIALISES` | is-a |
| `PM-02` specialises `E-01` | `E-01` | `SPECIALISES` | is-a |
| `PM-03` specialises `E-01` | `E-01` | `SPECIALISES` | is-a |
| `PM-04` specialises `E-01` | `E-01` | `SPECIALISES` | is-a |
| `PM-07` specialises `E-05` | `E-05` | `SPECIALISES` | is-a |
| `PM-08` specialises `E-05` | `E-05` | `SPECIALISES` | is-a |
| `PM-09` specialises `E-04` | `E-04` | `SPECIALISES` | is-a |
| `PM-12` specialises `E-10` | `E-10` | `SPECIALISES` | is-a |
| `PM-13` specialises `E-03` | `E-03` | `SPECIALISES` | is-a |
| `PM-14` specialises `E-02` | `E-02` | `SPECIALISES` | is-a |
| `RA-01` specialises `E-02` | `E-02` | `SPECIALISES` | is-a |
| `RA-05` specialises `E-07` | `E-07` | `SPECIALISES` | is-a |

## Edges that need care

Three kinds of edge do not resolve as a plain one-column-to-one-entity pointer. They are first-class in this vocabulary all the same.

**Self-referential edges.** A column that resolves to its own entity — a hierarchy or a versioning link. Legal entities have parents (`SUBSIDIARY_OF`), portfolios have parent portfolios (`SUB_PORTFOLIO_OF`), orders have parent orders (`CHILD_ORDER_OF`), a classification value is superseded by a newer one (`SUPERSEDED_BY`), a fund product is a sub-fund of an umbrella (`SUBFUND_OF`), a tax statement corrects a prior one (`CORRECTS`), and a portfolio company is succeeded by another (`SUCCEEDED_BY`). Four more are self-references to a parent part *within* a multi-part entity: a classification value belongs to a classification type (`VALUE_OF_TYPE`), a CSA is annexed to its master agreement (`ANNEXED_TO`), a vehicle belongs to its fund family (`IN_FUND_FAMILY`), and an economic term sits under its versioned fund-terms parent (`UNDER_TERMS_VERSION`). One more self-edge is a typed *party-to-party* relationship rather than a hierarchy: a legal entity is related to another legal entity (`RELATED_TO_PARTY`, `E-01.related_entity_id`) — manager-of, successor-of or guarantor-of, named by the `E-01.party_relationship_type` discriminator. That discriminator selects the *meaning* of the relationship, not the target type (the target is always another `E-01`), so it is a plain semantic column, not a polymorphic target-selector like the two below — the edge resolves as an ordinary self-FK.

**Polymorphic edges.** Two columns resolve to *one of several* entity types, chosen by a discriminator column on the same row:

- **`E-15.subject_id`** (`HAS_SUBJECT`) — the document node's link to the thing it concerns. The discriminator `subject_type` selects the target: `legal_entity` &rarr; `E-01`, `instrument` &rarr; `E-02`, `portfolio` &rarr; `E-03`, `holding` &rarr; `E-04`, `fund` &rarr; `PM-01`, `fund_investment` &rarr; `PM-09`. This is the structured&harr;unstructured bridge: resolve an entity, follow `SUBJECT_OF` to reach its documents.
- **`PM-09.target_id`** (`HOLDS_INTEREST_IN`) — a fund investment's link to the thing held. The discriminator `holding_type` selects the target: `portfolio_company` &rarr; `PM-04`, `fund` &rarr; `PM-01` (the fund-of-funds case, where look-through recurses through the holding graph).

## How this map is maintained

- Every foreign-key column and every `**Specialises:**` line in an entity file appears in [the mapping](#the-mapping), bound to one verb. The export tooling reconciles the two: a column with no verb, or a verb that binds no edge, is surfaced.
- A new entity or a new foreign key adds a row to the mapping and reuses an existing verb where the relationship already has a name; a genuinely new kind of relationship adds a new verb, with its inverse, in the block above.
- The verb names are stable identifiers. Renaming a verb is a breaking change to the graph projections and goes through the model's standard route.
