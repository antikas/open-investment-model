# E-37 — ESG Compliance Result

A stored point-in-time ESG-compliance result — the SFDR Article 6/8/9 classification, the EU Taxonomy alignment percentage, the PAI indicators, the mandate ESG-screen pass/fail, the stewardship-code disclosure conformance — for one subject, as of one date, on a stated methodology version. The ESG analogue of Risk Measurement (E-19) and Performance Result (E-20): append-only, with provenance.

## Purpose

A regulated investment firm must disclose, defend and stand behind ESG-compliance positions. SFDR (Regulation (EU) 2019/2088) requires the firm to classify each fund against Article 6, Article 8 or Article 9, report Principal Adverse Impact indicators on the prescribed quantitative templates, and stand behind those positions in periodic disclosures. The EU Taxonomy Regulation requires the alignment percentage to be reported against the binding criteria. The UK Stewardship Code requires the firm to evidence its stewardship activity. The US SEC ESG-disclosure regime applies the Marketing Rule and the Names Rule to ESG claims. All of those rules ask the same question: "what ESG-compliance position did you report, on what date, on what methodology" — and the answer must come from a stored record.

The ESG Compliance Result is that record. It is a computed-metric-as-entity: a record that feeds a governance, audit or regulatory decision answerable only from a stored record, *and* one that recomputation may not reproduce. The ESG result meets both tests: a regulator inspects the SFDR disclosure pack the firm filed and asks the firm to defend the Article-8 classification, the Taxonomy alignment percentage and the PAI indicator values; the answer must come from a stored result, computed on the underlying ESG measurement set (E-21) and the methodology (E-22) as they stood at the as-of date, not from a recomputation that today's data and today's methodology would no longer reproduce. The ESG data shifts (providers revise, methodologies update); the as-disclosed position cannot.

Like E-19 Risk Measurement and E-20 Performance Result, an ESG Compliance Result is **append-only** — a re-assessment for a later date is a new row, never an overwrite. The set of results for a subject is its ESG-compliance history.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `esg_compliance_result_id` | varchar | Primary key. |
| `subject_type` | varchar | What the result is for — `portfolio` (E-03) / `fund` (PM-01) / `composite` (a GIPS or ESG composite). |
| `subject_id` | varchar | The identifier of the subject — the portfolio, fund or composite the result is computed against. |
| `as_of_date` | date | The date the result is *as of*. |
| `sfdr_article_classification` | varchar | The SFDR Article classification — `article_6` (general) / `article_8` (light-green) / `article_9` (dark-green) / `n_a` (where SFDR does not apply). |
| `taxonomy_alignment_percentage` | decimal | The EU Taxonomy alignment percentage — the share of the subject's eligible activity that is taxonomy-aligned against the binding criteria. |
| `pai_indicators` | document (JSON) | The Principal Adverse Impact indicators — the prescribed PAI indicator set computed against the subject, per the SFDR Regulatory Technical Standards. |
| `mandate_esg_screen_result` | varchar | The result of the mandate-coded ESG screen — `pass` / `fail` / `breach`. |
| `breach_details` | text | Details of any breach — the failed screen, the breaching position, the source data; null where `mandate_esg_screen_result = pass`. |
| `metric_definition_id` | varchar (FK → E-22) | The governed Metric Definition the result was computed to — the methodology version in force. |
| `computed_by_sd` | varchar | The Service Domain that computed the result — `SD-10.9`. |

## Notes

- **Append-only.** The set of ESG Compliance Results for a subject is its compliance history. A re-assessment — run because the underlying ESG data was refreshed, the methodology was updated, or a periodic disclosure period closed — is a new row; the prior is retained.
- **`metric_definition_id` is the provenance hook.** Every stored result names the Metric Definition (E-22) version it was computed to — the methodology version. A change to the methodology does not silently rewrite the as-disclosed history; the audit chain stays intact.
- **The PAI indicator set is structured data, not free text.** The SFDR RTS prescribes a fixed set of indicators against quantitative templates; `pai_indicators` carries the structured-document grammar (the indicator values, the data coverage percentages, the explanatory narrative where the RTS allows). The full schema for `pai_indicators` is an open extension.
- **The mandate ESG screen sits alongside the SFDR / Taxonomy disclosure.** The same result record carries both the regulatory-disclosure position (SFDR, Taxonomy, PAI) *and* the mandate-compliance position (the client-mandated ESG screens, exclusions and tilts). They share an as-of date and a methodology version; both are part of the ESG-compliance picture for the subject.
- **The disclosure-gate Service Operation runs over the result set.** SD-10.9 gates each periodic SFDR / Taxonomy disclosure pack against the stored results before the disclosure is filed; the result entity is what makes the gate operational.

## Out of scope

- The underlying ESG data itself — that is E-21 ESG Measurement (the multi-provider, multi-pillar data point set owned by SD-13.9); E-37 is the stored *compliance result* computed against E-21, not the data.
- The investment-risk view of climate exposure — that is the `risk_type = climate` partition of E-19 Risk Measurement (owned by SD-07.8 Climate Risk Analytics); E-37 is the regulatory- and mandate-compliance position, not the risk measurement.
- The proxy-vote and stewardship-engagement record — those are PB-11 Proxy Vote and E-15 Document Metadata (the engagement records); E-37 carries the *conformance result* of the stewardship-code disclosure compliance, not the underlying voting and engagement events.
- The *definition* of an ESG metric — how Taxonomy alignment is computed, how a PAI indicator is defined — that is a Metric Definition (E-22) in the semantic layer; E-37 is the stored result, not the definition.
- The disclosure pack itself — the SFDR / Taxonomy disclosure filed with the regulator is a document the firm produces from the result set; E-37 is the underlying result the disclosure draws on, not the disclosure document.

## Owned and consumed by

- **Owned by:** SD-10.9 ESG & Sustainability Compliance — the second-line compliance capability that maps portfolios against the SFDR / Taxonomy regime, enforces mandate ESG constraints and runs the disclosure-gate controls.
- **Consumed by:** SD-13.10 Investment Reporting & Dashboards (internal ESG-compliance reporting and dashboards), SD-16.4 Financial Reporting & Disclosure (the firm's own sustainability-disclosure record where it consumes the product-level results), SD-16.5 Sustainability & Stewardship Governance (the governance picture of the firm's sustainability position), SD-10.8 Compliance Breach Management & Remediation (where a `mandate_esg_screen_result = breach` triggers the breach-handling lifecycle).

## Open extensions

- The structured grammar for `pai_indicators` — the typed schema of the SFDR PAI indicator set against the RTS templates.
- The cross-regime mapping — how the SFDR Article classification, the SEC ESG-disclosure regime, and the UK Sustainability Disclosure Requirements share a result record or are separated.
- The relationship to E-21 ESG Measurement — whether the result carries provenance back to the specific E-21 records that fed each indicator.
- The composite-level result computation — how an aggregate result for a GIPS or ESG composite relates to the individual portfolio results that roll into it.
