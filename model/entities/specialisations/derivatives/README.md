# Derivatives Specialisation

**Maturity:** Provisional · narrow by design — the portfolio-level layer above ISDA CDM's transaction grain, with the overlay-manager entity needs derived and dispositioned below (the boundary defended, not asserted)

The entity specialisation for **derivatives** — listed and over-the-counter — used by institutional investors for hedging, overlay management, cash equitisation, efficient exposure, and as instruments in their own right.

Its design point is its boundary with **ISDA CDM**: OpenIM does not re-model the derivative contract or its lifecycle — CDM already does that, well, in a machine-executable form — and instead models the *portfolio-level concerns above the transaction grain*. See the section below.

## How this pack specialises the core

Every entity here either specialises a [core entity](../../core/) or is a native relationship entity of the pack. The core says what is universal; the pack adds what is specific to derivatives:

- A **listed derivative** and an **OTC derivative** are each an Instrument / Asset (E-02), of `instrument_class = listed_derivative` and `otc_derivative`. **DR-01** and **DR-02** add the underlying relationship and the contract terms the core does not carry.
- A position in either is a Holding / Position (E-04); a derivatives trade is a Transaction (E-05); a collateral movement is a Cash Flow Event (E-06) — the core entities, used as-is.
- A **master agreement**, a **margin balance** and a **clearing relationship** are *relationships*, not instruments — they specialise no core entity and are native to the pack. **DR-03**, **DR-04** and **DR-05** model the legal, collateral and clearing framework that derivative positions sit inside.

What this pack adds that the core does not: the contract terms of a derivative, the underlying relationship, the ISDA master-agreement and collateral framework, the running margin position, and the clearing relationship.

## Entities

| ID | Entity | Specialises | Role |
|---|---|---|---|
| DR-01 | [Listed Derivative](DR-01-listed-derivative.md) | E-02 Instrument / Asset | An exchange-traded future or option — underlying, expiry, contract terms; centrally cleared by construction. |
| DR-02 | [OTC Derivative](DR-02-otc-derivative.md) | E-02 Instrument / Asset | A bilaterally negotiated swap, forward or OTC option — underlying, bespoke terms, counterparty, master agreement. |
| DR-03 | [Master Agreement & Collateral Terms](DR-03-master-agreement.md) | — | The ISDA Master Agreement and CSA governing an uncleared OTC derivative relationship — the netting set and the collateral terms. |
| DR-04 | [Margin & Collateral Balance](DR-04-margin-collateral-balance.md) | — | The running collateral position of a relationship — initial and variation margin posted, received and owed. |
| DR-05 | [Clearing Relationship](DR-05-clearing-relationship.md) | — | The CCP, clearing broker and clearing account through which cleared derivatives are cleared — the cleared-path peer of DR-03. |

The master agreement, the margining *position* and the clearing relationship are three distinct things — the collateral *balance* is a running state, not a legal document, and the cleared path has no CSA and faces a CCP rather than a bilateral counterparty. Collapsing them would force two unlike things into one master.

## Relationship to ISDA CDM — complementary, not a replacement

This pack is where OpenIM's complementarity with **ISDA CDM** is most concrete, and the boundary is deliberate.

**ISDA CDM (the Common Domain Model, now a FINOS Active Project) already models the derivative product, the trade in it, and the full set of lifecycle events** — execution, confirmation, novation, amendment, compression, clearing, settlement, margin-call and collateral events — at the transaction grain, in a machine-readable and machine-executable form. CDM also models the ISDA Master Agreement and CSA through its Legal Agreement model and a Clause Library of elections. **OpenIM does not reinvent any of that.**

The derivatives pack **references CDM** for the product-and-trade-and-lifecycle representation and models the *portfolio-level concerns above it*:

| Layer | Modelled by | What it answers |
|---|---|---|
| The contract, the trade, the lifecycle event, the legal-agreement elections | **ISDA CDM** | What is this swap? What happened to this trade? What does this CSA elect? |
| The instrument as buy-side reference data; the **position**; the **counterparty exposure**; the **master-agreement relationship**; the **margin balance**; the **clearing relationship** | **OpenIM derivatives pack** | What do we hold? Who do we face, net? Are we adequately collateralised? Which CCP clears this? |

The rule of thumb every entity file states: **if a question is about the contract or a lifecycle event, it is CDM's; if it is about the position, the exposure, the collateral relationship or the clearing relationship, it is OpenIM's.** Where an OpenIM implementation runs CDM, the DR-02 record carries a `cdm_trade_ref` cross-reference and DR-03 / DR-04 / DR-05 carry references to the corresponding CDM legal-agreement and event representations. Where it does not, the OpenIM entities are self-contained at the depth the buy-side operating model needs. The two models compose; they do not compete.

See [PRIOR-ART.md](../../../../PRIOR-ART.md) for OpenIM's full positioning against CDM, FIBO, FpML and the rest of the standards landscape.

## The derivatives-overlay manager — the pack's coverage derived, not asserted

