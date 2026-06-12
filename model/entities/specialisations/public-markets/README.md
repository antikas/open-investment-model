# Public-Markets Specialisation

**Maturity:** Provisional · broad — the pack covers the security master for listed equity and fixed income, the full order-to-settlement trade lifecycle as separable events, corporate-action processing, securities lending, and proxy voting.

The entity specialisation for **public / liquid-markets investing** — listed equities and fixed income, held directly or through separately managed accounts, traded on exchanges and through dealers, valued against observable prices.

This pack covers the security master for listed equity and fixed income, the order-to-settlement trade lifecycle, corporate-action processing, and index-constituent data. It is the liquid-markets counterpart to the [private-markets pack](../private-markets/README.md): where private markets have no universal identifiers and unstructured manager reporting, public markets have ISIN, CUSIP, SEDOL and FIGI on every instrument and standardised messaging across the lifecycle — so the master-data problem here is **normalisation across vendor feeds**, not entity resolution against a missing identifier.

## How this pack specialises the core

Every entity here specialises a [core entity](../../core/). The core says what is universal; the pack adds what is specific to public-markets investing:

- A **listed equity** and a **debt instrument** are each an Instrument / Asset (E-02). **PB-01** and **PB-02** add the listing, issue, coupon and issuer-relationship detail. For a bond the issuer relationship is load-bearing — the issuer *is* the credit exposure.
- The **trade lifecycle** is the expansion of a Transaction (E-05) of `transaction_type = trade`. The core names the trade as one event; the pack splits it into its real stages — **PB-03 Order** (intent), **PB-04 Execution** (the fill), **PB-05 Allocation** (the apportionment across portfolios), **PB-06 Settlement Instruction** (the final exchange of securities for cash).
- A **corporate action** is a Transaction (E-05) of `transaction_type = corporate_action` with its own mandatory / voluntary sub-model and key-date calendar — **PB-07**.
- An instrument's forward **income calendar** — coupons and dividends — is reference data on the instrument: **PB-08 Income Schedule**.
- A **market index's constituents** are the constituent expansion of Benchmark / Index (E-10) — **PB-09 Index Constituent**, effective-dated through rebalancing and reconstitution.

What this pack adds that the core does not have: the full order-to-settlement trade lifecycle as separable, individually-monitorable events; corporate-action processing with its date discipline and elections; the depth of the fixed-income issuer relationship; and the forward income schedule as data.

## Entities

| ID | Entity | Specialises | Role |
|---|---|---|---|
| PB-01 | [Listed Equity](PB-01-listed-equity.md) | E-02 Instrument / Asset | A listed share — issuer, listing venue, share class, free float. |
| PB-02 | [Debt Instrument](PB-02-debt-instrument.md) | E-02 Instrument / Asset | A government, agency, supranational or corporate bond — issuer (the credit), coupon, maturity, seniority. |
| PB-03 | [Order](PB-03-order.md) | E-05 Transaction | An instruction to buy or sell — the intent at the head of the trade lifecycle. |
| PB-04 | [Execution](PB-04-execution.md) | E-05 Transaction | A fill — a quantity traded in the market at a price, on a venue. |
| PB-05 | [Allocation](PB-05-allocation.md) | E-05 Transaction | The apportionment of an executed trade across the portfolios it was traded for. |
| PB-06 | [Settlement Instruction](PB-06-settlement-instruction.md) | E-05 Transaction | The instruction to exchange securities for cash and complete the trade. |
| PB-07 | [Corporate Action](PB-07-corporate-action.md) | E-05 Transaction | A mandatory or voluntary issuer event and its effect on the security and the holding. |
| PB-08 | [Income Schedule](PB-08-income-schedule.md) | E-02 Instrument / Asset | The forward calendar of contractual or expected income — a bond's coupons, an equity's dividends. |
| PB-09 | [Index Constituent](PB-09-index-constituent.md) | E-10 Benchmark / Index | The constituents and weights of a market index, effective-dated through rebalancing. |
| PB-10 | [Securities Loan](PB-10-securities-loan.md) | E-04 Holding / Position | A per-loan record of a lent security — borrower, fee, term, recall status; its collateral leg references E-26 Collateral Position. |
| PB-11 | [Proxy Vote](PB-11-proxy-vote.md) | E-05 Transaction | A per-(meeting, resolution, portfolio) vote record — recommendation, vote cast, rationale — for stewardship-code disclosure. |

