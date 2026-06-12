# DR-03 — Master Agreement & Collateral Terms

The bilateral legal framework governing an institutional investor's OTC derivative relationship with a counterparty — the ISDA Master Agreement, its Schedule, and the Credit Support Annex (CSA) or equivalent credit-support document that sets the collateral terms. One DR-03 record per (investor, counterparty) master-agreement relationship.

**Specialises:** none. A master agreement is not an Instrument / Asset and not a Transaction — it is a *legal relationship* between two Legal Entities. It references E-01 for the counterparty, and it is referenced by the OTC derivatives (DR-02) it governs, but it is a native entity of this pack with no core parent. It is the derivatives-pack analogue of the private-markets pack's PM-10 Fund Terms — the negotiated legal-and-economic framework, modelled as queryable data rather than left in a contract PDF.

## Purpose

Every OTC derivative an investor holds sits inside a master-agreement relationship. A single ISDA Master Agreement with a counterparty governs *all* the OTC trades between them: it is the document that makes close-out netting enforceable, sets the events of default and termination, and — through the CSA attached to it — defines how collateral is exchanged. The investor cannot reason correctly about counterparty exposure, collateral obligations, or termination risk without this relationship modelled explicitly. The exposure that matters for counterparty-risk purposes is not per-trade; it is the *net* exposure across every trade under one master agreement, because that is what close-out netting collapses to. DR-03 is the entity that makes the master-agreement set a first-class object so that netting, collateral and termination can be computed against it.

The CSA terms — threshold, minimum transfer amount, eligible collateral, the independent amount, whether the relationship is two-way — are economic parameters that drive daily operational margining. Held as a contract PDF they are unauditable and survive only in an operations team's working knowledge. Held as DR-03 data they are queryable and the margin process (DR-04) reads them.

## Attribute schema — Master Agreement

| Column | Type | Definition |
|---|---|---|
| `master_agreement_id` | varchar | **Golden key.** The OpenIM-assigned identifier for the master-agreement relationship. |
| `investor_entity_id` | varchar (FK → E-01) | The investing institution, as the entity party to the agreement. |
| `counterparty_entity_id` | varchar (FK → E-01) | The counterparty — a Legal Entity in the `counterparty` role. |
| `agreement_type` | varchar | The published form — `isda_2002` / `isda_1992` / `isda_2002_french` / other. |
| `agreement_date` | date | The date the master agreement was executed. |
| `governing_law` | varchar | The law the agreement is governed by — English, New York, etc. |
| `netting_enforceable` | boolean | Whether close-out netting is legally enforceable for this relationship and jurisdiction — the input to net-exposure computation. |
| `status` | varchar | `active` / `terminated`. |

## Attribute schema — Credit Support Annex

| Column | Type | Definition |
|---|---|---|
| `csa_id` | varchar | **Golden key** for the credit-support document. |
| `master_agreement_id` | varchar (FK → Master Agreement) | The master agreement this CSA is annexed to. |
| `csa_type` | varchar | The credit-support form — `csa_2016_vm` (variation-margin CSA), `csa_initial_margin` / `csd` / `cta`, etc. |
| `csa_law_form` | varchar | The legal form — New York, English, Irish, French, Japanese. |
| `margin_type` | varchar | `variation_margin` / `initial_margin` / `both` — which margin the document governs. |
| `direction` | varchar | `bilateral` (two-way) or `one_way` collateralisation. |
| `threshold_amount` | decimal | The unsecured exposure permitted before collateral must be posted. |
| `minimum_transfer_amount` | decimal | The smallest collateral movement that triggers a transfer. |
| `independent_amount` | decimal | The initial-margin / independent amount, where the document specifies one. |
| `eligible_collateral` | array | The asset types acceptable as collateral, with their haircuts. |
| `base_currency` | char | The base currency for collateral calculations. |
| `valuation_agent` | varchar | Which party calculates exposure and margin calls. |

## Notes

- **Relationship to ISDA CDM.** CDM has a Legal Agreement model that represents the ISDA Master Agreement and the CSA — including the 2016 and 2018 CSAs and credit-support deeds — through a Clause Library of identifiers, variants and elections rather than reproduced legal text. DR-03 is **complementary, not a duplicate**: where an implementation runs CDM, DR-03 carries the cross-reference to the CDM legal-agreement representation and holds the small set of elections the buy-side operating model reads directly — threshold, minimum transfer amount, independent amount, eligible collateral, netting enforceability. The full machine-readable election set is CDM's; DR-03 is the operational summary the counterparty-risk, collateral and termination domains consume. The boundary: CDM models the legal agreement as an executable document; OpenIM models the agreement as a portfolio-level *relationship* that trades hang off and exposure nets within.
- DR-03 governs **uncleared** OTC derivatives. A cleared OTC derivative faces a CCP and its margining runs through the clearing relationship (DR-05) under the CCP's rulebook, not a bilateral CSA. An investor typically has both: bilateral master agreements for uncleared trades and clearing arrangements for cleared ones.
- The master agreement is the **netting set**. Net counterparty exposure (SD-07.2) is computed per `master_agreement_id`, not per trade — every DR-02 under one master agreement nets, and the collateral held under its CSA offsets that net figure.
- The CSA is the bridge to operations: DR-04 Margin & Collateral Balance is computed *against* the CSA terms — the threshold and minimum transfer amount here determine when a margin call is made and for how much.

## Out of scope

- The legal agreement modelled as an executable, fully machine-readable document — that is ISDA CDM's Legal Agreement model and Clause Library; DR-03 is the operational summary of the elections the buy-side reads directly.
- The OTC derivatives the agreement governs — those are DR-02 OTC Derivative, which reference DR-03 through `master_agreement_id`.
- The cleared path — a cleared derivative faces a CCP under its rulebook, not a bilateral CSA — that is DR-05 Clearing Relationship; DR-03 governs uncleared OTC derivatives only.
- The running collateral balance computed against the CSA terms — that is DR-04 Margin & Collateral Balance; DR-03 sets the terms, DR-04 is the position.

## Owned and consumed by

- **Owned by:** SD-14.9 Legal & Contract Management (the executed agreement is a legal document).
- **Sourced from:** SD-06.6 Derivatives & OTC Trade Management (the ISDA / CSA is referenced and put in place as the OTC relationship is established).
- **Consumed by:** SD-11.4 Margin & Collateral Operations, SD-11.5 Collateral Optimisation & Inventory Management, SD-07.2 Credit & Counterparty Risk Management, SD-08.5 Valuation Adjustments & Reserves (XVA reads CSA terms), SD-10.x Investment Compliance (counterparty eligibility), DR-04 Margin & Collateral Balance.

## Open extensions

- The concrete CDM legal-agreement cross-reference — which CDM Clause Library elements DR-03's summary attributes map to.
- Side-letter and amendment versioning on the master agreement and CSA, effective-dated as PM-10 versions fund terms.
- The relationship to uncleared-margin-rules (UMR) phase-in status — which counterparty relationships are in scope for regulatory initial margin.
- Multi-CSA relationships — separate variation-margin and initial-margin documents under one master agreement, and the segregated-custodian arrangement initial margin requires.
