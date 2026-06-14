# OpenIM Glossary

Plain-English definitions of the investment-management vocabulary OpenIM uses. This glossary is a reader's reference: where a term carries a structural meaning in OpenIM (an entity, a Service Domain, a standard), the entry points to the relevant model element so the reader can follow it back.

The vocabulary spans **both public-markets investing and private-markets investing** — public-markets terms (TWR, GIPS, ISIN, ISDA CDM), private-markets / LP-GP terms (LPA, capital call, distribution, J-curve, vintage, the family of PME / IRR / TVPI / DPI / RVPI / MOIC metrics, the waterfall mechanics) and the master-data terms (LEI, golden key, alias, external identifier, ABOR / IBOR) that the OpenIM canonical model is built around.

Conventions: alphabetical; **bold** the term; cross-references with *see also*; each definition is one or two sentences plain enough to read on first encounter. Cross-references to OpenIM elements use the model's identifiers — `E-NN` for [core entities](entities/INDEX.md), `PB-NN` / `FO-NN` / `PM-NN` / `DR-NN` / `RA-NN` for [specialisation entities](entities/INDEX.md), `BD-NN` / `SD-NN.M` for [service-domain elements](service-domains/INDEX.md).

---

## A

**ABOR (Accounting Book of Record)** — The authoritative accounting view of positions and transactions, typically produced by the fund administrator under accounting policy. Daily but periodic; the basis for the NAV the fund strikes. *See also* IBOR; [E-04 Holding / Position](entities/core/E-04-holding-position.md); [SD-12.2 Accounting Book of Record (ABOR)](service-domains/BD-12-investment-operations-and-servicing/SD-12.2-accounting-book-of-record-abor.md).

**AIV (Alternative Investment Vehicle)** — A parallel structure (limited partnership, blocker, feeder) used alongside a main fund to accommodate tax, regulatory or investor-specific needs. Many LPs invest into a fund through their AIV rather than the main vehicle.

**Allocation (capital allocation)** — The split of capital across asset classes, strategies or mandates. Strategic allocation is long-horizon (see [SD-01.4 Strategic Asset Allocation](service-domains/BD-01-investment-strategy-and-allocation/SD-01.4-strategic-asset-allocation.md)); tactical allocation is medium-horizon ([SD-01.5](service-domains/BD-01-investment-strategy-and-allocation/SD-01.5-tactical-and-dynamic-asset-allocation.md)).

**Alias** — A name a master record has been seen under in a source. OpenIM stores aliases as first-class data (one master, many aliases) so entity resolution is auditable. *See* [E-13 Entity Alias](entities/core/E-13-entity-alias.md).

**Appraisal** — A periodic valuation of a directly-held real asset by a qualified valuer, governed by a recognised basis of value (IVS, RICS). *See* [RA-05 Asset Appraisal](entities/specialisations/real-assets/RA-05-asset-appraisal.md).

**Asset class** — A grouping of investments with shared economic behaviour — public equities, fixed income, private equity, private credit, real estate, infrastructure, natural resources, hedge funds. *See* [E-09 Asset Class](entities/core/E-09-asset-class.md).

## B

**Basis of value** — The named valuation purpose under which a value is determined — IVS Market Value, IVS Equitable Value, IFRS 13 Fair Value, and others. OpenIM keeps basis-of-value and reporting-basis distinct because they are not the same concept. *See* [RA-05 Asset Appraisal](entities/specialisations/real-assets/RA-05-asset-appraisal.md).

**BCBS 239** — Basel Committee principles for risk-data aggregation and reporting. Mandatory for banks; institutional investors adopt voluntarily as a discipline.

**Benchmark** — A reference index or peer set against which a portfolio's return is measured. Public-markets portfolios use published market indices; private-markets portfolios use vintage-year peer benchmarks (e.g. quartile rankings within a strategy and vintage). *See* [E-10 Benchmark / Index](entities/core/E-10-benchmark-and-index.md); [SD-09.4 Benchmark Management](service-domains/BD-09-performance-and-analytics/SD-09.4-benchmark-management.md).

