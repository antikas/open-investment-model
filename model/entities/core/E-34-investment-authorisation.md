# E-34 — Investment Authorisation

The Investment Committee's authorisation record — the recommendation memorandum the committee saw, the decision, the conditions, the authority-and-mandate verification and the dissent. One concept, two co-equal owning routes: the fund-commitment IC (SD-03.9) and the direct-investment IC (SD-04.5).

## Purpose

Every institutional investor runs investment decisions through a governance gate — the Investment Committee — and the IC's authorisation is the authority any subsequent execution depends on. SD-03.5 cannot proceed with a fund commitment without the SD-03.9 IC's approval; SD-04.6 cannot proceed with a direct-investment close without the SD-04.5 IC's approval. The authorisation is the chain of custody between diligence and close — what the IC saw, what it decided, on what date, with what conditions, against what authority. None of that is answerable from a transient process record — the governance audit trail must be answerable from a stored authorisation.

The Investment Authorisation is that record. It is a computed-metric-as-entity: a record that feeds a governance, audit or regulatory decision answerable only from a stored record, *and* one that recomputation may not reproduce. The authorisation meets both tests: the regulator and the board must be able to ask, of any executed commitment or deal, "show me the IC memorandum the committee saw, its decision and its conditions" — and the answer must be a stored record, not a recomputation that today's pipeline would no longer produce. The authority-and-mandate verification, the dissent, the conditions of approval and the recommended-versus-approved commitment amount are the as-decided record the audit reads.

The entity is **one concept, two co-equal owning routes** — the second co-owned entity in the model after E-27 Liability Profile. The fund-commitment IC (SD-03.9) and the direct-investment IC (SD-04.5) are structurally parallel governance gates over different deal chains: a real firm may operate one IC body across both routes or two separate bodies, but the model carries the capability as one entity with the `investment_route` field naming which IC route an authorisation came from. The `investment_route` is **not a partition key** — there is no schema authority either route holds over the other, and either route's authorisation is a complete instance in its own right. It is co-ownership outright, in the E-27 pattern: two views of the same kind of governance record, jointly the authoritative source for it.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `authorisation_id` | varchar | Primary key. |
| `investment_route` | varchar | The IC route the authorisation came from — `fund_commitment` (SD-03.9) / `direct_investment` (SD-04.5). The route, not a partition key. |
| `subject_type` | varchar | What `subject_id` resolves against — `fund` (PM-01) on the fund-commitment route; `deal` (PM-15), `portfolio_company` (PM-04) or `real_asset` (RA-01) on the direct route. |
| `subject_id` | varchar | The subject of the authorisation — for `fund_commitment`, FK → PM-01 (the fund); for `direct_investment`, FK → PM-15 (the deal / investment opportunity the committee is deciding), PM-04 (the portfolio company) or RA-01 (the real asset). |
| `ic_memorandum_ref` | varchar (FK → E-15) | The IC memorandum the committee saw, referenced through Document Metadata. |
| `decision` | varchar | The IC's decision — `approve` / `approve_with_conditions` / `decline` / `defer`. |
| `conditions` | text | The conditions attached to an `approve_with_conditions` decision — side-letter outcomes, structuring revisions, diligence items that must close before execution proceeds. |
| `committee_meeting_date` | date | The date of the committee meeting at which the decision was taken. |
| `dissent_record` | text | The recorded dissent — committee members who voted against or abstained, and the recorded reasons; the structured minute of the discussion's substance. |
| `authority_verification_note` | text | The note confirming the firm's corporate authority to enter the commitment / deal — the board / committee delegation under which the IC acts. |
| `mandate_fit_note` | text | The note confirming the commitment / deal fits the mandate, the asset allocation and the pacing plan in force. |
| `recommended_commitment_amount` | decimal | The commitment amount the memorandum recommended. |
| `approved_commitment_amount` | decimal | The commitment amount the committee approved — may differ from recommended where the committee scales the decision. |
| `approval_date` | date | The date the approval was recorded (typically the committee-meeting date; may differ for written-procedure approvals). |
| `status` | varchar | `draft` / `under_review` / `decided` / `superseded`. |

## Notes

