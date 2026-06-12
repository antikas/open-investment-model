# E-11 — Classification Type & Value

The extensible taxonomy behind time-varying classifications — the definition of *what classifiers exist* and *what values are valid within each*. The reference data that E-12 Classification History records against.

## Purpose

OpenIM treats classification generically: department, credit rating, sector, strategy, geography and the rest are not special cases, they are instances of one pattern — a time-varying attribute on a holding or investment. For that to hold, the classifiers themselves must be **defined as data, not as schema**. E-11 is that data. Adding a new classifier type, or a new value within one, is a governance action — a new row — not a code change.

The entity has two parts: **Classification Type** (what classifiers exist) and **Classification Value** (the valid values within each, with their own effective dating — classifier values change too, as departments open and close and strategies are renamed and retired).

## Attribute schema — Classification Type

| Column | Type | Definition |
|---|---|---|
| `classification_type_key` | int | Primary key. |
| `classification_type_code` | varchar | The classifier code — e.g. `DEPT`, `CREDIT_RATING`, `SECTOR`, `STRATEGY`, `GEOGRAPHY`. |
| `description` | varchar | What the classifier is. |
| `owner` | varchar | Who governs this classifier's values. |

## Attribute schema — Classification Value

| Column | Type | Definition |
|---|---|---|
| `classification_value_key` | int | Primary key. The value `-1` is reserved for `UNKNOWN`. |
| `classification_type_key` | int (FK → Classification Type) | The classifier this value belongs to; null on the reserved `UNKNOWN` row, which applies to every type. |
| `value_code` | varchar | The natural code of the value within its type. |
| `value_label` | varchar | The display label. |
| `effective_from` | date | When this value became valid. |
| `effective_to` | date | When it was retired; null while active. |
| `superseded_by_key` | int (FK → self) | The replacement value, for a rename or merge; null otherwise. |

## The reserved UNKNOWN value

One Classification Value row is reserved, loaded at build time and never modified: key `-1`, code `UNKNOWN`, effective from an epoch date and never expiring. Every holding or investment with no resolved classification for a period joins to it. This keeps E-12's aggregations clean — they still sum to the total — while keeping every gap *visible and queryable* rather than silently null. When a real classification is recovered, the correct row is inserted and the placeholder superseded; the `UNKNOWN` row itself is permanent.

## Notes

- Classifier values are themselves **effective-dated**. A model that treats classifier values as static lookup data produces wrong results as the business evolves — a retired department must not vanish from a historical query.
- Generic by design: keeping classifier definitions in E-11 as data is the move that makes department, rating, sector, strategy and geography one problem rather than five.

## Out of scope

- The time-varying classification *records* against a holding or investment — that is E-12 Classification History; E-11 defines what classifiers and values exist, E-12 records which value applied when.
- The asset-class taxonomy specifically — that is E-09 Asset Class, a dedicated reference entity, not a generic classifier here.
- The governance workflow for adding a classifier type or value — named as an open extension; the entity carries the structure, not the process.

## Owned and consumed by

- **Owned by:** SD-13.7 Data Quality & Governance.
- **Consumed by:** E-12 Classification History (every classification record references a type and a value here); SD-09 Performance & Analytics and SD-13.10 Investment Reporting & Dashboards (the slicing dimensions); SD-01.11 Liquidity Strategy & Tiering governs the `LIQUIDITY_TIER` classifier type and its tier values as its policy artefact (SD-13.7 owns the entity; SD-01.11 governs this classifier's values), and SD-07.3 Liquidity Risk Management consumes the taxonomy to classify each holding.

## Open extensions

- The governance workflow for adding a classifier type or value.
- The relationship to standard external taxonomies (e.g. GICS for sector) — which classifier values are internal and which align to an external scheme.
