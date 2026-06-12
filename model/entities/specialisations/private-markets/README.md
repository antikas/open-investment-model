# Private-Markets Specialisation

**Maturity:** Provisional · broad — the deepest of the four packs; the closed-end-fund-vehicle form of holding in full depth, look-through to portfolio companies and fund-agreement economics as computable data, plus directly-originated private credit

The entity specialisation for the **private, illiquid, no-universal-identifier shape** an institutional investor's holding takes — the closed-end-fund-vehicle form of holding in full depth (the form used by GP/LP private-asset funds, and the form a hedge-fund LPA structure also takes), plus directly-originated private credit (PM-14) which shares the same form-of-holding properties (private, illiquid, no universal identifier, structured monitoring against borrower / GP reports). An institutional investor commits capital to closed-ended funds run by external managers (GPs), invests directly and through co-investments in private companies and assets, and originates private loans alongside or independently of fund vehicles.

This pack is organised by **form of holding**, not by asset class — it is the closed-end-fund-vehicle form, the direct-private-credit form and the look-through to underlying companies, orthogonal to the [E-09 asset-class taxonomy](../../core/E-09-asset-class.md) (a private-equity, private-credit, real-estate, infrastructure or hedge-funds exposure can all be held in this form). The form-of-holding membership is why the manager-side per-investor record **PM-13 Investor Capital Account** belongs here: keeping per-investor capital accounts is a property of *operating a closed-end fund* — used by a GP/LP private-asset fund and by a hedge-fund LPA structure alike — not a private-markets-asset-class phenomenon; the open-ended-fund operator's per-investor record is a sibling future entity.

The private-markets data problem — no universal identifiers, unstructured manager reporting, look-through exposure — is the one with the least existing standardisation, which is why the pack is built to this depth.

## How this pack specialises the core

Every entity here specialises a [core entity](../../core/). The core says what is universal; the pack adds what is specific to the closed-end-fund-vehicle and direct-private-credit forms of holding:

- A **fund interest** is an Instrument / Asset (E-02) of class `fund_interest`. **PM-01 Fund & Vehicle** specifies the fund behind it.
- A **GP**, a **fund administrator** and a **portfolio company** are each a Legal Entity (E-01) in a role. **PM-02**, **PM-03** and **PM-04** add the structure each role needs.
- A **capital call** and a **distribution** are each a Transaction (E-05) with a cash consequence (E-06). **PM-07** and **PM-08** add the private-markets structure.
- A **fund NAV** is a Valuation (E-07) with `method = manager_mark`. The pack records the NAV trajectory and the multiples derived from it.

What the pack adds that the core does not have: the **commitment** relationship (capital pledged but not yet transferred), the **look-through** from an LP's fund interest to the fund's own holdings in companies, and the **LPA economics** as computable data.

## Entities

| ID | Entity | Specialises | Role |
|---|---|---|---|
| PM-01 | [Fund & Vehicle](PM-01-fund-and-vehicle.md) | E-02 Instrument / Asset | The fund and its main / parallel / feeder / co-invest / continuation vehicles, plus the Fund Family grouping. |
| PM-02 | [GP / Management Company](PM-02-gp-management-company.md) | E-01 Legal Entity (manager role) | The external manager — branded firm, management company, per-fund GP entity. |
| PM-03 | [Fund Administrator](PM-03-fund-administrator.md) | E-01 Legal Entity (administrator role) | A counterparty master for fund administrators and the operational metadata of dealing with them. |
| PM-04 | [Portfolio Company](PM-04-portfolio-company.md) | E-01 Legal Entity (portfolio-company role) | The underlying operating company — the unit of look-through exposure; the hardest master. |
| PM-05 | [Legal Vehicle / SPV](PM-05-legal-vehicle.md) | — | The legal structure through which a private investment is held. |
| PM-06 | [LP Commitment](PM-06-lp-commitment.md) | — | A commitment of capital by an LP to a fund — committed, drawn, unfunded. |
| PM-07 | [Capital Call](PM-07-capital-call.md) | E-05 Transaction | A drawdown event against a commitment. |
| PM-08 | [Distribution](PM-08-distribution.md) | E-05 Transaction | A return of capital or gain from a fund to its LPs. |
| PM-09 | [Fund Investment](PM-09-fund-investment.md) | E-04 Holding / Position | A fund's holding in a portfolio company — the look-through unit. |
| PM-10 | [Fund Terms](PM-10-fund-terms.md) | — | The LPA economic terms, modelled as computation-as-data. |
| PM-11 | [Manager Succession Event](PM-11-manager-succession-event.md) | — | A change in the manager entity behind a fund. |
| PM-12 | [Benchmark Cross-Reference](PM-12-benchmark-cross-reference.md) | E-10 Benchmark / Index | The mapping from an internal fund to an external benchmark provider's peer universe. |
| PM-13 | [Investor Capital Account](PM-13-investor-capital-account.md) | E-03 Portfolio / Mandate | The manager-side per-investor capital account in a fund the institution operates — the ILPA Capital Account Statement made first-class. Activates only for operated funds. |
| PM-14 | [Direct Loan](PM-14-direct-loan.md) | E-02 Instrument / Asset (`instrument_class = direct_loan`) | A directly-originated private loan — borrower, facility terms, covenants, drawn / undrawn position, interest accrual, workout state. The post-close lifecycle entity for direct private credit. |

## The LP

The investing institution in its LP role, and any external LPs, are **Legal Entities** (E-01) in the `investor` / LP role — there is no separate LP entity. An LP Commitment (PM-06) references the committing entity through E-01.
