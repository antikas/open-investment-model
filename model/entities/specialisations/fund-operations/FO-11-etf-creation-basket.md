# FO-11 — ETF Creation Basket (Portfolio Composition File)

The daily-published composition record that specifies exactly what an authorised participant must deliver (or will receive) when creating (or redeeming) one creation unit in an ETF — the set of `(instrument, quantity)` line items plus the cash balancing component that together constitute the in-kind exchange for one creation unit on a given dealing date.

**Specialises:** a first-class entity in the fund-operations pack extending the core entity model. FO-11 is not a holdable instrument or a transaction event; it is the authoritative dated reference record of the basket composition published by the ETF's fund administrator or index provider each business day before the primary market opens. The basket composition has its own dated daily lifecycle (a new FO-11 record per dealing date), a line-item structure (each constituent security with its quantity), and an independent cash balancing component — three characteristics that make FO-11 a first-class entity rather than an attribute set on FO-10.

**Design rationale — entity rather than attribute on FO-10.** Three characteristics require the basket to be a first-class entity: (1) the basket has a line-item structure — it is a set of `(instrument_id FK → E-02, quantity)` pairs, and a set cannot be represented as scalar attributes on a parent; (2) the basket has its own dated daily lifecycle — it is published once per dealing date and is referenced by all FO-10 orders submitted on that date (multiple orders share the same basket); and (3) the cash component and estimated cash are independent attributes of the basket, not of any individual order. This is the same rationale as FO-08 Service-Provider Appointment (a set of appointments cannot be attributes on FO-01) and FO-06 Fee Accrual (a computed figure of record with its own formula provenance).

## Purpose

Every ETF that operates a primary market publishes a Portfolio Composition File (PCF) each dealing day. The PCF specifies the exact basket of securities — identities and quantities — that constitutes one creation unit. An AP submitting a creation order must deliver this exact basket (or an accepted cash-in-lieu substitute); an AP redeeming receives this basket back. The PCF is the operational specification the AP uses to hedge the position before submission and to arrange the custody delivery.

FO-11 is the OpenIM entity for the PCF: the dated, per-dealing-day basket composition record that FO-10 creation/redemption orders reference. Multiple FO-10 orders on the same dealing date share the same FO-11 basket (the composition does not change within the dealing day, only between dealing days).

FO-11 is distinct from:

- **FO-10 ETF Creation/Redemption Order** — the individual transaction submitted by an AP, which references this basket.
- **E-04 Holding / Position** — the ETF fund's current securities positions. The basket composition is derived from (but not identical to) the fund's positions; it reflects the target portfolio the fund aims to hold, adjusted for liquidity, corporate-action timing, and the fund's policy on in-specie eligible securities.
- **E-02 Instrument / Asset** — the individual securities named in the basket; FO-11 holds the basket-level composition that references those instruments via FK.

## Attribute schema

### Identity and lifecycle

