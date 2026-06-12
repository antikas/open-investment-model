# E-14 — External Identifier

A cross-reference from a master record's golden key to an identifier in an external system or data vendor. The structure that lets OpenIM enrich and reconcile against the outside world without surrendering its own key.

## Purpose

OpenIM's master records are keyed on internal golden keys, by design — external identifiers are unstable, incomplete in private markets, and non-interoperable across vendors. But the investor still has to *use* external identifiers: to pull enrichment from a data vendor, to match a record from an administrator or a market-data feed, to reconcile against a benchmark provider's universe, to file a regulatory return. The External Identifier entity is the cross-reference map that makes that possible — golden key on one side, the external system's identifier on the other — so external data can be joined in without an external identifier ever becoming a primary key.

The master records each carry an `external_ids` map as their in-record view; E-14 is the normalised, queryable form, one row per (record, external system) pair.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `external_id_record` | varchar | Primary key. |
| `subject_type` | varchar | Which master the identifier belongs to — `legal_entity` (E-01) / `instrument` (E-02) / `fund` (PM-01) / `portfolio_company` (PM-04). |
| `subject_id` | varchar | The golden key of the master record. |
| `external_system` | varchar | The system, vendor or scheme the identifier belongs to. |
| `external_id` | varchar | The identifier value in that system. |
| `id_type` | varchar | The kind of identifier — `LEI`, `ISIN`, `CUSIP`, `SEDOL`, `FIGI`, `private_cusip`, a company-registry number, a regulator filing ID, a vendor entity ID. |
| `verified` | boolean | Whether the mapping has been verified, or is a candidate match. |

## Notes

- The golden key is never an external identifier. E-14 keeps the external world reachable without compromising that.
- Identifier coverage is asymmetric and the model is built for it: liquid instruments and regulated legal entities largely *have* standard identifiers (ISIN, CUSIP, FIGI, LEI); private companies and private funds largely do not. E-14 holds whatever exists; the entity-resolution process leans on it where it is present and falls back to alias matching (E-13) where it is not.
- A single record commonly carries several external identifiers — the cross-reference is one-to-many by design.

## Out of scope

- The variant *names* a record has been seen under — that is E-13 Entity Alias; E-14 holds structured identifiers (LEI, ISIN, registry numbers), E-13 holds names.
- The master record an identifier belongs to — that is E-01 Legal Entity, E-02 Instrument / Asset, or a private-markets master (PM-01, PM-04); E-14 is the normalised cross-reference of those records.
- The internal golden key itself — E-14 maps a golden key *to* external identifiers; the golden key is never an external identifier and is owned by the master entity.

## Owned and consumed by

- **Owned by:** key-partitioned by the master kind the identifier attaches to. **SD-13.1 Instrument & Security Master** for instrument identifiers (ISIN, CUSIP, SEDOL, FIGI on instruments); **SD-13.2 Entity & Counterparty Master** for legal-entity identifiers (LEI, BIC, vendor entity codes); **SD-13.3 Investment Vehicle & Fund Master** for fund / vehicle identifiers. Each master's owning Service Domain is the sole authoritative source for the identifiers of its own population. The full pattern is documented in [`ownership-map.md`](../../ownership-map.md).
- **Consumed by:** the entity-resolution process (an exact external-ID match is the high-confidence first tier of resolution); SD-13.4 Market & Reference Data Management; SD-16.3 Regulatory Reporting & Filings; every domain that pulls external enrichment.

## Open extensions

- **Canonicality (declared).** E-14 is canonical for external identifiers; the `external_ids` map on each master (E-01, E-02, the fund master) — and the dedicated `isin` / `figi` columns on E-02 — is a declared denormalised read-cache, derivable from E-14 and regenerated from it, not an independent source. The normalised form is canonical because it carries the per-identifier provenance (`verified`, the source system) the map cannot.
- The verification workflow — how a candidate external-ID match becomes a verified one.
