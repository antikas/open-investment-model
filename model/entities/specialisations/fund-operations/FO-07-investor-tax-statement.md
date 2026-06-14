# FO-07 — Investor Tax Statement

The issued-and-filed tax reporting document the fund or its transfer agent produces for an investor at the close of a tax year — the filed artefact of record for investor-level tax reporting obligations (1099-DIV/B, K-1, 1042-S, UK tax vouchers, FATCA/CRS per-investor classification reports, and equivalents).

**Specialises:** E-15 Document Metadata. The investor tax statement is a filed document of record: it has a document type (form_type), a subject (the investor), a filing date, and a lifecycle (prepared / filed / corrected / superseded). Each FO-07 row is one statement for one investor for one tax year, as issued. It references the figures of record that produced it — FO-03 Investor Unitholding, FO-05 Fund Distribution Event, FO-04 Dealing Order, and E-32 Tax Lot — rather than duplicating any of those figures.

**Why E-15 Document Metadata, not E-05 Transaction or the computed-figure family.** A tax statement is a filed document of record, not a holding-changing event. E-05 Transaction is the universal investment event — anything that changes a holding, from which positions are derived. A tax statement changes no holding, settles nothing, and has no counterparty in the transactional sense; almost no E-05 column (`transaction_type`, `portfolio_id`, `instrument_id`, `quantity`, `amount_usd`, `settlement_date`, `counterparty_entity_id`) maps coherently to a tax statement. The correct parent is E-15 Document Metadata — the entity that models filed documents of record. E-15's `document_type`, `subject_type`, `subject_id`, and `filing_date` map directly to FO-07's `form_type`, investor, and `filing_date`. E-15's scope covers both source documents received by the firm and documents issued by the firm; the investor tax statement is the issued case. The computed-figure family (E-07 Valuation, E-19 Risk Measurement, E-20 Performance Result, FO-06 Fee Accrual) is also not the parent: the reported figures in FO-07 are derived-at-issue snapshots and not the entity's essence — the entity's essence is the filing metadata and the correction chain, which are attributes of the filed document, not of a computed result.

**Why this is a stored entity and not a derived design note.** The figures that feed an investor tax statement (distributions, gains, income, withholding) all derive from FO-05, FO-04, FO-03, and E-32. The investor's tax *obligation* as computed from those figures is derivable. But the **issued document and its filing status** are not derivable from the underlying figures: whether the 1099-DIV has been filed, whether a corrected 1099 (re-issued with the CORRECTED checkbox) has been issued, the IRS submission reference, the tax year, the form type, and the FATCA/CRS reporting classification for this investor in this period — these are attributes of the filed artefact, not of the underlying transaction events. The filing itself (submitting to the IRS, to HMRC, to the OECD exchange) is a manager-side obligation with its own liability; the proof-of-filing is the record. The same SSOT principle that makes a filed NAV-per-unit record distinct from a recomputed figure applies here: the filed tax statement is the figure-of-record, not the computation that produced it.

## Purpose

A fund that issues securities to investors acquires tax-reporting obligations that run at the investor grain. For a US-resident investor in a mutual fund: the fund's transfer agent or administrator issues a **1099-DIV** (ordinary dividends and qualified dividends), a **1099-B** (proceeds from redemptions, with cost basis and holding period for funds that track lot-level data), and a **1042-S** for foreign-person withholding where applicable. For an LP investor in a partnership-structured fund: the fund issues a **K-1** (Schedule K-1 of Form 1065) carrying the investor's distributive share of income, gain, loss, deduction and credit. For cross-border reporting: the fund's FATCA classification and the OECD CRS per-investor report are issued to the relevant tax authority.

Each of these is a **filed document** with a tax authority or a legal obligation to furnish to the investor. It carries a filing date, a correction status, a form type, and in many cases an IRS or revenue-authority submission reference. The figures inside it derive from the fund's records (distributions from FO-05, redemption proceeds from FO-04, cost basis from FO-03 and E-32); the document's existence and its filing status do not.

FO-07 is the manager-side record of what was issued and filed. It stores the filing metadata, references the underlying figure-of-record entities that fed the computation, and carries the correction lifecycle. It is the proof-of-issue the firm's tax function (SD-17.4) needs to demonstrate it has met its investor-tax-reporting obligations.

FO-07 is distinct from:

- **FO-05 Fund Distribution Event** — the income distribution declaration and pay event. FO-05 is the event record; FO-07 references FO-05 distributions to characterise the income as ordinary, qualified, return-of-capital, or capital gain in the tax statement.
- **FO-04 Dealing Order** — the subscription, redemption, transfer or switch event. FO-07 references FO-04 redemption events where the statement must report proceeds and cost basis.
- **FO-03 Investor Unitholding** — the register position. FO-07 uses FO-03 to identify the investor and their period-opening and period-closing holding.
- **E-32 Tax Lot** — the per-lot cost basis and holding period record owned by SD-12.17. FO-07 references E-32 for the cost-basis and holding-period computation that populates the 1099-B or K-1 gain/loss lines; it does not duplicate the lot records.
- **SD-16.3 Regulatory Reporting & Filings** — SD-16.3 is the regulatory filing function (the submission to the regulator). FATCA and CRS reports are investment-tax-reporting obligations that sit with SD-17.4; SD-17.4 produces FO-07 and routes the filing through SD-16.3 where a formal regulatory-filing workflow is required.

