# E-23 — Extraction Record

The versioned record of what was parsed from a source manager document — the extracted fields, their validation status and confidence, and a reference to the source document (E-15). The provenance entity for data captured from unstructured manager reports.

## Purpose

A large part of a private-markets data estate arrives as documents — capital-account statements, GP quarterly reports, distribution notices — that must be parsed into structured fields. The figure that ends up in the model (a called amount, a reported NAV, a distribution) was *extracted* from a specific document, by a specific process, at a specific time, and either validated or flagged. The Extraction Record is the record of that extraction: what was read, from which document, with what confidence, and whether it passed validation.

It extends the model's computed-metric-as-entity principle from *computed* figures to *parsed* ones. Where E-19 Risk Measurement and E-07 Valuation store a figure because recomputation may not reproduce it, the Extraction Record stores a figure because re-extraction may not reproduce it — the source document, the parsing model and the validation rules all change over time, and audit must be able to answer "what did we read from this PDF, when, and did it validate." The captured figures populate the entities other Service Domains own (a capital call, a distribution, a valuation); the Extraction Record is the provenance trail behind that population.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `extraction_record_id` | varchar | Primary key. |
| `document_id` | varchar (FK → E-15) | The source document the fields were extracted from. |
| `source_type` | varchar | The kind of document — `capital_account_statement` / `gp_quarterly_report` / `distribution_notice` / `capital_call_notice` / `valuation_statement`. |
| `as_of_period` | date | The reporting period the extracted figures are *as of*. |
| `extracted_fields` | document (JSON) | The structured set of fields parsed from the document — the field names and values, in the computation-as-data spirit. |
| `extraction_method` | varchar | How the fields were extracted — `manual` / `template` / `model` (an automated parse). |
| `model_id` | varchar | The extraction model behind an automated parse — the link to model governance (SD-14.4); null for a manual extraction. |
| `confidence_score` | float | The confidence of the extraction, where the method warrants one. |
| `validation_status` | varchar | `pending` / `validated` / `flagged` / `rejected` — the outcome of the steward and rule-based validation. |
| `version` | varchar | The version of the extraction; a re-extraction of the same document and period is a new version. |
| `extracted_at` | timestamp | When the extraction was performed. |

## Notes

- **Versioned, append-by-version.** A re-extraction of the same document for the same period — a corrected parse, a re-run under an improved model — is a new version; the prior extraction is retained, so an extracted figure stays traceable to the exact parse that produced it.
- `document_id` ties every extraction back to its source document (E-15), and `model_id` ties an automated parse to the model that produced it — so a parsing model later found to be flawed can be traced to every figure it extracted.
- The Extraction Record is the provenance layer, not the destination: the validated figures populate the capital calls (PM-07), distributions (PM-08), valuations (E-07) and capital accounts (PM-13) the owning Service Domains record; the Extraction Record records *that they were read from this document, this way*.

## Out of scope

- The structured business records the extracted figures populate — capital calls (PM-07), distributions (PM-08), valuations (E-07), investor capital accounts (PM-13) — those are owned by their respective Service Domains; E-23 is the provenance of the parse, not the records it feeds.
- The source document itself — its metadata, storage and provenance — that is E-15 Document Metadata, referenced through `document_id`; E-23 is what was *read from* the document.
- The data-quality rule the extraction is validated against — that stays a Service-Domain artefact of SD-13.7; E-23 carries the `validation_status` outcome, not the rule.

## Owned and consumed by

- **Owned by:** SD-13.6 GP & Manager Report Ingestion.
- **Consumed by:** SD-12.8 Capital Call & Distribution Processing, SD-12.9 Fund Accounting & NAV, SD-08.3 Private-Asset Valuation, SD-14.8 Internal Audit, SD-13.7 Data Quality & Governance.

## Open extensions

- The field-level lineage from an Extraction Record to each business record it populates.
- The re-extraction model — how a corrected parse relates to the figures already populated from the prior version.
- The `extracted_fields` document grammar per source type.
