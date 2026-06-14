# E-15 — Document Metadata

The metadata and provenance of a source document — a manager report, a capital-account statement, an LPA, an IC paper, a trade confirmation, a prospectus. Links a source document to the durable record it concerns.

## Purpose

Much of what an institutional investor knows arrives as documents — and in private markets, much of it arrives *only* as documents. The Document Metadata entity is not the document; it is the structured record *about* the document: what it is, when it was filed, what it concerns, where it sits. It exists for two reasons. First, **provenance**: every extracted data point — a valuation, a capital call, a fund term, a holding — should be traceable to the document it came from. Second, **retrieval**: linking a document to the durable record it concerns (and to the classification context of E-12) is what lets unstructured content be queried in the *correct* context.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `document_id` | varchar | Primary key. |
| `document_type` | varchar | Manager / quarterly report, capital-account statement, LPA, side letter, IC paper, capital-call notice, trade confirmation, prospectus, AGM minutes, etc. |
| `subject_type` | varchar | What the document concerns — `legal_entity` / `instrument` / `portfolio` / `holding` / `fund` / `fund_investment`. |
| `subject_id` | varchar | The durable identifier of the record the document concerns. |
| `filing_date` | date | When the document was filed or received. |
| `as_of_date` | date | The date the document's content is *as of* (a Q1 report filed in Q2 is as-of Q1). |
| `storage_path` | varchar | Where the document is held. |
| `source` | varchar | Where the document came from — a manager portal, an administrator, a broker, internal filing. |

## Notes

- The link from a document to a *durable* identifier is the load-bearing part. Where an operational identifier is not durable, the document resolves to the durable key (E-13), so historical documents stay correctly attached through identifier changes.
- Document Metadata is the on-ramp record for SD-13.6 GP & Manager Report Ingestion — the ingestion pipeline reads the document, the metadata records what was read — and the provenance anchor for every domain that consumes extracted data.
- E-15 covers both documents *received* by the firm (manager reports, capital-account statements, LPAs, trade confirmations) and documents *issued* by the firm that are filed or furnished to a counterparty or authority (investor tax statements, regulatory filings). The filing-status lifecycle and correction chain are attributes of the issued-document case.

## Out of scope

- The document content itself — E-15 is the structured record *about* a document, not the document; the file is held at `storage_path`, not in this entity.
- The data points extracted from a document — a valuation, a capital call, a fund term — those are E-07, PM-07, PM-10 and the other entities; E-15 is the provenance anchor they trace back to.
- The legal and economic terms abstracted from a contract — those are PM-10 Fund Terms, RA-03 Lease / Tenancy and DR-03 Master Agreement; E-15 records that the document exists, not its parsed terms.

## Owned and consumed by

- **Owned by:** SD-13.11 Document & Content Management.
- **Consumed by:** SD-13.6 GP & Manager Report Ingestion, and — as the provenance anchor — every domain that consumes extracted data (valuation, transactions, fund terms).

## Open extensions

- The provenance link from an extracted data point back to the document and the specific field it was extracted from.
- The relationship to E-12 classification context for context-correct retrieval of historical documents.
