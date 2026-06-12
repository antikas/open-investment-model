# agentINVEST canonical seed data — data dictionary

> **This data is synthetic.** Every figure in these seeds is generated, not
> observed. It is realistic in *shape* and internally consistent — every holding
> has a valuation in every period it is struck; cash positions and accruals are
> dated; valuations, risk measures and returns tie back to real portfolios and
> instruments; the two books of record diverge the way real books do; and the
> external comparator feed agrees with the internal book except on a catalogued set
> of differences — so a NAV, a return, or a reconciliation is computable end-to-end
> from it. But it is **not real and not production-grade**: no figure corresponds to
> any actual fund, security, manager or counterparty, and the data carries none of
> the controls or provenance a production data set would.
>
> In particular the reconciliation data is a **synthetic exercise, not a real
> reconciliation**: the internal dual book (IBOR and ABOR) is internally consistent
> and diverges realistically, but the custodian and administrator records it is
> compared against are *also* synthetic — derived from the internal book with
> differences deliberately injected and labelled, not statements from a real
> custodian or administrator. A green reconciliation over this data proves the
> reconciliation *works against a known answer key*; it is **never** a reconciliation
> against a live custodian and **never** evidence of production readiness. Treat a
> green pipeline over this data as a *foundation*, never as production readiness.

This directory holds the seed CSVs for the agentINVEST canonical data layer — the
core entities of the investment-data master model, populated as a small,
self-contained slice covering the NAV-strike surface **and** the reconciliation
surface (a dual book of record, transactions, cash flows, and an external comparator
feed with labelled differences). The numbers are produced by
`generate_synthetic_seed.py` (deterministic: re-running emits byte-identical files).

## The three funds

The data describes three funds, chosen to span the public/private/multi-asset range:

| Fund | Name | Character | Holdings | Valuation cadence |
|---|---|---|---|---|
| `FUND-PM` | Evergreen Private Markets Fund | Private markets — private equity, private credit, real estate, infrastructure | ~20 (fund interests + real assets) | Quarterly manager marks / appraisals |
| `FUND-EQ` | Meridian Global Equity Fund | Public equities — developed + emerging markets, with cash and short fixed income | ~20 (listed equities, debt, cash) | Monthly observable prices |
| `FUND-MA` | Polaris Multi-Asset Fund | Multi-asset — equities, fixed income, a private-equity sleeve, a real-estate sleeve, hedge funds and cash | ~21 (the union of liquid and illiquid) | Monthly for liquid, quarterly for illiquid |

Each fund is a *total-fund* portfolio with asset-class sub-portfolios beneath it.
Liquid holdings (listed equity, debt, cash) are valued **monthly** — the public
NAV-strike cadence — across a 24-month window (Apr-2024 … Mar-2026). Illiquid
holdings (private fund interests, real assets) are valued **quarterly** — the
private-markets manager-mark cadence. Risk is struck **monthly**; performance is
struck **quarterly** plus a since-inception figure per fund.

## The core entities

| Seed | Entity | What it is | Key | Approx rows |
|---|---|---|---|---|
| `raw_e01_legal_entity.csv` | Legal Entity | The party master — manager, custodian, issuers, fund GPs, counterparties | `entity_id` | ~50 |
| `raw_e02_instrument_asset.csv` | Instrument / Asset | The holdable-thing master — equities, debt, fund interests, real assets, cash | `instrument_id` | ~60 |
| `raw_e03_portfolio_mandate.csv` | Portfolio / Mandate | The capital containers — the three total funds and their asset-class sub-portfolios | `portfolio_id` | ~16 |
| `raw_e04_holding_position.csv` | Holding / Position | What each fund owns, at **two books of record** (IBOR and ABOR), at the latest period-end | `(position_id, book)` | ~120 |
| `raw_e05_transaction.csv` | Transaction | The investment events — settled trades + subscriptions, plus in-flight (unsettled) trades dated with trade and settlement dates and a status | `transaction_id` | ~85 |
| `raw_e06_cash_flow_event.csv` | Cash Flow Event | The dated, signed cash movements — the cash leg of a settled trade, dividends, coupons, fees | `cash_flow_id` | ~100 |
| `raw_e07_valuation.csv` | Valuation | The append-only value trajectory of each holding — one row per mark, with method, level, source and confidence | `valuation_id` | ~1,100 |
| `raw_e09_asset_class.csv` | Asset Class | The nine-class controlled taxonomy (public / private / both) | `asset_class_key` | 9 |
| `raw_e13_entity_alias.csv` | Entity Alias | Alternate names a master record has been seen under | `alias_id` | ~20 |
| `raw_e14_external_identifier.csv` | External Identifier | Cross-references from a golden key to external-system identifiers (LEI, ISIN, internal) | `external_id_record` | ~50 |
| `raw_e19_risk_measurement.csv` | Risk Measurement | The append-only risk-measure trajectory — VaR, exposure, stress loss, liquidity tier — per fund, struck monthly | `measurement_id` | ~250 |
| `raw_e20_performance_result.csv` | Performance Result | The append-only return trajectory — time-weighted quarterly returns, gross and net, plus a since-inception figure per fund | `performance_result_id` | ~50 |

