# PM-10 — Fund Terms

The economic terms of a fund as set by its Limited Partnership Agreement (LPA) — hurdle, management fee, carried interest, clawback, preferred return. Modelled as **computation-as-data**: each term is a first-class entity carrying a *definition* the platform can evaluate, not a scalar the platform hopes is right. Versioned by effective date.

## The problem this entity solves

LPA economic terms are richer than any fixed schema can express. Management fees step down after the investment period and can vary by LP cohort. Carried interest can ratchet on an IRR threshold. Hurdle rates can themselves be functions — of fund size, of vintage, of time. A schema with a `hurdle_rate FLOAT` column captures none of this; it forces the real terms into a scalar and the true calculation ends up in a notes field, or in one person's memory. That is unauditable and it does not survive the person leaving.

## The pattern — computation-as-data

OpenIM models every LPA economic term as a definition with a `definition_type` and, where the term is not a simple scalar, a structured `formula_spec`. A term is either **FIXED** (a scalar `fixed_rate`) or **COMPUTED** (a structured `formula_spec` the calculation engine interprets). A carry or distribution calculation reads `definition_type` and interprets either the scalar or the specification. Adding a fund with a bespoke formula adds a *row*, not a code path. The terms are data — queryable, versioned, auditable: for any historical distribution you can point to the exact term definition in effect on that date.

## Structure — the Fund Terms model

`FundTerms` is the versioned parent; each economic term is a child entity carrying its own definition.

```
FundTerms (terms_id, fund_id, effective_from, effective_to, version, source)
    ├── HurdleDefinition          — the preferred-return threshold before carry
    ├── ManagementFeeDefinition   — the fee, including step-downs and cohort variation
    ├── CarryDefinition           — carried interest: catch-up, waterfall type, ratchets
    ├── ClawbackDefinition        — the clawback provision: lookback period, conditions
    └── PreferredReturnDefinition — the preferred-return calculation method
```

## Attribute schema — FundTerms (parent)

| Column | Type | Definition |
|---|---|---|
| `terms_id` | varchar | Primary key. |
| `fund_id` | varchar (FK → PM-01) | The fund these terms govern. |
| `effective_from` | date | When this version of the terms became effective. |
| `effective_to` | date | When it was superseded; null while current. |
| `version` | int | The version sequence for the fund's terms. |
| `source` | varchar | `LPA` (authoritative, document-backed), `VERBAL_CONFIRMATION` (business-acknowledged, triggers a data-quality flag until document-confirmed), or a data vendor (a rounded approximation, a starting point only). |

## Attribute schema — term definitions (the children)

Each term definition shares the computation-as-data shape. The hurdle is the worked example:

| Column | Type | Definition |
|---|---|---|
| `hurdle_id` | varchar | Primary key. |
| `terms_id` | varchar (FK → FundTerms) | The version of the fund terms this belongs to. |
| `definition_type` | varchar | `FIXED` or `COMPUTED`. |
| `fixed_rate` | float | The scalar rate, when `FIXED`; null otherwise. |
| `formula_spec` | document (JSON) | The structured calculation specification, when `COMPUTED`; null otherwise. |

`ManagementFeeDefinition`, `CarryDefinition`, `ClawbackDefinition` and `PreferredReturnDefinition` follow the same shape, each adding the attributes its term needs, all keeping the FIXED-or-COMPUTED discipline.

## Versioning

Terms change — at each fund close, at LPA amendments, at step-down points. `FundTerms` is a **versioned entity**: a change inserts a new row with `effective_from` set to the change date and closes the prior row. No history is overwritten. Any historical carry or distribution can be recomputed with the term definition that was actually in force.

## The fee-boundary across fund forms

PM-10 is the fee *definition* for the closed-end LPA form. The boundary across the three-layer chain holds the same way for both open-ended and closed-end funds: (1) fee *definition / schedule* lives on PM-10 (closed-end) and on `FO-02.class_fee_schedule` (open-ended share/unit classes); (2) fee *computed amount* is FO-06 Fee Accrual, produced and owned by SD-12.11 Expense, Fee & Carry Processing, which reads PM-10 or FO-02 but never duplicates the formula; (3) NAV *booking* of the accrual is SD-12.9 Fund Accounting & NAV, which consumes FO-06. No formula is duplicated; no figure is double-owned. The `formula_spec_ref` field on FO-06 is a provenance pointer back to the PM-10 `terms_id` (or FO-02 schedule-version token) that produced the accrual — not a typed FK, consistent with the FO-02/PM-10 precedent for bare provenance pointers.

## Out of scope

- The fund the terms govern — that is PM-01 Fund & Vehicle, referenced through `fund_id`; PM-10 is the economic terms, not the fund.
- The authoritative LPA document the terms are sourced from — that is the document held under SD-14.9 Legal & Contract Management and recorded by E-15 Document Metadata; PM-10 is the parsed, structured terms.
- The actual capital calls and distributions the terms govern the economics of — those are PM-07 Capital Call and PM-08 Distribution; PM-10 is the term definitions, not the events.
- Per-LP-cohort side-letter overrides on the terms — handled by SD-10.5 and named as an open extension, not part of the FundTerms structure.

## Owned and consumed by

- **Owned by:** SD-13.3 Investment Vehicle & Fund Master (the structured term data).
- **Sourced from:** SD-14.9 Legal & Contract Management (the LPA is the authoritative document).
- **Consumed by:** SD-12.11 Expense, Fee & Carry Processing, SD-09.8 Private-Markets Performance Analytics, SD-03.4 Fund Investment Due Diligence, SD-12.15 Transfer Agency & Investor Dealing (the dealing frequency, cut-off and pricing basis govern subscription and redemption order processing).

## Open extensions

- The full attribute schema for each of the five term definitions.
- The `formula_spec` document grammar — the typed vocabulary a COMPUTED term is expressed in.
- Per-LP-cohort term variation — side-letter overrides (SD-10.5) on fund terms.
- This entity is the canonical model's worked example of **P4 — Legal Document Intelligence**.
