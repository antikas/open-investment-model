# PM-04 — Portfolio Company

The underlying operating company an investor holds exposure to — directly, through one or more funds, or both. The unit of **look-through exposure**, and the hardest master in OpenIM.

**Specialises:** E-01 Legal Entity, in the `portfolio_company` role. PM-04 adds the private-markets-specific structure — the look-through relationships, the cross-manager overlap, the company-lineage tracking.

## Why it is the hardest master

Without a portfolio company master, an investor cannot aggregate exposure across vehicles — and that aggregation is the foundation of concentration-risk monitoring, sector-exposure analysis and CIO reporting. The same company is routinely held through a fund, a co-investment vehicle alongside it, and a separate fund from another manager. The arithmetic of total exposure is simple once the entities match; the entire difficulty is *recognising it is the same company*.

It is hard because: **no universal identifier** (most private companies have no LEI, ISIN or CUSIP — Private CUSIPs are emerging but early); **same company, different names** across managers and after rebrands; **multi-manager overlap** is common; and **companies change** through mergers, acquisitions and spin-offs, so the master must track lineage.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `company_id` | varchar | **Golden key** (also the `entity_id` of the Legal Entity in the portfolio-company role). |
| `company_name` | varchar | Canonical name. |
| `known_aliases` | array | Every name the company has been seen under across manager reports, co-invest documents, administrator statements (the in-record view of E-13). |
| `sector` | varchar | Industry classification (GICS or an internal scheme). |
| `sub_sector` | varchar | Finer-grained industry classification. |
| `country` | varchar | Primary jurisdiction. |
| `lei` | varchar | Legal Entity Identifier, where one exists; most private companies have none. |
| `external_ids` | map | PitchBook, Preqin, Companies House, SEC CIK, vendor entity IDs, Private CUSIP (the in-record view of E-14). |
| `status` | varchar | `active` / `exited` / `merged` / `acquired`. |
| `successor_company_id` | varchar (FK → self) | The surviving entity after a merger or acquisition; null while active. Carries the lineage. |
| `gp_relationships` | array | The managers (PM-02) that report this company — enables cross-manager overlap detection. |
| `first_seen_at` | date | When the investor first encountered this entity. |
| `last_reviewed_at` | date | Date of the last steward review. |
| `reviewed_by` | varchar | The data steward who last reviewed the record. |

## Resolution

Three-tier matching — exact identifier match, alias / normalised-name match, steward review queue. Portfolio companies carry the **highest unresolved volume** of any master, especially early in a manager relationship — every new manager brings a wave of company names. The master gets smarter every cycle: alias lists grow, unresolved volume falls.

## Out of scope

- The generic party master a portfolio company specialises — that is E-01 Legal Entity in the `portfolio_company` role; PM-04 adds the look-through, overlap and lineage structure.
- A fund's *holding* in a company — that is PM-09 Fund Investment; PM-04 is the company, not the fund's position in it.
- A real asset an investor holds directly — that is RA-01 Direct Real Asset; PM-04 is strictly a company reached through a fund, not a directly-owned asset.
- The variant names a company has been seen under in normalised form — that is E-13 Entity Alias, of which PM-04 carries only the in-record `known_aliases` view.

## Owned and consumed by

- **Owned by:** SD-13.2 Entity & Counterparty Master.
- **Populated via:** SD-13.6 GP & Manager Report Ingestion (companies are discovered as managers report on them).
- **Consumed by:** SD-07.5 Look-Through Exposure Analysis, SD-07.4 Concentration & Exposure Risk, SD-04.8 Portfolio-Company Stewardship & Value Creation, SD-09.5 Investment Analytics & Insight, SD-13.9 ESG & Sustainability Data.

## Open extensions

- The full `gp_relationships` sub-structure — relationship type (equity / credit / co-invest), first and last reported dates.
- The lineage model — a company-event sub-entity behind `successor_company_id`.
- The relationship to PM-09 Fund Investment, the look-through holding.