The reconciliation surface adds an **external comparator feed** (a custodian holdings
and cash file, a fund-administrator statement) plus the **labels manifest** that
catalogues the differences between the internal book and that feed — described in
*The external comparator feed and the labels manifest* below.

### Two books of record, and how they diverge (Holding / Position)

A holding is recorded in **two books**: the *IBOR* (the investment book — the firm's
real-time, **trade-date** view, the one the front office trades and manages against)
and the *ABOR* (the accounting book — the **settlement-date**, accrual-basis view used
for NAV, financial reporting and audit). The two share a `position_id` but are distinct
rows (`book = ibor` / `book = abor`); the identity is the composite `(position_id, book)`.

The two books **genuinely differ** — that is the whole point of holding both, and it is
what a reconciliation of IBOR against ABOR exists to find. **ABOR is the accounting
truth** (the NAV-bearing book): its market value is the holding's mark, and a NAV
computed over it ties to the holding valuations. **IBOR diverges from it** on the three
ways the two books really differ:

- **Trade-date vs settlement-date timing.** A trade agreed on or before the as-of date
  but settling *after* it is in IBOR (recognised on trade date) but not yet in ABOR
  (recognised on settlement date). So for a holding with an in-flight buy, the IBOR
  **quantity** and **market value** are higher than the ABOR figures across the trade-
  date-to-settlement-date window. (The matching unsettled trade is in the Transaction
  seed with a `pending` / `confirmed` status and a settlement date after the as-of date.)
- **Accruals.** ABOR carries accrued but unpaid income (coupon, dividend) on the
  accrual basis; the real-time IBOR view does not. So `accrued_income_usd` is present on
  the ABOR row and zero on the IBOR row (visible on the debt holdings).
- **Cost basis / lot treatment.** The two books carry the position's cost on different
  lot conventions — ABOR on an average-cost / amortised accounting basis, IBOR on a
  trade-date lot basis — so `cost_basis_usd` differs between the books.

A reconciliation of IBOR against ABOR over this data therefore finds a **knowable,
non-empty** set of differences (around seventeen logical holdings differ on at least one
of quantity, cost basis, market value or accrued income), characterised by these three
classes — not random noise. A valuation references the **logical holding**
(`position_id`), because a mark applies equally to both books; the book-specific
divergence lives on the holding row, not the mark.

### Transactions and cash flows (E-05 / E-06)

`raw_e05_transaction.csv` carries the **events** that move holdings: settled historic
trades and subscriptions, plus the in-flight (unsettled) trades that drive the trade-
date/settlement-date book divergence. Each transaction has a `trade_date`, a
`settlement_date` (after the trade date for the in-flight ones), a `status`
(`pending` / `confirmed` / `settled` / `cancelled`), a type, and the portfolio and
instrument it touches. `raw_e06_cash_flow_event.csv` carries the **cash consequences**:
the cash leg of a settled trade (tied to its transaction), and income and fee flows
(dividends, coupons, a management fee per fund) — each dated, signed by direction
(`inflow` / `outflow`) and typed. The two are kept separate because not every cash flow
is a discrete transaction and not every transaction is a single cash flow.

## The as-of / append-only entities (the bi-temporal access pattern)

Three entities are **append-only** — Valuation, Risk Measurement and Performance
Result. A figure is never overwritten; a revision is a **new row**. These carry two
independent time axes, and both are queryable:

- **Valid-time (the business as-of date)** — when the figure is *true of the world*:
  `valuation_date` for a valuation, `as_of_date` for a risk measure, `period_end`
  for a return. This is the everyday axis: *what was the value at quarter-end?*
- **Knowledge-time (when we recorded it)** — `recorded_at` in the seed. A restated
  valuation (a late manager NAV), a recalibrated VaR, or a recomputed return is the
  **same business key recorded later** with a different value. This is the audit /
  GIPS axis: *what did we believe the value was, as of a given date?*

A handful of rows in each of the three are deliberate **restatements** — same
business key, a later `recorded_at`, a revised figure — so the two-axis behaviour is
exercisable. The dbt intermediate layer materialises this as a genuine bi-temporal
grain (an append-only log plus derived system-time bounds), exposing three views per
entity:

- the **current** value — the latest-recorded figure per business key (what a NAV
  strike reads);