**Bi-temporal** — The discipline of recording both *effective time* (when the fact was true in the world) and *record time* (when the firm learned it). OpenIM's classification machinery is bi-temporal so the model can answer "what did we believe, and as of when". *See* [E-12 Classification History](entities/core/E-12-classification-history.md).

## C

**Capital account** — An LP-specific record of its position in a fund: commitment, capital called, distributions received, NAV share, unfunded amount. The fund administrator produces it.

**Capital call** — A notice from a GP to its LPs requesting drawdown of committed capital, with amount, deadline, purpose and account details. *See* [PM-07 Capital Call](entities/specialisations/private-markets/PM-07-capital-call.md).

**Carried interest (carry)** — The GP's share of fund profits, typically 20% above a hurdle rate. Paid through the waterfall.

**Cash flow event** — A dated movement of cash — call, distribution, fee, interest, dividend. The granular record performance is computed from. *See* [E-06 Cash Flow Event](entities/core/E-06-cash-flow-event.md).

**Catch-up** — The waterfall mechanic by which the GP receives an accelerated share of distributions after the hurdle is met, until the GP's overall share of profits reaches the agreed percentage (typically 20%).

**Co-investment** — A direct investment by an LP alongside a fund into a specific portfolio company or asset, usually at reduced or zero fees. *See* [SD-04.7 Co-Investment Management](service-domains/BD-04-direct-and-co-investment/SD-04.7-co-investment-management.md).

**Commitment** — The amount of capital an LP has contractually committed to a fund. Drawn down by capital call over the fund's investment period. *See* [PM-06 LP Commitment](entities/specialisations/private-markets/PM-06-lp-commitment.md).

**Commitment pacing** — The portfolio-construction discipline of deciding the rate of new commitments to private-markets funds so the target allocation is reached and held over time. *See* [SD-01.10 Commitment Pacing](service-domains/BD-01-investment-strategy-and-allocation/SD-01.10-commitment-pacing-and-deployment-planning.md).

**Composite** — Under GIPS, an aggregation of one or more portfolios managed to a similar strategy. Performance must be reported at the composite, not at a cherry-picked portfolio. *See* [SD-09.6 GIPS Compliance](service-domains/BD-09-performance-and-analytics/SD-09.6-gips-performance-standards-compliance.md).

**Corporate action** — A change in an issuer's securities — dividend, split, merger, rights issue — affecting holdings. *See* [PB-07 Corporate Action](entities/specialisations/public-markets/PB-07-corporate-action.md).

## D

**Distribution** — A return of cash (or, occasionally, in-kind) by a fund to its LPs. *See* [PM-08 Distribution](entities/specialisations/private-markets/PM-08-distribution.md).

**DPI (Distributions to Paid-In)** — Total cash distributed by a fund divided by total capital called. The realised-multiple. A DPI of 1.0× means cumulative cash back equals cumulative cash in. *See also* RVPI, TVPI.

## E

**Effective date / Effective from / Effective to** — The world-time validity of a fact, distinct from when the firm recorded it. The bi-temporal companion of *record time*. *See also* Bi-temporal.

**Entity resolution** — The process of recognising that two records in different source systems refer to the same real-world entity (the same fund, company, manager). Necessary because private markets have no universal identifier. *See* [E-13 Entity Alias](entities/core/E-13-entity-alias.md), [E-14 External Identifier](entities/core/E-14-external-identifier.md).

**External identifier** — A cross-reference from an OpenIM golden key to an external system's identifier (LEI, FIGI, ISIN, vendor ID). *See* [E-14 External Identifier](entities/core/E-14-external-identifier.md).

## F

**Fair value (IFRS 13 / ASC 820)** — The accounting definition: the price that would be received to sell an asset in an orderly transaction between market participants at the measurement date. Equivalent to *IVS Market Value*; distinct from *IVS Equitable Value*.

**FIBO (Financial Industry Business Ontology)** — A formal ontology of financial *things* — instruments, legal entities, securities — maintained by the EDM Council. OpenIM aligns to FIBO for legal-entity and instrument semantics. *See* [PRIOR-ART.md](../PRIOR-ART.md).

**FIGI (Financial Instrument Global Identifier)** — An open, free identifier for financial instruments maintained by Bloomberg / Object Management Group. Used as one of the external identifiers OpenIM resolves across.

