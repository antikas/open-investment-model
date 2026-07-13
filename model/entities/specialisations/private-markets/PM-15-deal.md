# PM-15 — Deal / Investment Opportunity

The first-class record of a direct-investment opportunity — the deal — from the moment it is sourced to the moment it either dies or converts into a post-close record on the book. One row per opportunity; the record the BD-04 deal chain works on.

## Purpose

The BD-04 deal chain — origination, screening, diligence, structuring, IC approval, closing — is a sequence of capabilities that all act on *the same thing*: one sourced opportunity moving through a funnel. Until now that thing was an analytical artefact (SD-04.1's "deal pipeline"); the Deal / Investment Opportunity makes it a governed record. It carries the identity of the opportunity (what is being bought, from whom, under which sourcing thesis), the origination facts (who sourced it, how, when), the anticipated holding structure, and — once a deal closes — the typed conversion link to whichever post-close record the deal lands as: a fund/SPV investment position (PM-09), a direct loan (PM-14) or a direct real asset (RA-01). The pipeline questions ("what is in the funnel, at what stage, sourced through which channel, converting at what rate") are answerable from the record set rather than from a spreadsheet.

**Deal stage is deliberately not an attribute of this entity.** The stage a deal is at (sourced → screening → diligence → decision → committed / declined) is a *time-varying classification*, and the model already carries the machinery for exactly that: stage values are defined as E-11 Classification Type & Value data, and the dated stage history of each deal is E-12 Classification History rows against the `deal_id`. Putting a `stage` column on the deal would destroy the history the funnel analytics need; the classification pattern keeps every transition, bi-temporally. The same separation applies to the IC decision: the decision on a deal is an E-34 Investment Authorisation (`investment_route = direct_investment`, `subject_id` → the deal) — PM-15 carries no approve / decline attributes.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `deal_id` | varchar | Primary key. |
| `target_entity_id` | varchar (FK → E-01) | The target of the opportunity — the target company, the asset owner, or the borrower, each a role of the Legal Entity party master. |
| `deal_name` | varchar | The working name of the opportunity. |
| `strategy` | varchar | The sourcing thesis the deal was originated under — the sector / geography / deal-size-band / return-profile criteria of SD-04.1's thesis definition. |
| `originating_team` | varchar | The desk or team that sourced the opportunity. |
| `source_channel` | varchar | How the deal arrived — `proprietary` / `intermediated` / `gp_syndicated` (co-investment deal flow received from a GP and routed to SD-04.7). |
| `sourced_date` | date | When the opportunity entered the pipeline. |
| `structure` | varchar | The anticipated holding structure — `spv` / `direct` / `co_invest` / `jv` / `sma`, aligned to PM-05's `vehicle_type` values so an anticipated structure and the closed deal's actual vehicle speak the same vocabulary. |
| `converted_record_type` | varchar | What the conversion lands as — `fund_investment` (PM-09), `direct_loan` (PM-14) or `direct_real_asset` (RA-01); null until — and unless — the deal closes. |
| `converted_record_id` | varchar | The identifier of that post-close record — a PM-09, PM-14 or RA-01 identifier per `converted_record_type`; null until — and unless — the deal closes. |

## Notes

- **The conversion link is the funnel's exit edge — and it is typed.** A deal that closes becomes a deployed position, and the direct route closes into more than one shape of record: a company deal lands as a fund/SPV investment position (PM-09), a lending deal as a direct loan (PM-14), a real-asset deal as a direct real asset (RA-01). `converted_record_type` names which — the same subject-discriminator pattern E-12 (`subject_type` / `subject_id`) and PM-09 (`holding_type` / `target_id`) carry — and `converted_record_id` holds the identifier of that post-close record, so conversion analytics ("of the deals sourced under this thesis, which became positions, at what cycle time") join the pipeline to the book whatever the mode. A deal that dies simply never populates the pair — the record, and its stage history, remain as the funnel's memory.
- **The structure discriminator anticipates the holding layer.** `structure` uses PM-05's `vehicle_type` vocabulary (`spv` / `direct` / `co_invest` / `jv` / `sma`) — at sourcing it is the *anticipated* structure; the closed deal's actual legal vehicle is a PM-05 record. Keeping the vocabularies aligned means no re-mapping at conversion.
- **Deals have the private-markets identity problem.** Opportunities arrive from origination networks, intermediaries and GP syndication with no universal identifier — the same no-shared-key reality every private-markets master faces. The alias (E-13) / external-identifier (E-14) treatment for deal records is an open extension.

## Out of scope

- The deal stage — that is E-12 Classification History against the deal (stage values defined as E-11 data); PM-15 deliberately carries no stage column (see Purpose).
- The IC decision on the deal — that is E-34 Investment Authorisation with `subject_id` → the deal (`investment_route = direct_investment`); PM-15 is the subject of the authorisation, not the decision record.
- The screening memo, diligence pack, indicative model and term sheet — those are the analytical artefacts of SD-04.2, SD-04.3 and SD-04.4; PM-15 is the deal record they attach to, not the analysis itself.
- The target company, asset owner or borrower as a party — that is E-01 Legal Entity (and PM-04 Portfolio Company once a closed target is mastered); PM-15 references the target, it does not master it.
- The post-close records a deal converts into — PM-09 Fund Investment, PM-14 Direct Loan and RA-01 Real Asset, referenced through the `converted_record_type` / `converted_record_id` pair — and the PM-05 Legal Vehicle that holds them; PM-15 is the pre-commitment pipeline record.
- The manager / fund pipeline on the BD-03 route — that remains a Service-Domain artefact of SD-03.1 Manager Sourcing & Pipeline; PM-15 covers the direct-investment deal chain only.

## Owned and consumed by

- **Owned by:** SD-04.1 Deal Origination & Sourcing — origination creates the deal record and is the authoritative source for the pipeline; the record is then worked by the rest of the deal chain.
- **Consumed by:** SD-04.2 Deal Screening & Triage, SD-04.5 Investment Approval & Authorisation, SD-04.6 Deal Execution & Legal Closing.

## Open extensions

- Alias and external-identifier treatment for deals — deal records arrive from CRM-shaped sources with no universal identifier; whether deal identity gets the E-13 / E-14 treatment the party and fund masters have.
- The co-investment variant — whether a `gp_syndicated` deal needs co-investment-specific attributes (the GP's offer terms, the syndication clock) or whether those stay SD-04.7 artefacts.
- The BD-03 sibling — SD-03.1's manager pipeline remains an analytical artefact; whether it follows this entity's precedent is that Service Domain's open question.
- The deal economics — indicative ticket size and currency, expected close date — whether any snapshot belongs on the record at sourcing, or all of it stays with the time-varying screening and structuring artefacts.
