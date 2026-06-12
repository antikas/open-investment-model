# PM-06 — LP Commitment

A commitment of capital by a limited partner to a fund (PM-01). The foundational private-markets relationship: the LP pledges an amount, the fund draws it down over time through capital calls (PM-07).

## Purpose

A commitment is a promise of capital, not a transfer of it. The committed amount is drawn down gradually as the fund makes investments; the gap between committed and drawn — the **unfunded commitment** — is a liquidity obligation the investor must be able to meet on call. The commitment is the anchor for commitment pacing, unfunded-commitment liquidity modelling, and the J-curve. One commitment row exists per (fund, LP).

The commitment is a private-markets relationship with no equivalent in liquid investing — there is no "commitment" to a holding of listed shares. It is one of the entities that justifies a private-markets specialisation pack rather than a forced fit into the core.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `commitment_id` | varchar | Primary key. |
| `fund_id` | varchar (FK → PM-01) | The fund the capital is committed to. |
| `lp_entity_id` | varchar (FK → E-01) | The limited partner — a Legal Entity in the LP / investor role. |
| `committed_usd` | decimal | The amount of capital committed. |
| `commitment_date` | date | The date of the commitment (typically a fund close). |
| `currency` | char | The commitment currency. |

Derived, not stored: `unfunded_commitment` = `committed_usd` − cumulative capital called (PM-07); `called_pct` = cumulative called / committed.

## Notes

- **The LP may itself be a fund.** `lp_entity_id` is a Legal Entity (E-01) in the LP role — and a fund (PM-01) is itself a legal entity. When a **fund-of-funds** commits to an underlying fund, the fund-of-funds is the LP on that commitment: `lp_entity_id` points to the fund-of-funds' legal entity. The same fund-of-funds therefore appears in the model twice over — as a PM-01 Fund (the thing the investor holds) and, on each underlying commitment, as the committing LP here. This is the roles model working as intended: an entity is one record, the role is what the relationship records.
- One commitment row exists per (fund, LP) — whether the LP is the investing institution or another fund-of-funds in the chain.

## Out of scope

- The drawdown of committed capital — that is PM-07 Capital Call; PM-06 is the promise of capital, PM-07 is the demand against it.
- The return of capital and gain from a fund — that is PM-08 Distribution; PM-06 is the commitment, not the cash returned.
- The fund the capital is committed to — that is PM-01 Fund & Vehicle, referenced through `fund_id`; the committing LP is an E-01 Legal Entity in the LP role.
- The fund's economic terms governing the commitment's economics — those are PM-10 Fund Terms; multiple-close cohort variation is an open extension.

## Owned and consumed by

- **Owned by:** SD-03.5 Fund Commitment & Subscription.
- **Consumed by:** SD-01.10 Commitment Pacing & Deployment Planning, SD-05.6 Liquidity-Aware Portfolio Management, SD-11.6 Fund Finance & Capital-Call Liquidity, SD-09.7 Private-Markets Cash-Flow Forecasting, SD-12.8 Capital Call & Distribution Processing.

## Open extensions

- Multiple closes — a commitment made at first or a later close, with different economics per LP cohort (see PM-10 Fund Terms versioning).
- Commitment transfers and secondary sales of a commitment.