- the **as-of-knowledge** value — the figure the firm believed on a chosen knowledge
  date (the prior value of a since-revised figure is still retrievable);
- the full **versioned** log — every recorded figure with its knowledge-validity
  window.

So you can ask both *"what is the value of this holding at 2025-12-31?"* (current)
and *"what did we believe that value was, before the revision landed?"*
(as-of-knowledge) — and get different, correct answers.

## The external comparator feed and the labels manifest

Reconciliation compares the firm's own records against the outside world. These seeds
carry a **synthetic external comparator feed** — the records a firm reconciles its book
against — plus a **labels manifest** that catalogues, as ground truth, every difference
deliberately built into the feed.

| Seed | What it is |
|---|---|
| `raw_custodian_holdings.csv` | The custodian's position record per holding — quantity and market value the firm reconciles its internal positions against |
| `raw_custodian_cash.csv` | The custodian's cash balance per fund |
| `raw_admin_statement.csv` | The fund administrator's statement — transaction lines and a cash balance per fund |
| `break_labels.csv` / `break_labels.json` | The **labels manifest** — every deliberately-injected difference, catalogued |

The custodian and administrator records are **derived from the internal book**, so the
**clear majority of rows agree** (most custodian holdings tie exactly to the firm's
positions, and every unbroken cash balance agrees to the cent). A deliberate **minority
carry a difference** — a *break* — and every one of those is catalogued in the labels
manifest. The manifest is the **answer key**: it states exactly which differences exist,
**and each catalogued difference matches the data by value** — a labelled break's amount
or quantity is the actual difference between the feed and the internal book, never a
figure unrelated to it. So the correctness of a reconciliation can be measured against the
manifest both ways: a reconciliation should find **every** catalogued break (with the
right amount), invent **none**, and disagree with the manifest on nothing. There are no
unlabelled differences hiding in the feed, and no labels without a real difference behind
them — on positions, transactions or cash.

Two of the break classes are grounded in the rest of the data rather than being free-
standing figures: a **cash** break is a fund whose administrator balance differs from its
custodian balance by exactly the labelled amount (every other fund's two balances are
equal), and a **timing** break is a holding that genuinely carries an in-flight
(unsettled) trade — the custodian, recording on a settlement-date basis, lags the
internal trade-date book by exactly that trade's quantity.

The manifest uses the standard reconciliation-break vocabulary:

- `reconciliation_type` — what was being reconciled: `position` / `cash` / `transaction`
  (also `ibor_abor` / `custodian` / `counterparty` in the wider vocabulary).
- `cause_classification` — the root cause: `pricing` (the custodian marks a security
  differently) / `data_error` (a different quantity or balance) / `missing_transaction`
  (a trade in one record but not the other) / `timing` (a trade booked trade-date in one
  record, settlement-date in the other — the TD/SD difference) / `fx` (a currency-
  translation difference). The five differences the feed carries — **price · quantity ·
  missing/extra transaction · timing/TD-SD · FX** — map onto these.
- `materiality` — `low` / `medium` / `high`, by the size of the difference.
- `record_ref` and `expected_side` — which record disagreed, and on which side
  (`custodian` or `internal`) the difference sits.

The feed carries on the order of a dozen catalogued breaks — roughly two of each
difference type across the positions, two on the transaction record (one the
administrator is missing, one it has in excess), and one on cash — against a clear
majority of matching rows. The manifest's count equals the number of injected breaks;
the unbroken rows are the larger part of the feed, so a reconciliation has to *find* the
breaks rather than assume every row is one.

`break_labels.csv` and `break_labels.json` are the same manifest in two forms (the JSON
adds a top-level `count` and `description`); use whichever is easier to read.

## What is deliberately not seeded

This is a slice of the core entity set covering the NAV-strike and reconciliation
surfaces — not a full demo of the whole investment-data model. It does **not** include:

- the specialisation-pack entities (the per-asset-class depth — fund cash-flow
  schedules, capital calls, distributions, the four-lens NAV detail);
- benchmark, price/market-data, or scenario master data (referenced by id where
  natural, but not populated as their own seeds);
- any downstream aggregate (a fund-NAV mart, a returns mart, a reconciliation result) —
  those compute over these seeds.

The figures are plausible but uncalibrated: valuation cadences, fee assumptions, return
magnitudes, and the divergence and break sizes are illustrative, not benchmarked against
any real fund, custodian or administrator.

## Regenerating

```sh
python generate_synthetic_seed.py
```

The generator is deterministic (a fixed random seed), so a regenerate produces
byte-identical CSVs — the seeds stay stable and the pipeline stays idempotent. The
CSVs carry an operational `recorded_at` column on the three append-only entities;
the schema-faithful staging views select only the model's own columns, so this
provenance column does not affect schema conformance.