| Column | Type | Definition |
|---|---|---|
| `basket_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for this basket composition record. |
| `fund_product_id` | varchar (FK → FO-01) | The ETF fund this basket composition applies to. |
| `share_class_id` | varchar (FK → FO-02) | The share or unit class this basket composition applies to (where a fund has multiple classes with different creation-unit sizes, one FO-11 per class per dealing date). |
| `dealing_date` | date | The dealing date this basket is valid for. The PCF is published once per dealing date; this is the date AP orders referencing this basket must be submitted on. |
| `published_at` | timestamp | The date and time the PCF was published (typically before the exchange opens on `dealing_date`). |
| `basket_type` | varchar | `published` \| `custom`. A `published` basket is the standard daily PCF issued by the fund administrator for all APs on the dealing date. A `custom` basket is negotiated per-AP or per-order, differing from the published composition by mutual agreement between the fund and the specific AP — permitted under SEC Rule 6c-11 (17 CFR 270.6c-11, 2019), which allows ETFs to use custom baskets that diverge from the published PCF provided the fund's custom-basket policy is disclosed. A FO-10 order with `settlement_basis = custom` references a custom FO-11 basket (basket_type = custom). |
| `ap_entity_id` | varchar (FK → E-01, nullable) | For custom baskets: the authorised participant for whom this basket was negotiated. Null for published (standard) baskets. |

### Basket composition — line items

The basket composition is a set of line items. Each line names a security and the quantity per creation unit. The line-item structure is the core of FO-11; the following attributes describe each line in the set.

| Column | Type | Definition |
|---|---|---|
| `instrument_id` | varchar (FK → E-02) | The instrument (equity, bond, or other eligible security) in this basket line. Each basket line references one E-02 record via its golden key. |
| `quantity_per_creation_unit` | decimal | The number of shares, par value, or units of the instrument per creation unit on this dealing date. The quantity is specified to the precision the fund's dealing convention requires (typically whole shares for equities; decimal for bonds in par-value terms). |
| `market` | varchar | The primary market or exchange on which the instrument settles (ISO 10383 MIC code where applicable). Used by the AP to route the basket delivery to the correct settlement system. |

### Cash component

| Column | Type | Definition |
|---|---|---|
| `cash_component` | decimal | The net cash amount payable by the AP to the fund (creation) or by the fund to the AP (redemption) per creation unit, arising from accrued income, timing differences between the basket securities' values and the creation-unit NAV, and any accumulated income in the fund not yet distributed. Signed by direction: positive = AP pays the fund; negative = fund pays the AP. |
| `cash_component_currency` | char(3) | The currency of `cash_component`. Typically the fund's base currency. |
| `estimated_cash` | decimal | An intraday estimate of the cash component, published at basket-release time and used by APs for pre-trade cash management. The `cash_component` is the official settled figure; `estimated_cash` is an indicative proxy available earlier in the dealing day. |

### Metadata

| Column | Type | Definition |
|---|---|---|
| `total_basket_value` | decimal | The total value of the basket (securities + cash component) at the time of publication, in the fund's base currency. Published as a reference figure for APs; the authoritative per-unit NAV is the class-grain E-07 record owned by SD-12.9. |
| `creation_unit_size` | integer | The number of ETF shares per creation unit on this dealing date, as published alongside the basket. This is a read-cache from FO-02 / FO-01 and is included here for dealing-day completeness on the PCF record. |

## Notes

- **One FO-11 per (share class, dealing date).** The basket composition is fixed for the dealing day. All FO-10 orders submitted on `dealing_date` reference the same FO-11 record; the basket does not change between AP orders within the dealing day.
- **The basket is derived, not authoritative.** FO-11 is the published PCF composition. The ETF's actual holdings are carried in E-04 Holding / Position at the IBOR/ABOR grain. The basket is derived from those holdings each day by the fund administrator (SD-12.9), incorporating accrued income, index rebalancing targets, and in-specie eligibility rules. FO-11 records the published basket; it does not replace the position record.
- **Line items are a set, not a count.** The number of securities in the basket varies by ETF. A broad-market equity ETF may carry hundreds of lines; a sector ETF may carry fewer. FO-11's line-item structure is relational: one row per (basket_id, instrument_id, dealing_date) in the normalised form.
- **Cash component vs residual cash on FO-10.** The `cash_component` on FO-11 is the published daily cash balancing amount per creation unit. The `cash_residual` on FO-10 is the actual net cash settled for a specific order (which may differ from the published cash component where cash-in-lieu substitutions apply). FO-11 carries the published reference; FO-10 carries the settled actuals.

## Out of scope

- The ETF's live portfolio holdings — those are E-04 Holding / Position at the IBOR/ABOR grain. FO-11 is the derived, published basket composition, not the live fund position.
- The intraday iNAV series — the continuously published indicative NAV; that is a real-time reference price, not a composition record.
- The creation/redemption order itself — that is FO-10, which references this basket.
- The index composition of the index the ETF tracks — that is a reference-data record at the E-10 Benchmark / Index grain. The ETF basket is related to but not identical to the index composition (it may omit illiquid constituents, round quantities to lot sizes, and include a cash component for timing differences).

## Owned and consumed by

- **Owned by:** SD-12.9 Fund Accounting & NAV — the fund-administration function strikes the NAV and publishes the Portfolio Composition File each dealing day as part of its fund-administration output. SD-12.9 is the system of record for the daily basket composition and the cash component figure that accompanies it.
- **Consumed by:** SD-12.15 Transfer Agency & Investor Dealing (reads FO-11 when validating and accepting FO-10 creation/redemption orders — the basket referenced on each FO-10 must match the published FO-11 for that dealing date; SD-12.15 confirms the AP's submitted composition against the authoritative FO-11); SD-12.5 Custody & Safekeeping Oversight (reads FO-11 to verify that the basket securities delivered or received by the AP in settlement match the authoritative daily composition; the safekeeping function confirms in-kind deliveries against the published PCF); SD-12.1 Investment Book of Record (IBOR) (the basket defines the securities entering or leaving the fund's portfolio; IBOR uses FO-11 to identify the instruments and quantities to book as in-kind receipts or deliveries at the point the creation/redemption settles).

## FIBO alignment

**No published FIBO class for the ETF Portfolio Composition File (PCF) or Creation Basket.** FIBO models instruments (including fund shares as instruments) and portfolios at the conceptual level; it does not define classes for the daily PCF, the in-specie basket composition, or the creation-unit structure of an ETF primary market.

- Individual basket constituents are instruments: `fibo-sec-eq-eq:CommonShare`, `fibo-sec-dbt-bnd:Bond` or the applicable FIBO instrument class applies to each E-02 record the `instrument_id` FK resolves to.
- The basket-composition record itself, its daily lifecycle, and the cash component are OpenIM additions with no FIBO equivalent in the published ontology.

## Open extensions

- A basket-amendment record — where the published PCF is corrected or supplemented after initial publication (e.g., a corporate action announced after the basket was released), a versioned amendment record linking back to the original FO-11.
- An in-specie eligibility flag per line item — recording which basket constituents are eligible for in-kind delivery vs cash-in-lieu substitution per the fund's in-specie eligibility policy.
- The full PCF distribution record — where the basket was disseminated (exchange data vendors, AP portals), for regulatory and audit purposes.