The pack's five entities are *narrow by design*, but "narrow by design" must be defended against a real buy-side segment, not asserted relative to a boundary the model itself drew. The under-represented practitioner is the **derivatives-overlay manager** — the currency-overlay manager, the LDI / pension-buyout duration-overlay manager, the managed-futures CTA, the volatility-arbitrage fund — who invests mostly or wholly synthetically and would need richer entity content than `position / exposure / relationship` if those needs were not met elsewhere. Each of the three entity needs an overlay manager would expect is derived and dispositioned:

| Overlay-manager entity need | Disposition | Where it lives |
|---|---|---|
| **Hedge-accounting designation** (the IFRS 9 / ASC 815 hedge-effectiveness designation as a holding-level attribute — the hedged item, the hedge relationship, the effectiveness test) | **Deferred to the accounting layer, not a derivatives-pack entity.** Hedge-accounting designation is a *property of the holding's accounting treatment*, carried on the Holding / Position (E-04) and governed by the accounting standard the books are kept to (SD-12.2 ABOR, SD-12.9). It is not a derivative-instrument attribute — an equity or a bond can be a hedged item too — so modelling it in the derivatives pack would mis-place it. A `hedge_designation` candidate attribute on E-04 (with the hedged-item reference, the relationship type, and the effectiveness-test result) is named as a core-entity open extension, not a DR entity. | E-04 (candidate attribute); accounting SDs |
| **Multi-underlying allocation** (a synthetic position taken at the strategy level and allocated across the underlying portfolios or funds it is run for) | **Covered by the existing OpenIM allocation entity, not a new DR entity.** The apportionment of a single executed exposure across the portfolios it was traded for is PB-05 Allocation (the public-markets-pack allocation entity), which generalises across instrument families — a swap allocated across funds is the same allocation shape as an equity block allocated across portfolios. The derivatives position (E-04, specialised by DR-01 / DR-02) carries the per-portfolio holding; PB-05 carries the apportionment that produced it. | PB-05 Allocation; E-04 |
| **Netting-set hierarchy** (cross-product netting granularity finer than a single master-agreement netting set — sub-netting sets, product-class netting, the give-up state) | **Covered by DR-03 at the buy-side grain, with the finer hierarchy deferred to ISDA CDM's Legal Agreement model.** DR-03 Master Agreement & Collateral Terms models the netting set the buy-side operating model needs — one per ISDA master-agreement relationship. The finer cross-product and sub-netting-set hierarchy, and the give-up / clearing-novation state, are *legal-agreement-election and lifecycle-event* concerns — CDM's Legal Agreement model and its event model carry them at the transaction grain, and DR-03 cross-references the CDM legal-agreement representation where an implementation runs CDM. The buy-side overlay manager that does not run CDM holds DR-03 at the master-agreement netting-set grain, which is sufficient for portfolio-level exposure and collateral adequacy; the finer hierarchy is a CDM concern by the same boundary rule the pack draws for every other contract-and-lifecycle question. | DR-03; ISDA CDM (Legal Agreement model) |

The asymmetry is therefore **needs-driven, not self-sealing**: of the three overlay-manager entity needs, one is re-homed to the core accounting layer (hedge designation is not a derivative attribute), one is already covered by the existing allocation entity (PB-05 generalises), and one is met by DR-03 at the buy-side grain with the finer hierarchy deferred to CDM on the same boundary rule the rest of the pack follows. The 5-entity count holds against the overlay-manager challenge — but the defence is the per-need derivation above, not "full coverage relative to the boundary we chose."

## The counterparty

The investor's derivatives counterparties — swap dealers, clearing brokers, central counterparties, exchanges — are **Legal Entities** (E-01) in the `counterparty` role. There is no separate counterparty entity. DR-02, DR-03 and DR-05 reference the counterparty through E-01; where a counterparty relationship carries substantial structure of its own, that structure is the relationship entity (DR-03, DR-05), not a duplicate party master.

## Sources

The pack's research is grounded in:

- FINOS Common Domain Model — overview and scope: <https://cdm.finos.org/docs/cdm-overview/>
- FINOS CDM — Legal Agreements (Master Agreement and CSA modelling): <https://cdm.finos.org/docs/legal-agreements/>
- FINOS — "From Standards to Impact: CDM Becomes an Active FINOS Project": <https://www.finos.org/blog/from-standards-to-impact-cdm-becomes-an-active-finos-project>
- ISDA — CDM solutions infohub: <https://www.isda.org/isda-solutions-infohub/cdm/>
- ISDA — Initial Margin Documentation: <https://www.isda.org/a/D0DgE/20210526-ISDA_Initial-Margin-Documentation-Where_to_Begin_FINAL.pdf>
- ISDA — 2016 Variation Margin Protocol: <https://www.isda.org/protocol/isda-2016-variation-margin-protocol/>
- ESMA — Clearing obligation and risk-mitigation techniques under EMIR: <https://www.esma.europa.eu/post-trading/clearing-obligation-and-risk-mitigation-techniques-under-emir>
- CFA Institute GIPS — Guidance Statement on Overlay Strategies: <https://www.gipsstandards.org/wp-content/uploads/2022/01/gs_overlay_2022.pdf>
