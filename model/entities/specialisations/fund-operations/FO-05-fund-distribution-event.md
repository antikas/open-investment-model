# FO-05 — Fund Distribution Event

The fund's formal declaration and payment of income or capital gains to its own unitholders — the open-ended-fund-to-unitholder distribution lifecycle (declaration / ex-date / record date / pay date), with the per-unit income amount and equalisation treatment.

**Specialises:** E-05 Transaction (`transaction_type = distribution`). A fund distribution event is an investment event: it results in income cash flows (E-06) to unitholders and reduces the fund's NAV per unit on the ex-date (the ex-date NAV drop). FO-05 adds the fund-operations structure specific to an open-ended fund paying income to its registered unitholders — the event lifecycle (declaration, ex, record, pay), the per-unit distribution amount, the accumulation / income class treatment, and the equalisation calculation that makes the distribution fair across investors who subscribed at different points in the period.

**Why specialises E-05, not a standalone entity.** A fund distribution is an event — it happens, is recorded, is immutable, and results in a cash flow (E-06) and a NAV-per-unit adjustment (E-07). The E-05 event-specialisation is the correct structural model: PM-08 Distribution (closed-end fund LP distribution) uses exactly this shape, and FO-05 is its open-ended-fund parallel. A standalone entity would duplicate E-05's event semantics. The FO-05-specific structure (the ex-date lifecycle, the per-unit amount, equalisation) are the attributes this specialisation adds.

## Purpose

An open-ended fund that operates an income class declares and pays distributions to its unitholders periodically — typically monthly (money-market funds), quarterly or semi-annually (bond funds), or annually (equity funds). The distribution is the fund's gross income (coupons received, dividends received, net securities-lending income) net of the fund's expenses, divided across unitholders at the record date in proportion to units held.

FO-05 records the lifecycle of that event: the board or trustee declaration of the distribution amount per unit; the ex-date on which the NAV per unit falls by the distribution amount (so that a subscriber on or after the ex-date does not receive income they have not economically contributed to); the record date that fixes which unitholders receive the distribution; and the pay date on which cash moves from the fund to the investors.

FO-05 is distinct from:

- **PB-07 Corporate Action** — the fund's receipt of a dividend or coupon *on an instrument it holds*. PB-07 is an event on an asset the fund owns as an investor; FO-05 is an event the fund *pays to its own investors* as the issuing manager. PB-07 is income *in*; FO-05 is distribution *out*.
- **PM-08 Distribution** — the closed-end fund's capital distribution to LPs, anchored by PM-06 LP Commitment and the capital-call / waterfall structure. PM-08 is a commitment-based capital event (return of capital / income / gain split); FO-05 is a periodic income declaration from an open-ended registered fund to its registered unitholders at the class grain.
- **SD-12.7 Income & Distribution Processing** — SD-12.7 *processes* the receipt and booking of income cash as it arrives at the fund; FO-05 is the declared *distribution event* the fund pays out to its investors. SD-12.7 runs the income accrual engine; FO-05 is the output of that engine crystallised as a distribution declaration.

## Attribute schema

### Identity and relationship

