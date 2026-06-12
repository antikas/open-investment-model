# E-38 — Internal Credit Rating

The firm's own methodology-driven internal credit rating — the issuer or instrument, the rating, the rating methodology version, the analyst, the committee date, the change reason and the watch status. Versioned through rating-change events; the firm's independent credit view, distinct from and cross-checked against the external rating agencies.

## Purpose

A credit analyst's central output is a **rating** — the firm's own structured judgement of the creditworthiness of an issuer or an instrument, methodology-driven, kept current as a standing artefact. The rating is not a one-off analytical note; it is the standing view the firm holds and acts on, and it persists between the rating-change events that mutate it. SD-02.5 selects securities against the rating; SD-07.2 measures credit risk against it; SD-10.1 monitors mandate-rating constraints against it. The rating is the unit those consumers read.

The Internal Credit Rating is the record of one such rating — for an issuer or an instrument, at a methodology version, by an analyst, ratified by a credit committee on a date, with a stated change reason and a watch status. It is a standing record rather than a transient one, but its trajectory through time — the sequence of rating-change events — is the load-bearing history.

The entity is **versioned by rating-change event.** Each change — initial rating, upgrade, downgrade, affirmation, withdrawal — is a new row with its own `effective_from`; the prior version's `effective_to` is closed when the new version takes effect. The rating in force at any past date is read from the version whose effective range covers that date. The mandate-compliance audit, the back-tested credit-spread relationship, the rating-migration analytics all run on the version trajectory.

The rating is the firm's own — methodology-driven, traceable, defensible. It is cross-checked against the external rating agencies (Moody's, S&P, Fitch) but not derived from them; the internal rating may sit above, at, or below the consensus external view, and a divergence is the analyst's call to defend. The methodology is governed (held as a Metric Definition, E-22, versioned); the rating is the result the methodology produces.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `internal_credit_rating_id` | varchar | Primary key. |
| `subject_type` | varchar | What the rating is for — `issuer` (E-01 in the issuer role) / `instrument` (E-02, typically a specific debt instrument). |
| `subject_id` | varchar | The identifier of the subject — the issuer (E-01) or the instrument (E-02). |
| `rating_scale` | varchar | The internal rating scale — e.g. internal AAA–C, or IG–HY–distressed band scheme. The scale is the firm's; the convention is named here. |
| `rating_value` | varchar | The rating on the scale — the firm's grade for the subject (e.g. `A+`, `BB-`, `distressed`). |
| `rating_methodology_id` | varchar (FK → E-22) | The governed Metric Definition the rating was assigned under — the methodology version. |
| `rating_analyst` | varchar | The credit analyst responsible for the rating. |
| `rating_committee_date` | date | The date the credit committee ratified the rating decision. |
| `rating_change_reason` | varchar | The reason the rating version exists — `initial` / `upgrade` / `downgrade` / `affirmation` / `withdrawal`. |
| `rating_watch_status` | varchar | The watch status on the rating — `stable` / `positive_watch` / `negative_watch` / `developing`. |
| `effective_from` | date | The date this rating version takes effect. |
| `effective_to` | date | The date this version ceased to be effective; null while in force. |

## Notes

- **Versioned by rating-change event.** Each change is a new row; the prior version is closed by `effective_to`. The set of versions for a subject is its rating history, the substrate of rating-migration analytics and the audit trail of mandate-rating compliance. A rating that is reviewed and unchanged is recorded as an `affirmation` event with a new `rating_committee_date` — the affirmation is part of the history.
- **`rating_methodology_id` is the provenance hook.** Every rating version names the Metric Definition (E-22) it was assigned under — the methodology version in force. A change to the methodology that triggers re-rating creates new rating versions; the prior versions stay on file at their methodology, so the audit chain stays intact.
- **The rating is the firm's own and is distinct from external agency ratings.** Moody's, S&P and Fitch issue their own ratings; those are external data points the credit analyst consumes (typically through E-08 Price & Market Data or a dedicated rating-agency feed) and cross-checks against. The internal rating may agree, lead, lag or diverge; the divergence is the analyst's defended call.
- **`rating_watch_status` is the forward signal.** A rating itself reflects today's assessment; the watch flags an imminent change — `negative_watch` is a likely downgrade, `positive_watch` is a likely upgrade, `developing` is a directional change yet to resolve. Mandate-rating constraints often read on the rating-plus-watch combination.

## Out of scope

- The credit *research* the rating synthesises — the issuer analysis, the covenant review, the financial-model work — those are the SD-02.3 analytical artefacts; E-38 is the standing rating the research culminates in.
- The credit *risk measurement* the rating feeds — that is E-19 Risk Measurement on the `risk_type = credit` partition (owned by SD-07.2 Credit & Counterparty Risk Management); E-38 is the standing rating, not the point-in-time risk measure that consumes it.
- The credit *recommendation* — that is the SD-02.5 buy / sell / hold call; E-38 is the rating the recommendation references, not the recommendation itself.
- The external rating-agency rating — that is third-party data; E-38 is the firm's own internal rating, distinct from and cross-checked against the external view.
- The mandate-rating constraint itself — that is E-16 Risk Limit (typically `limit_type = mandate`, encoding a constraint such as "minimum internal rating BBB"); E-38 is the rating the constraint reads against.

## Owned and consumed by

- **Owned by:** SD-02.3 Credit Research & Analysis — the credit-research capability that runs the rating methodology, maintains the rating committee and owns the standing artefact.
- **Consumed by:** SD-02.5 Security Selection & Recommendation (the buy / sell / hold decision the rating feeds), SD-07.2 Credit & Counterparty Risk Management (the issuer-credit-risk and downgrade-watch view), SD-10.1 Investment Guideline Monitoring (mandate-rating constraints — minimum-rating limits, downgrade-triggered actions), SD-13.10 Investment Reporting & Dashboards (the rating-distribution and rating-migration analytics).

## Open extensions

- The rating methodology itself as a typed structure — moving beyond a Metric Definition reference to a structured representation of the rating model.
- The relationship between issuer ratings (the standing creditworthiness) and instrument ratings (which can differ from the issuer's where the instrument is structurally subordinated or enhanced).
- The cross-scale mapping — how the firm's internal scale aligns to the external agency scales for back-test and benchmark purposes.
- The rating-migration analytics on the version trajectory — the typed structures supporting the transition-matrix and survival-analysis questions the credit-research function runs.
