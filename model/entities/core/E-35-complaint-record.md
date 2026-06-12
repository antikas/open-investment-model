# E-35 — Complaint Record

The regulated complaint record — the complaint, the acknowledgement, the investigation, the final response, the FOS-referral note, the redress, the root-cause categorisation and the systemic-finding flag. The FCA DISP record an inspection runs against, and the Consumer-Duty outcomes-evidence record.

## Purpose

A regulated firm must handle complaints to a regulated standard. The FCA DISP sourcebook prescribes the process (acknowledgement, investigation, final response within the regulated deadline), the Financial Ombudsman Service referral rights and the records retention; the UK Consumer Duty raises the standing obligation to act on the outcomes-evidence complaints surface. None of that is answerable from a transient case ticket — the regulator inspects the complaint record, and the firm must be able to show, for any complaint, what was said, when, by whom, and what root cause was found.

The Complaint Record is that record. It is a computed-metric-as-entity: a record that feeds a governance, audit or regulatory decision answerable only from a stored record, *and* one that recomputation may not reproduce. The complaint record meets both tests: an FCA inspection asks "show me the complaint, the final response and the root-cause categorisation" — the answer must come from a stored, append-by-update record, not from a recomputation that today's case-management system would no longer reproduce. The complaint stays on the record; the firm's responses are time-stamped against it; the outcomes evidence is the trajectory of records, not a current snapshot.

The capability runs the loop from individual case to root cause to systemic remediation: the `root_cause_classification` is the categorisation that ties an individual case to a recurring cause, and the `is_systemic_finding` flag is the signal that the cause has reached the threshold for cross-firm remediation. The single-case record carries both — the complaint *and* its place in the firm's outcomes evidence.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `complaint_id` | varchar | Primary key. |
| `client_entity_id` | varchar (FK → E-01) | The complainant client / investor, in the client / investor role of Legal Entity. |
| `complaint_received_date` | date | The date the complaint was received — the clock-start for the DISP deadlines. |
| `complaint_category` | varchar | The category of complaint — `suitability` / `service` / `charges` / `performance` / `mis-sale` / other. |
| `complaint_text` | text | The complaint as received, in the complainant's words. |
| `acknowledgement_date` | date | The date the firm acknowledged the complaint to the complainant. |
| `investigation_outcome` | text | The outcome of the firm's investigation — the finding, the basis for it, the remedy recommended. |
| `final_response_date` | date | The date the final response was issued — the regulated deadline ends here. |
| `final_response_text` | text | The final response issued to the complainant. |
| `fos_referral_provided` | boolean | Whether the FOS referral rights were provided in the final response, where applicable. |
| `redress_amount` | decimal | The redress paid to the complainant, where any was. |
| `root_cause_classification` | varchar | The root-cause category the complaint is tagged to — the categorisation that links the case to the firm's outcomes evidence. |
| `is_systemic_finding` | boolean | Whether the root cause has reached the threshold for systemic remediation across the firm. |
| `status` | varchar | `open` / `investigating` / `final_response_issued` / `escalated_to_fos` / `closed`. |

## Notes

- **Append-by-update on the case grain.** A complaint exists as one record updated through its lifecycle — acknowledgement, investigation, final response, FOS escalation, close. The status moves; the prior field values are not overwritten so much as added to (the acknowledgement date stays even after the final response is issued). A reopened complaint, or a subsequent stage in a multi-stage case, is recorded against the same `complaint_id`; a new complaint from the same client is a new record.
- **The DISP deadline runs on `complaint_received_date` and ends on `final_response_date`.** A complaint with no final response within the deadline is an open record the regulator can ask about; the record stays open until the response is issued or the case is closed.
- **The root-cause loop is what makes this more than a ticket system.** `root_cause_classification` is the field that turns an individual case into outcomes evidence — the audit reads complaints by category to find recurring causes. `is_systemic_finding` is the flag that surfaces a category for remediation; the firm's response to systemic findings is recorded outside the complaint set (in remediation programmes), but the flag is the link.
- **Consumer Duty's outcomes-evidence requirement reads on this record.** The firm must demonstrate that it has acted on the outcomes complaints surface; the complaint record set is the load-bearing evidence.

## Out of scope

- The unregulated client query, request or commercial dispute that does not meet the regulatory definition of a complaint — those sit on SD-15.13's client-servicing case record; E-35 is the regulated subset.
- The remediation programme that responds to a systemic finding — that is a separate firm-level response orchestrated through SD-14.2 Corporate Compliance & Conduct and the affected operational Service Domains; E-35 carries the flag, not the remediation.
- The Financial Ombudsman Service's own case record once the complaint is referred — that is the FOS's record, not the firm's; E-35 carries the firm-side record of escalation, the FOS case proceeds on its own track.
- The complaints management information aggregated across the record set — that is the MI SD-15.16 produces from the records and SD-14.2 / SD-16.3 consume; E-35 is the record-grain underneath, not the aggregated MI.

## Owned and consumed by

- **Owned by:** SD-15.16 Complaint & Client-Case Management — the first-line conduct-control capability that operates the FCA DISP process and the Consumer-Duty outcomes-evidence loop.
- **Consumed by:** SD-14.2 Corporate Compliance & Conduct (the complaints MI, the root-cause findings and the conduct-and-outcomes evidence), SD-16.3 Regulatory Reporting & Filings (the complaint statistics that feed the regulatory returns the firm owes), SD-15.14 Client & Investor Reporting (per-client reporting of complaint history where relevant), SD-14.8 Internal Audit (the as-handled record the audit reads).

## Open extensions

- The root-cause taxonomy in full — the standardised classification the categorisation runs against.
- The cross-jurisdiction equivalent regimes — how the DISP shape generalises to the SEC adviser-complaint regime, the MiFID II complaint-handling regime, the EU national variants.
- The systemic-remediation linkage — the structured relationship between a complaint record carrying `is_systemic_finding = true` and the remediation programme that closes the cause.
- The FOS referral sub-model — the structured record of the FOS case progression once the complaint is escalated.
