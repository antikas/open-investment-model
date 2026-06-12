# PB-11 — Proxy Vote

A per-(meeting, resolution, portfolio) record of a vote cast at a shareholder meeting — the recommendation, the vote cast, and its rationale. The structured, auditable form of the firm's voting record that stewardship-code disclosure requires.

**Specialises:** E-05 Transaction (`transaction_type = governance_action`). A vote is an instruction issued against a holding, the way a trade is issued against an instrument — an action the investor takes as owner. It is tied to the meeting event (PB-07 Corporate Action, the meeting), the resolution being voted, and the portfolio (E-03) that holds the shares as at the record date. One vote record exists per (meeting, resolution, portfolio).

## Purpose

When the investor holds shares it has the right and, increasingly, the obligation to vote them at the issuer's meetings. Each vote is one instruction, on one resolution, at one meeting, for one portfolio's holding — and the firm must be able to **publish its voting record**: how it voted, on what, and why. The Proxy Vote is the structured record of that vote, kept at the (meeting, resolution, portfolio) grain that the disclosure obligation needs.

It exists as an entity, not as activity logging, because the UK Stewardship Code and equivalent regimes require the firm to disclose its voting record in a form that can be reported, aggregated and audited — "how did we vote on every resolution, and was it consistent with our policy." The crisp grain (one instruction per meeting-resolution-portfolio) and the hard disclosure obligation are what make it a first-class entity, where the softer-edged stewardship engagement — a free-form, multi-interaction case record — is carried as document metadata and classification rather than as a master.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `vote_id` | varchar | Primary key. |
| `meeting_id` | varchar (FK → PB-07) | The shareholder meeting — a PB-07 Corporate Action of the meeting kind. |
| `resolution_ref` | varchar | The resolution being voted on at the meeting. |
| `portfolio_id` | varchar (FK → E-03) | The portfolio whose holding is being voted; one vote row per portfolio, since portfolios may split. |
| `holding_qty_at_record_date` | decimal | The quantity held as at the meeting's record date — the votes the portfolio is entitled to. |
| `recommended_vote` | varchar | The recommended vote under the firm's voting policy. |
| `proxy_adviser_rec` | varchar | The proxy adviser's recommendation, where one was obtained. |
| `cast_vote` | varchar | The vote actually cast — `for` / `against` / `abstain` / `withhold` / `split`. |
| `policy_basis` | varchar | The voting-policy basis the vote was cast on. |
| `rationale` | varchar | The rationale for the vote, especially where it departs from the recommendation or the adviser. |
| `conflict_flag` | boolean | Whether a conflict of interest was identified and managed for this vote. |
| `lodged_date` | date | When the vote was lodged. |
| `confirmation_status` | varchar | `pending` / `lodged` / `confirmed` / `rejected` — confirmation the vote was received against the deadline. |

## Notes

- A Proxy Vote is **append-only** — a vote, once cast and lodged, is a fact; an amended vote before the deadline is a new record, and the lodged record is retained for disclosure.
- The per-portfolio grain matters: the firm may **split** its vote across portfolios — voting one way for a portfolio with a stewardship mandate and another for an index portfolio — so the vote is recorded per (meeting, resolution, portfolio), not once for the firm.
- The `rationale` and the departure from `proxy_adviser_rec` are the stewardship-disclosure content: the firm must be able to show not just how it voted but why, and where it overrode an adviser's recommendation.

## Out of scope

- The meeting event itself — that is PB-07 Corporate Action (the meeting), referenced through `meeting_id`; PB-11 is the vote cast at the meeting, not the meeting.
- The holding that confers the voting right — that is E-04 Holding / Position as at the record date; PB-11 carries the entitled quantity, not the position record.
- The free-form stewardship engagement — meetings, letters, escalation with an issuer — that is carried as Document Metadata (E-15) and classification, not as a master entity; PB-11 is the crisp-grained vote, its softer sibling is not an entity.

## Owned and consumed by

- **Owned by:** SD-12.12 Proxy Voting & Stewardship Operations.
- **Consumed by:** SD-16.2 Owner & Investor Reporting (stewardship-code voting disclosure), SD-10.9 ESG & Sustainability Compliance, SD-16.1 Corporate & Fund Governance, SD-14.8 Internal Audit.

## Open extensions

- The split-vote sub-model in full — the rules by which a firm's vote is split across portfolios and mandates.
- The engagement-to-vote link — connecting a vote to the stewardship engagement that informed it.
- The voting-policy model — the codified policy `recommended_vote` is derived from.