**Four-lens NAV** — The discipline of carrying multiple concurrent views of a private-fund NAV: GP-reported, shadow-accounted, valuation-adjusted, proxy-rolled. Recognises that no single number is canonical at every grain. *See* [E-07 Valuation](entities/core/E-07-valuation.md); [SD-08.3 Private-Asset Valuation](service-domains/BD-08-valuation-and-pricing/SD-08.3-private-asset-valuation.md).

**From-day-one IRR** — IRR recalculated as if capital had been called on day one of the commitment, stripping the inflation effect of a subscription credit facility. Typically 300–600 bps lower than the GP-reported IRR for buyout funds that use a subscription line.

**Fund** — A pooled investment vehicle. OpenIM models a fund as a kind of Instrument (a specialisation of [E-02](entities/core/E-02-instrument-asset.md)); the private-markets specialisation is [PM-01 Fund / Vehicle](entities/specialisations/private-markets/PM-01-fund-and-vehicle.md).

**Fund administrator** — A third-party firm that produces the fund's accounting, NAV strike, investor statements, and other administrative records. *See* [PM-03 Fund Administrator](entities/specialisations/private-markets/PM-03-fund-administrator.md).

**Fund terms** — The economic terms of a fund — hurdle, carry percentage, management fee, clawback — versioned over time. Modelled as computation-as-data, not scalar columns. *See* [PM-10 Fund Terms](entities/specialisations/private-markets/PM-10-fund-terms.md).

## G

**General Partner (GP)** — The fund manager; the entity with management authority and unlimited liability in a limited partnership. *See* [PM-02 GP / Management Company](entities/specialisations/private-markets/PM-02-gp-management-company.md).

**GIPS (Global Investment Performance Standards)** — A voluntary standard from CFA Institute for calculating and presenting investment performance. *See* [SD-09.6 GIPS Compliance](service-domains/BD-09-performance-and-analytics/SD-09.6-gips-performance-standards-compliance.md).

**Golden key** — OpenIM's internal canonical identifier for a master record, stable across the firm's systems. Externally-issued identifiers (LEI, FIGI, ISIN) are mapped to it.

## H

**Holding (position)** — What is owned: a position in an instrument, in a portfolio, at a point in time. The atomic unit of investment record. *See* [E-04 Holding / Position](entities/core/E-04-holding-position.md).

**Hurdle (preferred return)** — A minimum return — typically 8% — an LP receives before the GP earns any carry.

## I

**IBOR (Investment Book of Record)** — The real-time, manager-side view of positions and transactions, intraday and forward-looking. Differs from ABOR's accounting-policy basis. *See also* ABOR; [E-04 Holding / Position](entities/core/E-04-holding-position.md).

**ILPA (Institutional Limited Partners Association)** — The LP industry body; publisher of the standard quarterly reporting templates GPs use to report to LPs.

**ILPA templates** — Standardised quarterly reporting formats (Reporting Template, Performance Template) covering capital activity, fees, performance and portfolio detail. Format standardisation, not master-data standardisation.

**Instrument (asset)** — The universal holdable thing — listed equity, debt, derivatives, fund interests, loans, real assets, cash. *See* [E-02 Instrument / Asset](entities/core/E-02-instrument-asset.md).

**IRR (Internal Rate of Return)** — The annualised, money-weighted return that discounts a stream of cash flows to zero. The standard private-markets return metric. *See also* From-day-one IRR; MWR; TWR.

**ISDA CDM (Common Domain Model)** — A machine-readable model of financial products and their lifecycle events, maintained under FINOS. OpenIM is complementary to CDM: CDM models the transaction layer; OpenIM models the portfolio, fund and mandate layer above it.

**ISIN (International Securities Identification Number)** — A 12-character standard identifier for securities. One of the external identifiers OpenIM resolves across in public markets.

**IVS (International Valuation Standards)** — The valuation profession's standards, maintained by the IVSC. Six named bases of value, including Market Value and Equitable Value. *See* [RA-05 Asset Appraisal](entities/specialisations/real-assets/RA-05-asset-appraisal.md).

## J

