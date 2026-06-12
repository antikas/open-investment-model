# PM-13 — Investor Capital Account

The manager-side per-investor capital account in a fund the institution *operates* — the running record of one investor's contributions, distributions, allocated income and gain, and closing balance. The ILPA Capital Account Statement made first-class.

**Specialises:** E-03 Portfolio / Mandate (the operated-fund capital container, per investor). An investor's capital account is the per-investor view of the fund the institution operates — the share of the fund's capital attributable to one limited partner. It is the manager-side mirror of PM-06 LP Commitment, which is the investor-side record of the institution committing into someone else's fund. This entity activates only when the institution operates funds (it is the system of record SD-12.9 keeps for *its* investors); it is dormant otherwise.

> **Pack membership is by form of holding, not by asset class.** PM-13 sits in this pack because the manager-side per-investor capital account is the **operated-fund / closed-end-fund-vehicle form** — the running per-investor record a fund operator keeps. That form is used by a GP/LP private-asset fund, but also by a hedge-fund LPA structure (which keeps per-investor capital accounts with equalisation accounting) and by an open-ended-fund operator (a UCITS ICVC, a US '40-Act mutual fund, an ETF), which keep per-investor records of a different shape. The capability PM-13 names is therefore **fund-form-orthogonal**: it is a property of operating a fund, not of investing in a private-markets asset class. PM-13 specialises the closed-end-fund capital-account shape; the hedge-fund and open-ended-fund variants of the per-investor record are sibling future entities, not a contradiction of this one's placement.

## Purpose

When the institution operates a fund — as the GP or manager keeping the books for outside investors — it must maintain each investor's **capital account**: the running balance of what that investor has contributed, what it has been distributed, the income and gain allocated to it, and its closing capital. The Investor Capital Account is that per-investor record, rolled forward each period.

It is genuinely distinct from PM-06 LP Commitment, and the distinction is the GP / LP boundary. PM-06 is the **investor side** — the institution as a limited partner committing capital into a fund someone else manages, one commitment row per (fund, LP). PM-13 is the **manager side** — the institution operating the fund and keeping the running capital account for *its* investors. They are mirror images of the same economic relationship viewed from opposite ends of the GP / LP boundary: PM-06 is owned by the buy-side commitment process (SD-03.5), PM-13 by the fund-administration process (SD-12.9). An institution that both invests in funds and operates its own carries both.

It is the ILPA Capital Account Statement made first-class — the per-investor statement the operated fund issues, with the standard's contribution / distribution / allocation / closing-balance roll-forward.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `capital_account_id` | varchar | Primary key. |
| `fund_id` | varchar (FK → PM-01) | The operated fund the capital account is held in. |
| `investor_entity_id` | varchar (FK → E-01) | The investor whose capital account this is — a Legal Entity in the investor / LP role. |
| `period` | date | The period the capital account is struck *as of*; one record per (fund, investor, period). |
| `opening_balance` | decimal | The investor's capital balance at the start of the period. |
| `contributions` | decimal | Capital contributed by the investor during the period. |
| `distributions` | decimal | Capital and gain distributed to the investor during the period. |
| `allocated_income` | decimal | Income allocated to the investor's account during the period. |
| `allocated_gain` | decimal | Realised and unrealised gain allocated to the investor during the period. |
| `management_fee` | decimal | The management fee charged to the investor's account during the period. |
| `carried_interest` | decimal | Carried interest allocated away from the investor's account, where applicable. |
| `closing_balance` | decimal | The investor's capital balance at the end of the period — opening + contributions − distributions + allocated income + allocated gain − fees. |
| `currency` | char | The currency the capital account is denominated in. |

## Notes

- **Append-by-period.** One Investor Capital Account record is struck per (fund, investor, period); the roll-forward links each period's closing balance to the next period's opening. The history is the investor's full capital-account trajectory in the fund.
- The roll-forward — opening + contributions − distributions ± allocated income / gain − fees = closing — is the ILPA Capital Account Statement structure; the per-investor statements the operated fund issues are produced from these records.
- The manager-side / investor-side mirror with PM-06 is the roles model working across the GP / LP boundary: the same economic relationship is one record on each side, owned by the side that is the system of record for it.

## Out of scope

- The investor-side commitment into a fund someone else manages — that is PM-06 LP Commitment; PM-13 is the manager side, the per-investor account in a fund the institution itself operates.
- The fund's overall NAV — that is the fund-level E-07 Valuation (`method = manager_mark`) struck by SD-12.9; PM-13 is one investor's share of the fund's capital, not the fund's total value.
- The capital calls and distributions as events — those are PM-07 Capital Call and PM-08 Distribution; PM-13 is the per-investor running balance the events move, not the events.

## Owned and consumed by

- **Owned by:** SD-12.9 Fund Accounting & NAV.
- **Consumed by:** SD-16.2 Owner & Investor Reporting (the per-investor capital-account statements), SD-12.8 Capital Call & Distribution Processing, SD-16.1 Corporate & Fund Governance, SD-14.8 Internal Audit.

## Open extensions

- The fee-and-carry waterfall in full — the management-fee, carried-interest and hurdle mechanics that drive the allocations.
- Multiple share classes or LP cohorts within one operated fund, each with different economics.
- The relationship between the per-investor capital accounts and the fund-level NAV they reconcile to.
