# PB-01 — Listed Equity

A share in a company admitted to trading on a regulated exchange or multilateral trading venue — the equity-class instrument an institutional investor holds directly or through a separately managed account.

**Specialises:** E-02 Instrument / Asset (`instrument_class = listed_equity`). A position in a listed share is a Holding (E-04) in an Instrument of class `listed_equity`; PB-01 is the entity that carries the listing, share-class and issuer detail behind that instrument. It aligns to the FIBO Securities domain's equity concepts (FBC/SEC) — OpenIM references those semantics rather than re-defining what an equity *is*.

## Purpose

A listed equity is the most standardised instrument an investor holds: it has universal identifiers, an observable price, and a public issuer. The entity exists to carry the attributes the core E-02 record deliberately leaves to the specialisation — the listing (which venue, under which local code), the share class (ordinary, preference, restricted, multiple-voting), and the explicit relationship to the issuing Legal Entity. Unlike the private-markets masters, the hard problem here is **not** entity resolution against a missing identifier; it is **normalisation** — the same share appears under a ticker in one feed, a CUSIP in a settlement workflow, an ISIN in a regulatory report and a FIGI in a market-data platform, and the security master must reconcile them to one golden record.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `instrument_id` | varchar (FK → E-02) | **Golden key.** The core Instrument / Asset record this equity specialises. |
| `issuer_entity_id` | varchar (FK → E-01) | The issuing company, as a Legal Entity in the `issuer` role. |
| `share_class` | varchar | `ordinary` / `preference` / `restricted` / `class_a` / `class_b` / `adr` / `gdr` — the class, including multiple-voting and depositary-receipt forms. |
| `primary_listing_mic` | varchar | ISO 10383 Market Identifier Code of the primary listing venue. |
| `local_code` | varchar | The exchange-local trading code (ticker) on the primary venue. |
| `isin` | varchar | International Securities Identification Number. |
| `cusip` | varchar | CUSIP, where the security is North American. |
| `sedol` | varchar | SEDOL, where the security trades on a UK / Irish venue. |
| `figi` | varchar | Share-class FIGI; the composite FIGI links the venue-level FIGIs of the same share class. |
| `trading_currency` | char | The currency the listing trades in. |
| `country_of_incorporation` | varchar | The issuer's country of incorporation — distinct from the listing country. |
| `shares_outstanding` | decimal | Total shares in issue — the denominator for market-cap and index-weight calculation. |
| `free_float_pct` | float | The proportion of shares available to public investors, after strategic and locked-up holdings. |
| `gics_sector` | varchar (FK → E-11) | Industry classification (the in-record view of a Classification, E-11 / E-12). |
| `voting_rights_per_share` | decimal | Votes attached to a share of this class — material for stewardship and dual-class structures. |
| `status` | varchar | `active` / `suspended` / `delisted`. |

## Notes

- A single company may be the issuer of **several** PB-01 records — multiple share classes, and the same class cross-listed on more than one venue. They share an `issuer_entity_id`; the issuer is one E-01, not one per listing.
- A depositary receipt (ADR / GDR) is modelled as its own PB-01 with `share_class = adr` / `gdr` and its own identifiers; its relationship to the underlying ordinary share is an open-extension cross-reference, not a merge.
- `free_float_pct` and `shares_outstanding` are the inputs PB-09 Index Constituent consumes to compute float-adjusted index weights; they are effective-dated through E-12 because both change with corporate actions.
- Identifier normalisation, not resolution, is the master-data work — see the pack README.

## Out of scope

- The generic instrument record a listed equity specialises — that is E-02 Instrument / Asset of `instrument_class = listed_equity`; PB-01 carries only the listing, share-class and issuer detail E-02 leaves to the specialisation.
- The issuing company itself — that is E-01 Legal Entity in the `issuer` role; one company may issue several PB-01 records, sharing one `issuer_entity_id`.
- A tradable debt security — that is PB-02 Debt Instrument; PB-01 is the equity-class instrument only.
- The dividend stream on an equity — that is PB-08 Income Schedule; PB-01 carries the static share attributes, not the income calendar.

## Owned and consumed by

- **Owned by:** SD-13.1 Instrument & Security Master.
- **Populated via:** SD-13.4 Market & Reference Data Management (vendor reference-data feeds).
- **Consumed by:** SD-06.1 Order Management, SD-06.2 Trade Execution, SD-08.1 Security Pricing, SD-07.1 Market Risk Management, SD-09.2 Performance Attribution, SD-12.6 Corporate Actions Processing, SD-13.5 Benchmark & Index Data Management.

## Open extensions

- The depositary-receipt-to-underlying cross-reference, and the fungibility ratio between them.
- The relationship between PB-01 and PB-08 Income Schedule for the dividend stream.
- The concrete FIBO Securities (equity instrument) concept mapping.