| Column | Type | Definition |
|---|---|---|
| `distribution_event_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for this distribution event. |
| `share_class_id` | varchar (FK → FO-02) | The share or unit class making the distribution. A fund that offers both accumulation and income classes of the same sub-fund will have a FO-05 record only for the income class — accumulation classes reinvest income into NAV rather than paying it out. |

### Event lifecycle

| Column | Type | Definition |
|---|---|---|
| `declaration_date` | date | The date the board, trustee or Authorised Corporate Director (ACD) formally declares the distribution amount per unit. The declaration date is the governance anchor; the other key dates follow from it. |
| `ex_date` | date | The ex-dividend / ex-distribution date: on and after this date, buyers of units do not receive the declared distribution. The fund's NAV per unit falls by the `distribution_per_unit` amount on the ex-date, reflecting the liability the fund has crystallised to its unitholders. |
| `record_date` | date | The date that fixes the register of unitholders entitled to the distribution. Investors holding units as of the record date receive the distribution; investors who redeemed before the record date do not. |
| `pay_date` | date | The date cash is transferred from the fund to the investors. For income classes, this is the date the investors receive the cash in their accounts. For reinvested distributions (accumulation classes), there is no pay date — accumulation classes do not use FO-05; the reinvestment is reflected in NAV movement only. |

### Distribution economics

| Column | Type | Definition |
|---|---|---|
| `distribution_per_unit` | decimal | The gross income distribution amount per unit, in `class_currency`. Declared as of the ex-date; strikes the NAV-per-unit by this amount on the ex-date. |
| `class_currency` | char(3) | The currency of the distribution, derived from `FO-02.class_currency`. |
| `distribution_type` | varchar | The nature of the distribution: `income` (ordinary income — interest, dividends net of fund expenses) / `capital_gain` (realised capital gains distributed to investors, common in US '40-Act funds) / `return_of_capital` (a distribution from the fund's capital rather than income; reduces cost basis). |

### Equalisation

| Column | Type | Definition |
|---|---|---|
| `equalisation_per_unit` | decimal | The income equalisation amount per unit, where the fund operates equalisation accounting. Equalisation is the mechanism that ensures investors who subscribed mid-period receive the correct proportion of the distribution — they pay an equalisation amount on subscription (included in their subscription price) that is returned to them with the first distribution, so that only the income earned during their period of holding is distributed to them. Null where the fund does not operate equalisation. |
| `equalisation_method` | varchar | The equalisation method applied: `pool` (a single pool of equalisation credits for the class) / `individual` (per-investor equalisation calculated from each investor's subscription price and the NAV at subscription). Null where equalisation is not applied. |

### Reference to NAV effect

| Column | Type | Definition |
|---|---|---|
| `ex_date_nav_per_unit` | decimal | The NAV per unit of this class *after* the ex-date drop — the post-distribution NAV per unit struck by SD-12.9 at the ex-date. This is a declared read-cache of the class-grain E-07 Valuation record at `(unit_class_id, valuation_date = ex_date)`, carried on FO-05 for audit convenience. The authoritative figure is the E-07 record owned by SD-12.9. |

## Notes

- **FO-05 is an immutable event.** Once declared and paid, a distribution is a fact. Corrections to the per-unit amount are new records (a reversal FO-05 and a correcting FO-05), not edits.
- **Income class only.** FO-05 applies only to `distribution_policy = income` share classes (from FO-02). An accumulation class (`distribution_policy = accumulation`) does not declare distributions — it reinvests income into NAV, leaving a NAV trail but no distribution event. FO-05 records do not exist for accumulation classes.
- **The ex-date NAV drop is recorded in E-07.** The event that reduces the NAV per unit on the ex-date is reflected in the class-grain E-07 Valuation record owned by SD-12.9 — the post-distribution NAV per unit struck at the ex-date. FO-05 carries `ex_date_nav_per_unit` as a convenience cache; the authoritative provenance-bearing record is E-07.
- **Equalisation protects per-period investors.** Without equalisation, a late-period subscriber (who has held units for only part of the income period) receives the same distribution per unit as an early-period subscriber, subsidised by the early-period investors. Equalisation accounting corrects this: the subscriber's price includes an equalisation credit, which is returned with the first distribution, so only earned income is distributed. Many UCITS and registered funds apply equalisation on income classes.

## Out of scope

- The income *received* by the fund on the instruments it holds — that is PB-07 Corporate Action (dividends and coupons from held instruments), processed and booked by SD-12.7 Income & Distribution Processing. FO-05 is the *outgoing* distribution from the fund to its unitholders.
- The NAV-per-unit figure that reflects the ex-date drop — that is the class-grain E-07 Valuation record owned by SD-12.9; FO-05 carries `ex_date_nav_per_unit` as a read-cache only.
- The closed-end fund distribution to LP investors — that is PM-08 Distribution anchored by PM-06 LP Commitment. PM-08 is a capital event; FO-05 is a periodic income event from an open-ended registered fund.
- The processing of income receipt by the fund prior to distribution declaration — that is SD-12.7 Income & Distribution Processing; FO-05 is the point at which the accrued income is crystallised as a declared, per-unit distribution event.
- Accumulation class reinvestment — accumulation classes do not use FO-05; their income treatment is a NAV movement, not a declared event.

## Owned and consumed by

- **Owned by:** SD-12.7 Income & Distribution Processing — the income-and-distribution processing function declares the distribution, calculates the per-unit amount (gross income net of expenses, divided by units in issue at the record date), and manages the ex-date, record-date and pay-date lifecycle. SD-12.7 produces FO-05 as the crystallised output of the income accrual engine.
- **Consumed by:** SD-12.9 Fund Accounting & NAV (the ex-date NAV drop — the post-distribution NAV per unit is the class-grain E-07 record SD-12.9 strikes at the ex-date, which falls by `distribution_per_unit`; units-in-issue at the record date feed the per-unit calculation); SD-12.15 Transfer Agency & Investor Dealing (the pay-date cash transfer to investors, calculated from FO-05 `distribution_per_unit` × FO-03 `units_held` at the record date, for each investor in the class); SD-12.2 Accounting Book of Record (the distribution payment is a cash event booked in ABOR); SD-09.1 Performance Measurement (the distribution is the income-return leg of total return — it must be accounted for in return calculations alongside NAV movement); SD-17.4 Investment & Portfolio Tax (the `distribution_type` governs the income / capital-gains tax treatment for investors; withholding tax at source may apply for cross-border distributions).

## FIBO alignment

**Partial — structural alignment at the event level; distribution-mechanics layer is OpenIM.**

- FIBO's collective-investment-vehicle framework — a fund distribution event aligns at the conceptual level to FIBO's treatment of income distributions from collective investment vehicles to their unitholders. FIBO does not define a FundDistribution class in its published Funds ontology; the alignment is to FIBO's collective-investment-vehicle concept at the structural level.
- FIBO's date-and-time framework (`fibo-fnd-dt-fd`) — the four key dates (declaration, ex, record, pay) align to FIBO's generic date-taxonomy constructs: `fibo-fnd-dt-fd:CalculatedDate` (dates derived from a formula or rule, such as ex-date derived from record date) and `fibo-fnd-dt-fd:RelativeDate` (dates offset from an anchor, such as pay date offset from record date). FIBO's FinancialDates ontology does not define ExDividendDate, RecordDate or PaymentDate as named classes; the alignment is to FIBO's generic calculated/relative/specified date constructs.

What FIBO does not model, and what FO-05 adds:

- The **equalisation accounting mechanics** — the per-investor equalisation credit that makes per-period distribution economically fair across investors who subscribed at different points in the income period.
- The **ex-date NAV drop linkage** — the explicit connection between the distribution declaration and the class-grain E-07 Valuation adjustment that SD-12.9 strikes.
- The **distribution lifecycle** — the full declaration / ex / record / pay date sequence as a governed event record, with the pay-date cash-transfer trigger consumed by SD-12.15.

## Open extensions

- Monthly distribution accrual sub-record — for funds that accrue daily and pay monthly, a structured accrual ledger linking each day's accrual to the period's FO-05 declaration.
- Enhanced equalisation sub-model — per-investor equalisation at the `individual` method, linking each FO-03 record to its equalisation credit amount.
- The scrip dividend / reinvestment-of-income option — where investors elect to reinvest their income distribution into new units rather than receive cash; the reinvestment is a subscription FO-04 at the ex-date NAV.