- **The subject set, per route.** Each owning route reads the same `subject_id` contract from its own side. For the **fund-commitment route (SD-03.9)** the subject is the fund (PM-01) — unchanged by the deal-record extension. For the **direct-investment route (SD-04.5)** the subject set includes the deal itself (PM-15 Deal / Investment Opportunity) — the natural subject now that the pipeline record is first-class, since the IC decides *a deal*, and may do so before the target is mastered — alongside the portfolio company (PM-04) and the real asset (RA-01) for authorisations framed directly against a mastered target. Extending the subject set is a change to the shared schema both co-owners hold jointly; neither route's own subjects were altered by it. Because the subject set spans four masters, `subject_type` is the discriminator that names which master a given `subject_id` resolves against — the same typed-reference pattern E-12 (`subject_type` / `subject_id`) and PM-09 (`holding_type` / `target_id`) carry.
- **Co-owned by SD-03.9 and SD-04.5.** One concept, two co-equal owners, the fund-commitment view and the direct-investment view of the same kind of governance record. There is no key attribute that assigns an instance to one owner or the other — `investment_route` records which route an authorisation came from, but it is not a partition key in the E-04 / E-25 / E-29 sense (no schema authority is split). The full pattern is documented in [`ownership-map.md`](../../ownership-map.md), and is the same pattern E-27 Liability Profile follows.
- **The IC memorandum is the load-bearing artefact.** The memorandum (referenced through `ic_memorandum_ref`) is the synthesis document the committee was asked to decide against — the GP / deal summary, the thesis, the diligence findings, the proposed structure, the recommended commitment. The authorisation record points at the memorandum the committee actually saw; a revised memorandum after the decision is a new memorandum, not a mutation of this one.
- **`recommended_commitment_amount` and `approved_commitment_amount` carry the as-decided record.** Where the committee scales a recommendation, both numbers are stored — the audit answers "what was the firm recommending versus what was the firm approving" from a record.
- **`status = superseded`** is the close on an authorisation revised by a later IC decision (a re-decision after material change in conditions, a top-up commitment authorised separately). The set of authorisations against a subject is the as-decided history.

## Out of scope

- The diligence work the memorandum synthesises — that is the SD-03.3 (ODD) / SD-03.4 (IDD) artefacts for the fund-commitment route, the SD-04.3 diligence pack for the direct-investment route; E-34 carries the decision the diligence informs, not the diligence work itself.
- The legal close the authorisation enables — that is the SD-03.5 (fund commitment) / SD-04.6 (deal closing) operation; E-34 is the authority the close runs under, not the close itself.
- The commitment record on the funds-flow side — that is PM-06 LP Commitment (for fund commitments) or the post-close direct holding (for direct investments); E-34 is the authorisation behind the commitment, not the commitment record itself.
- The IC pipeline and cadence — those are SD-03.9 / SD-04.5's operational artefacts; E-34 is the as-decided record of one IC decision, not the pipeline of decisions.
- The deal record the direct route decides on — that is PM-15 Deal / Investment Opportunity, referenced through `subject_id`; E-34 is the decision *against* the deal, not the deal itself.

## Owned and consumed by

- **Owned by:** co-owned by **SD-03.9 Fund-Commitment Approval & Authorisation** (the IC gate for the fund-commitment route in BD-03) and **SD-04.5 Investment Approval & Authorisation** (the IC gate for the direct-investment route in BD-04) — a single concept with two co-equal owners, the fund-commitment IC view and the direct-investment IC view of the same kind of governance record. The full pattern is documented in [`ownership-map.md`](../../ownership-map.md), and parallels E-27 Liability Profile.
- **Consumed by:** SD-03.5 Fund Commitment & Subscription (the fund-route execution that runs under the authorisation), SD-04.6 Deal Execution & Legal Closing (the direct-route execution that runs under the authorisation), SD-12.8 Capital Call & Distribution Processing (the funds-flow side of fund commitments), SD-16.1 Corporate & Fund Governance (the governance machinery the IC operates within), SD-14.8 Internal Audit (the as-decided record the audit reads).

## Open extensions

- The conditional-approval sub-model — the precise contract between an `approve_with_conditions` decision and the downstream gate that verifies the conditions have been satisfied before execution proceeds.
- The IC Memorandum entity — whether the memorandum itself warrants first-class status alongside the authorisation, or remains a Document Metadata reference.
- The cross-route consolidated IC — how a firm running one IC body across both routes consolidates the authorisations at the implementation level (the model carries the capability as one entity; the operational structure is an implementation matter).
- The relationship to the SD-01.10 pacing-plan-in-force when the authorisation was taken — whether the pacing-plan version is stored on the authorisation.