## Attribute schema

### Identity and relationship

| Column | Type | Definition |
|---|---|---|
| `tax_statement_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for this investor tax statement record. |
| `investor_entity_id` | varchar (FK → E-01) | The investor to whom the statement is issued — a Legal Entity in the investor / unitholder role. For omnibus registrations, this is the legal holder of record. |
| `fund_product_id` | varchar (FK → FO-01) | The fund from which the statement is issued. |
| `unitholding_id` | varchar (FK → FO-03) | The investor's register position in the fund as of the close of the tax year. The primary link to the investor's unit record. |

### Filing metadata

| Column | Type | Definition |
|---|---|---|
| `form_type` | varchar | The tax form or report type issued: `1099-DIV` / `1099-B` / `K-1` / `1042-S` / `FATCA-report` / `CRS-report` / `UK-tax-voucher` / `other`. The form type determines the filing regime and the authority the statement is filed with or furnished to. |
| `tax_year` | int | The calendar or fiscal tax year the statement covers (e.g. `2024` for the tax year ended 31 December 2024). |
| `filing_status` | varchar | The lifecycle state of the statement: `prepared` (produced, not yet filed or furnished) / `filed` (submitted to the relevant tax authority or furnished to the investor within the regulatory deadline) / `corrected` (a correction has been issued; the original is superseded by the `corrects_statement_id` reference) / `superseded` (this record has been replaced by a correcting statement). |
| `filing_date` | date | The date the statement was filed with the tax authority or furnished to the investor. Null while `filing_status = prepared`. |
| `corrects_statement_id` | varchar (FK → FO-07, self-ref) | Where `filing_status = corrected`, the `tax_statement_id` of the original statement this record corrects. A corrected 1099 or K-1 is a legally distinct filing that supersedes the original; the chain of originals and corrections is tracked here. Null for original filings. |
| `submission_reference` | varchar | The tax authority's or filing agent's reference for this submission (e.g. the IRS acknowledgement number for an electronic FATCA filing). Null where not applicable or not yet received. |

### Reportable figures (by reference, not by duplication)

| Column | Type | Definition |
|---|---|---|
| `tax_classification` | varchar | The investor's tax classification for this fund and tax year as determined by the FATCA or CRS regime: `US-person` / `non-US-specified-US-person` / `NFFE` / `FFI` / `exempt-payee` / `CRS-reportable` / `not-reportable`. Governs which reporting regime applies. |
| `total_ordinary_income` | decimal | The investor's total ordinary income (dividends, interest, short-term capital gains) reported on the statement for the tax year, in `currency`. Derived from FO-05 distribution events and FO-04 dealing events over the period; carried here as the reported figure, not as a recomputable input — the same figure-of-record principle as FO-06 `net_charge`. |
| `total_qualified_income` | decimal | The investor's total qualified dividend income reported, in `currency`. Null where the form type does not distinguish qualified income (e.g. K-1). |
| `total_capital_gain` | decimal | The investor's total capital gain (short- and long-term combined) reported on the statement for the tax year, in `currency`. Null where no redemption or distribution giving rise to capital gain occurred. |
| `cost_basis_reported` | decimal | The aggregate cost basis reported for the investor's redemption proceeds on the statement (1099-B), in `currency`. References the E-32 Tax Lot records for the lots closed during the period. Null for form types that do not carry cost basis (K-1, 1099-DIV, 1042-S). |
| `withholding_reported` | decimal | The total tax withheld and reported on the statement (backup withholding on 1099, foreign withholding on 1042-S), in `currency`. Null where no withholding applies. |
| `currency` | char(3) | The reporting currency of the amounts on this statement, ISO 4217. |

### Effective-dating

| Column | Type | Definition |
|---|---|---|
| `issued_at` | timestamp | The timestamp at which this statement was generated and issued. Append-only: once issued, a statement is not overwritten; corrections are new FO-07 rows. |
| `record_created_at` | timestamp | The timestamp at which this record was created in the system of record. |

## Notes

- **Append-only and correction-chained.** Once issued, a tax statement record is not overwritten. A correction (e.g. a corrected 1099 or K-1) is a new FO-07 row with `filing_status = corrected` and `corrects_statement_id` pointing to the original. The chain of originals and corrections traces the complete filing history. This matches the append-only discipline of the computed-figure-of-record family (E-07, E-19, E-20, FO-06).
- **Figures are derived-at-issue snapshots, stored for the filing audit trail.** The `total_ordinary_income`, `total_qualified_income`, `total_capital_gain`, `cost_basis_reported`, and `withholding_reported` columns carry the amounts *as reported on the filed statement* — the figures that appeared on the document furnished to the investor or filed with the tax authority, derived from FO-05, FO-04, FO-03, and E-32 at statement-generation time. They are not recomputed on read. The non-derivable residue — the `form_type`, `filing_status`, `corrects_statement_id`, `submission_reference`, `tax_classification`, and `filing_date` — is what makes FO-07 a stored entity rather than a design note: those attributes are properties of the *issued document*, not of the underlying events. The reported figures are stored alongside them as the snapshot that was actually furnished; they cannot be reconstructed from the underlying entities alone because the characterisation (ordinary vs qualified, short-term vs long-term) depends on an as-of-issue judgement by the tax function. The SSOT for the underlying events is FO-05, FO-04, FO-03, and E-32; FO-07 stores the rendered snapshot that proves what was filed.
- **One row per (investor, fund, form type, tax year).** The primary grain is the (investor, fund, tax year, form_type) combination. A US-resident investor in a fund that issues both a 1099-DIV and a 1099-B will have two FO-07 rows for the same tax year.
- **Register grain.** FO-07 is at the legal-holder-of-record grain (the omnibus or direct investor), consistent with FO-03 Investor Unitholding. Look-through to underlying investors within an omnibus account is outside this entity's scope; the fund's reporting obligation runs to the legal holder of record.

## Out of scope

- The underlying transaction events (distributions, redemptions, withholding tax captures) — those are FO-05, FO-04, and E-06. FO-07 references these; it does not reproduce them.
- The lot-level cost-basis and holding-period computation — that is E-32 Tax Lot (SD-12.17). FO-07 carries the aggregate reported figure; the lot detail is E-32.
- The submission of the FATCA or CRS report to the tax authority as a regulatory filing — that is SD-16.3 Regulatory Reporting & Filings consuming SD-17.4's output. FO-07 is the statement-of-record; SD-16.3 handles the formal filing workflow.
- The firm's own corporate tax returns — that is SD-17.5 Corporate Tax. FO-07 is investor-facing tax reporting; SD-17.5 is the firm's own tax compliance.
- The K-1 at fund of funds or feeder-fund grain — where a fund of funds issues K-1s to its LPs and also receives K-1s from the underlying funds it invests in. FO-07 is the K-1 the fund *issues* to its LPs; the K-1s the fund *receives* from underlying funds are an input to the computation (they flow into SD-17.4's tax-characterisation work) and are represented as Document Metadata (E-15) or raw inputs to SD-17.4, not as FO-07 rows.

## Owned and consumed by

- **Owned by:** SD-17.4 Investment & Portfolio Tax — the investment-tax function sets the tax-characterisation framework, runs the FATCA/CRS classification, produces the investor-facing tax documents, and owns the filing lifecycle. FO-07 is the record it issues and is sole owner.
- **Consumed by:** SD-16.3 Regulatory Reporting & Filings (the formal submission of FATCA/CRS reports to the relevant tax authority — SD-16.3 consumes FO-07 to feed the regulatory-filing workflow for per-investor tax reports); SD-12.15 Transfer Agency & Investor Dealing (the transfer agent populates the investor's year-end tax reporting pack, using FO-07 as the statement of record to accompany investor account statements); SD-15.14 Client & Investor Reporting (the tax statement is furnished to the investor as part of the annual reporting pack — SD-15.14 includes FO-07 in the investor's annual communication).

## FIBO alignment

**Partial — structural alignment at the investor-document level; the filing-status lifecycle and form-type taxonomy are OpenIM.**

FIBO's published ontologies (as of the current FIBO namespace suite) do not define a `TaxStatement` or `InvestorTaxReport` class. The closest structural alignments are to the FIBO Financial Instruments (`fibo-fbc`) and Foundations (`fibo-fnd`) layers at the conceptual level:

- The investor (E-01) aligns to FIBO's legal-person and account-holder constructs.
- The document lifecycle aligns conceptually to FIBO's `cmns-doc:Document` (OMG Commons v1.2 — the current location of the generic Document class) and `fibo-fnd-arr-lif:LifecycleStage` constructs at the generic level.
- No specific FIBO class maps to the 1099-DIV, K-1, 1042-S, or CRS-report filing constructs; no FIBO curie is asserted for FO-07 — no invented curie is asserted.

What FIBO does not model, and what FO-07 adds:

- The **filing-status lifecycle** (prepared / filed / corrected / superseded) with the correction-chain reference.
- The **form-type taxonomy** mapping to IRS and CRS regulatory regimes.
- The **register-grain issued-document record** — the proof-of-issue that demonstrates the investor-tax-reporting obligation was met.

## Open extensions

- The sub-investor look-through for omnibus registrations — where the legal holder of record is an intermediary, the per-underlying-investor tax records below FO-07.
- The multi-jurisdiction extension — where a single investor has tax obligations in multiple jurisdictions in the same tax year, and the fund must produce multiple form types; the `form_type` enum would be extended.
- The digital-filing receipt sub-model — the FATCA IDES submission acknowledgement, IRS FIRE system confirmation codes — where regulatory e-filing systems return machine-readable receipts.