**J-curve** — The characteristic shape of a private-markets fund's cumulative net cash flow from the LP's perspective: negative in the early years (fees and called capital, no distributions yet, early write-downs), bottoming out, then climbing positive as investments mature and exits arrive.

## L

**Legal entity** — A party — issuer, counterparty, manager, custodian, administrator, portfolio company — modelled as a single master with roles, not as separate masters per role. *See* [E-01 Legal Entity](entities/core/E-01-legal-entity.md).

**LEI (Legal Entity Identifier)** — A 20-character standard identifier for legal entities, issued under the Global LEI System (GLEIF). One of the external identifiers OpenIM resolves across.

**Limited Partner (LP)** — A capital provider in a limited partnership; provides the bulk of the fund's capital and has limited liability and limited management rights.

**Limited Partnership Agreement (LPA)** — The constitutional document of a private-markets fund, running to hundreds of pages — strategy, restrictions, fees, waterfall, redemption rights, reporting, GP removal, key-person provisions.

**Look-through exposure** — The aggregated exposure to an underlying issuer or asset across pooled vehicles and direct holdings. Computing look-through requires resolving the same underlying across multiple vehicle reports. *See* [SD-07.5 Look-Through Exposure Analysis](service-domains/BD-07-investment-risk/SD-07.5-look-through-exposure-analysis.md).

## M

**Management fee** — A periodic fee paid to the GP, typically 2% of committed capital during the investment period and stepping down to a percentage of invested capital during the harvest period. Charged regardless of performance.

**Mandate** — The governing instruction for a pool of capital — objectives, benchmark, restrictions, fees — whether self-authored by an asset owner or codified from an inbound client mandate. Modelled as a facet of [E-03 Portfolio / Mandate](entities/core/E-03-portfolio-mandate.md). *See also* [SD-01.2 Investment Mandate & Policy Definition](service-domains/BD-01-investment-strategy-and-allocation/SD-01.2-investment-mandate-and-policy-definition.md).

**MFN (Most Favoured Nation)** — An LP's right (typically negotiated in a side letter) to elect any more favourable terms granted to other LPs in the same fund. Triggers reporting and election obligations.

**MOIC (Multiple on Invested Capital)** — Total value (realised plus unrealised) divided by invested capital, at the deal grain. The deal-level analogue of TVPI.

**MWR (Money-Weighted Return)** — A return measure that weights cash flows by their size and timing. IRR is the most common MWR. *See also* TWR.

## N

**NAV (Net Asset Value)** — The accounting value of a fund or portfolio's assets less its liabilities, on a stated valuation date. In private markets, NAV is interpretive — the four-lens pattern recognises that no single NAV is canonical at every grain.

**Net IRR** — IRR net of all fees and carried interest — the return an LP actually realises.

## P

**PME (Public Market Equivalent)** — A method of comparing a private-markets fund's return to a hypothetical investment of the same cash flows in a public-market index. Several variants (Long-Nickels, Kaplan-Schoar, Direct Alpha). *See* [SD-09.8 Private-Markets Performance Analytics](service-domains/BD-09-performance-and-analytics/SD-09.8-private-markets-performance-analytics.md).

**Portfolio (mandate)** — The container — the investor's capital organised into portfolios, mandates, sleeves, accounts. *See* [E-03 Portfolio / Mandate](entities/core/E-03-portfolio-mandate.md).

**Portfolio company** — A company a private-markets fund (or co-investment) holds an investment in. Modelled as a role of [E-01 Legal Entity](entities/core/E-01-legal-entity.md), not a separate master.

**Preferred return** — *See* Hurdle.

**Price and market data** — Observed market data — prices, yields, rates, FX — the observable inputs that value liquid holdings. *See* [E-08 Price & Market Data](entities/core/E-08-price-market-data.md).

**Private CUSIP** — A 9-character CUSIP issued for private-market securities (launched 2025). Coverage is early; OpenIM still assumes private markets lack a universal identifier.

## R

**Reference model** — What OpenIM is. A reference framework for organising capabilities and master data, not a design blueprint for a particular firm. Matches BIAN's positioning. *See* [PRIOR-ART.md](../PRIOR-ART.md) and [model/README.md](README.md).

