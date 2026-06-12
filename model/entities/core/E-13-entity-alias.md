# E-13 — Entity Alias

A name a master record has been seen under. The structure that makes entity resolution work — fed by the resolution feedback loop, read by it on the next cycle.

## Purpose

The same thing appears under many names across sources — a legal entity under variant names across data vendors and documents; a private company under one name in one manager's report and another in a second's; an instrument under different vendor descriptions; a manager under a historical name after a rebrand. The Entity Alias is the record of each such name. Collectively, the alias set for a master record is **accumulated institutional knowledge**: every alias is a name the platform has learned maps to a golden key. A long alias list is not clutter — it is why the unresolved queue shrinks over time.

The master records (Legal Entity E-01, Instrument E-02, and the private-markets masters) each carry a `known_aliases` array as their convenient in-record view; E-13 is the normalised, queryable form of the same information, with the provenance of each alias.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `alias_id` | varchar | Primary key. |
| `subject_type` | varchar | Which master the alias belongs to — `legal_entity` (E-01) / `instrument` (E-02) / `fund` (PM-01) / `portfolio_company` (PM-04). |
| `subject_id` | varchar | The golden key of the master record. |
| `alias_name` | varchar | The name the record was seen under. |
| `first_seen_at` | date | When this alias was first encountered. |
| `source` | varchar | Where the alias came from — a named manager report, an administrator statement, a data vendor, a market-data feed. |
| `confirmed_by` | varchar | The data steward who confirmed the alias maps to this record. |

## Notes

- Entity Alias is **append-only** — an alias, once learned, is kept. A record does not lose names; it accumulates them.
- The resolution feedback loop writes here: when a steward confirms an unresolved record is an existing entity under a new name, that name becomes an Entity Alias, and the next resolution cycle matches it automatically.
- Alias volume varies sharply by subject: a private portfolio company (no universal identifier) accumulates many aliases; a listed instrument with an ISIN accumulates few.

## Out of scope

- A cross-reference to a structured identifier in an external system or vendor scheme — that is E-14 External Identifier; E-13 holds the *names* a record has been seen under, E-14 holds its external *identifiers*.
- The master record an alias belongs to — that is E-01 Legal Entity, E-02 Instrument / Asset, or a private-markets master (PM-01, PM-04); E-13 is the normalised alias of those records, not the records themselves.
- A change in the entity behind a fund — a merger, rebrand or acquisition — that is PM-11 Manager Succession Event; a rebrand produces an alias here, but the event itself is PM-11.

## Owned and consumed by

- **Owned by:** key-partitioned by the master kind the alias attaches to. **SD-13.1 Instrument & Security Master** for instrument aliases; **SD-13.2 Entity & Counterparty Master** for legal-entity aliases; **SD-13.3 Investment Vehicle & Fund Master** for fund / vehicle aliases. Each master's owning Service Domain is the sole authoritative source for the aliases of its own population. The full pattern is documented in [`ownership-map.md`](../../ownership-map.md).
- **Consumed by:** the entity-resolution process behind every master; SD-13.6 GP & Manager Report Ingestion.

## Open extensions

- **Canonicality (declared).** E-13 is canonical for aliases; the `known_aliases` array on each master (E-01, E-02, the fund master) is a declared denormalised read-cache, derivable from E-13 and regenerated from it, not an independent source. The normalised form is canonical because it carries the per-alias provenance (`source`, `first_seen_at`, `confirmed_by`) the array cannot.
- Alias confidence — distinguishing a steward-confirmed alias from an auto-learned one.
