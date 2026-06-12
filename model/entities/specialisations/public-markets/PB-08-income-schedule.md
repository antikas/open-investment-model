# PB-08 — Income Schedule

The forward calendar of contractual or expected income payments on an instrument — the coupon stream of a bond, the dividend stream of an equity — held as dated reference data.

**Specialises:** E-02 Instrument / Asset. The income schedule is an attribute of the instrument, not an event in its own right; PB-08 is the structure that carries the *forward-known* payment calendar that PB-01 and PB-02 reference. Where PB-07 Corporate Action records an income event when it *occurs*, PB-08 is the *projection* of those events before they occur.

## Purpose

A bond's coupons are contractual and known at issue; an equity's dividends are expected and forecastable from declared and historical policy. Several capabilities need that forward stream as **data, not as a sequence of past events**: income accrual (a bond accrues interest daily against the next coupon), cash-flow forecasting (SD-09.7 needs the projected receipts), fixed-income performance attribution (the income return is a distinct component), and liquidity planning. PB-08 materialises the schedule as one row per expected payment, so those computations join to dated rows rather than re-deriving the calendar each time. It is the bridge between an instrument's static terms (PB-02's `coupon_rate`, `coupon_frequency`) and the actual income events PB-07 records.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `income_schedule_id` | varchar | Primary key — one row per scheduled payment. |
| `instrument_id` | varchar (FK → E-02) | The instrument the payment is on — a PB-01 listed equity or PB-02 debt instrument. |
| `income_type` | varchar | `coupon` / `dividend` / `amortisation` / `principal_redemption`. |
| `period_start_date` | date | The start of the accrual period this payment covers. |
| `period_end_date` | date | The end of the accrual period. |
| `scheduled_payment_date` | date | The date the payment is scheduled to be made. |
| `rate` | float | The coupon rate or declared dividend rate for the period. |
| `amount_per_unit` | decimal | The expected payment per unit / per share held. |
| `currency` | char | The payment currency. |
| `is_projected` | boolean | `false` for a contractual coupon known at issue; `true` for a forecast equity dividend or a floating-rate coupon not yet reset. |
| `reset_rate_observed` | float | For a floating-rate coupon — the reference rate once observed at the reset date; null until then. |
| `schedule_status` | varchar | `scheduled` / `confirmed` / `paid` / `cancelled` / `superseded`. |

## Notes

- For a **fixed-rate bond** the whole schedule is `is_projected = false` and known from `issue_date` to `maturity_date` — a deterministic materialisation of PB-02's coupon terms.
- For a **floating-rate bond** the schedule dates are known but each `amount_per_unit` is projected until the reference rate is observed at the reset date; `reset_rate_observed` is populated then, and the row moves toward `confirmed`.
- For an **equity** every row is `is_projected = true` — a forecast from declared and historical dividend policy — until the dividend is declared, at which point it firms up. The declared dividend then becomes a PB-07 Corporate Action of `event_type = cash_dividend`.
- A schedule row is **superseded, not deleted**, when terms change (a coupon step-up triggers, a dividend is cut) — consistent with the model's append-only, archive-not-delete stance and its bi-temporal design.
- The actual receipt of a scheduled payment is processed as a PB-07 event and a Cash Flow Event (E-06); PB-08 is the expectation, PB-07 the realisation.

## Out of scope

- The actual receipt of a scheduled payment — that is a PB-07 Corporate Action and a core E-06 Cash Flow Event; PB-08 is the expectation, PB-07 the realisation.
- The static instrument terms the schedule is derived from — those are PB-02's `coupon_rate` / `coupon_frequency` and PB-01's dividend attributes; PB-08 materialises them as dated rows, it does not own them.
- The generic instrument record PB-08 specialises — that is E-02 Instrument / Asset; the income schedule is an attribute of the instrument, not an event in its own right.
- Dividend-forecast confidence and source tracking — named as an open extension; the entity carries only the `is_projected` flag.

## Owned and consumed by

- **Owned by:** SD-13.1 Instrument & Security Master.
- **Populated via:** SD-13.4 Market & Reference Data Management.
- **Consumed by:** SD-09.7 Private-Markets Cash-Flow Forecasting (the public-markets income schedule contributes to forecasts for funds holding public-debt and dividend-yielding portfolios), SD-09.2 Performance Attribution (income return), SD-12.7 Income & Distribution Processing, SD-08.1 Security Pricing (accrued-interest calculation), SD-11.2 Liquidity Management.

## Open extensions

- The relationship between a projected equity dividend row and the declared PB-07 Corporate Action that confirms it.
- The floating-rate reset sub-model — the reference-rate observation that fixes a projected coupon.
- Dividend-forecast confidence / source tracking, distinguishing declared, consensus and model-forecast rows.