**Recallable distribution** — A distribution the GP retains the contractual right to call back (typically during the investment period). Failing to track recallability inflates available-cash forecasts and breaks pacing models. *See also* Distribution.

**Record time / Record from / Record to** — The firm-time at which a fact was recorded, distinct from when it was true in the world. The bi-temporal companion of *effective time*.

**Return of capital** — A distribution type that gives back called capital, reducing the LP's cost basis. Distinguished from profit / gain distributions and recallable distributions.

**Risk limit** — A configured, versioned constraint on a measured risk — the threshold a measured value must stay within. *See* [E-16 Risk Limit](entities/core/E-16-risk-limit.md).

**Risk measurement** — A point-in-time risk result (VaR, sensitivity, exposure, stress loss), stored append-only with its method and provenance. *See* [E-19 Risk Measurement](entities/core/E-19-risk-measurement.md).

**RVPI (Residual Value to Paid-In)** — The GP-reported NAV of unrealised investments divided by total capital called. The unrealised-multiple — inherently uncertain because it depends on the GP's own marks. *See also* DPI, TVPI.

## S

**Secondaries** — Transactions in existing private-fund interests. **LP-led** — an LP sells its stake to a buyer. **GP-led** — the GP moves assets from a maturing fund into a new continuation vehicle and LPs elect to roll or take liquidity. *See* [SD-04.9 Exit & Realisation Management](service-domains/BD-04-direct-and-co-investment/SD-04.9-exit-and-realisation-management.md).

**Service Domain** — A discrete, non-overlapping unit of business capability — a single thing the firm does, owning the full lifecycle of one asset or entity type. The atomic unit of OpenIM's service-domain decomposition. *See* [model/service-domains/INDEX.md](service-domains/INDEX.md).

**Side letter** — A bilateral agreement between a GP and a specific LP modifying standard LPA terms — fee discounts, co-investment rights, enhanced reporting, MFN, key-person provisions. *See* [SD-10.5 Side-Letter & Fund-Term Compliance](service-domains/BD-10-investment-compliance-and-guideline-monitoring/SD-10.5-side-letter-and-fund-term-compliance.md).

**SSI (Standing Settlement Instruction)** — The pre-agreed settlement details (account, bank, custodian) for a counterparty, applied automatically to executed trades. *See* [SD-11.7 Bank Account & Mandate Administration](service-domains/BD-11-treasury-cash-and-collateral/SD-11.7-bank-account-and-mandate-administration.md).

**Subscription credit facility** — A fund-level credit line a GP draws against committed (but uncalled) LP capital, used to fund investments before issuing capital calls. Effect: inflates the GP-reported IRR. *See also* From-day-one IRR.

## T

**Transaction** — The universal investment event — trade, subscription, capital call, distribution, corporate action, transfer. *See* [E-05 Transaction](entities/core/E-05-transaction.md).

**TVPI (Total Value to Paid-In)** — The total-return multiple: DPI plus RVPI. As reliable as the RVPI component, which depends on the GP's own marks.

**TWR (Time-Weighted Return)** — A return measure that eliminates the effect of cash-flow timing, giving the manager's "skill return". The public-markets standard. *See also* MWR; IRR.

## V

**Valuation** — A point-in-time value of a holding and the method that produced it — observable price, mark-to-model, appraisal. Append-only. *See* [E-07 Valuation](entities/core/E-07-valuation.md).

**Vintage year** — The year a fund made its first investment. Critical to benchmarking because economic environment at deployment drives entry price.

## W

**Waterfall** — The algorithm in the LPA that splits fund distributions between LPs and GP: return of capital → preferred return → GP catch-up → split (typically 80/20) of subsequent profits.

**Waterfall (American)** — Carry calculated and paid deal-by-deal as exits occur.

**Waterfall (European)** — Carry calculated and paid on the fund as a whole, only after the LPs have received their committed capital back plus the preferred return.

## X

**XVA (Valuation Adjustments)** — Family of adjustments to a derivative's mid-market value to reflect credit, funding, capital and other costs (CVA, DVA, FVA, KVA, MVA). *See* [SD-08.5 Valuation Adjustments & Reserves](service-domains/BD-08-valuation-and-pricing/SD-08.5-valuation-adjustments-and-reserves.md).