## Design notes

- **The trade lifecycle is four entities, not one.** Order, execution, allocation and settlement are operationally distinct stages with different owners, different timing and different failure modes — mirrored in the wire formats (FIX order and execution-report messages, the ISO 20022 securities-settlement `sese` and corporate-events `seev` message families). The pack models them as siblings (PB-03 to PB-06), the same way the private-markets pack keeps Capital Call and Distribution separate rather than collapsing them. An Order is mutable while live; everything downstream of it is append-only.
- **The issuer is the credit.** For PB-02, the relationship to the issuing Legal Entity (E-01) is the join on which issuer-level credit-risk aggregation depends. One issuer is typically behind a whole curve of bonds.
- **Identifiers exist; the work is normalisation.** Public-markets instruments carry ISIN, CUSIP, SEDOL and FIGI. The security master's task is reconciling the same instrument across vendor feeds that use different identifiers, codes and classifications — not resolving it against no identifier at all.
- **Builds on FIBO.** PB-01 and PB-02 align to the FIBO Securities domain's equity and debt-instrument concepts. OpenIM references those semantics rather than re-defining what an equity or a bond *is*; the per-class mapping is recorded in [`../../../fibo-alignment.md`](../../../fibo-alignment.md).
- **Income as expectation vs realisation.** PB-08 holds the *forward* income calendar; PB-07 records each income event when it *occurs*. The two are deliberately distinct — a projected dividend on PB-08 firms into a declared PB-07 corporate action.

## Sources

The pack's research is grounded in:

- FIX Trading Community — implementation guide (the order and execution-report messages): <https://www.fixtrading.org/implementation-guide/>
- FactSet — FIX protocol pre-trade allocation: <https://insight.factset.com/fix-protocol-enables-pre-trade-allocation>
- ISO 20022 — securities message definitions (`setr` / `sese` / `semt` / `seev` families): <https://www.iso20022.org/iso-20022-message-definitions>
- DTCC — ISO 20022 corporate-actions messaging specifications: <https://www.dtcc.com/asset-services/corporate-actions-processing/iso-20022-messaging-specifications>
- Intrinio — modern security-master architecture (ticker / CUSIP / ISIN / FIGI normalisation): <https://intrinio.com/blog/modern-security-master-architecture-unifying-ticker-cusip-isin-and-figi-data-at-scale>
- FINOS — Securities & Issuer ID mapping: <https://www.finos.org/hubfs/SecRef_%20Securities%20&%20Issuer%20ID%20mapping_%20.pdf>
- Infosys BPM — corporate-actions processing, voluntary vs mandatory: <https://www.infosysbpm.com/blogs/financial-services/corporate-actions-processing.html>
- Nasdaq — index methodology (free-float weighting, rebalancing, reconstitution): <https://indexes.nasdaq.com/docs/Methodology_NDX.pdf>
- BIS CPMI — delivery-versus-payment in securities settlement systems: <https://www.bis.org/cpmi/publ/d06.pdf>
- Cognizant — the impact of T+1 accelerated settlement on corporate actions: <https://www.cognizant.com/uk/en/insights/blog/articles/the-impact-of-t-1-accelerated-settlements-on-corporate-actions>

See [PRIOR-ART.md](../../../../PRIOR-ART.md) for how the OpenIM entity model relates to FIBO, the identifier standards and the wider standards landscape.
