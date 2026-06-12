# E-32 — Tax Lot

The per-(client, instrument, acquisition-tranche) tax-lot record — the lot-level grain underneath a holding, carrying its cost basis, acquisition date, lot-relief eligibility and wash-sale-adjustment history. Append-only on the lot grain; supersession by lot-close.

## Purpose

A position in a single instrument may sit across many tax lots — each lot the residue of one acquisition tranche, each with its own cost basis, its own acquisition date, and its own short-term / long-term qualification. The tax outcome of a sale depends on *which* lot the sale draws against: the same dollar sale realises a different gain (or loss, or wash-sale-disallowed loss) depending on the lot-relief method in force and the lot-selection logic. The position carries the headline quantity and value; the lots underneath carry the tax record.

The Tax Lot is the record of one such lot — a row per (client, instrument, acquisition-tranche), with the cost basis (including reinvested dividends and corporate-action adjustments), the acquisition date, the lot-relief method that governs how the lot is drawn against, the wash-sale adjustment if any, the holding-period class, and the lot-close record once realised. It is the lot-level grain underneath the ABOR holding (E-04 with `book = abor`), and the entity SD-17.4's strategic-tax discipline, SD-15.14's per-client tax reporting and SD-15.15's after-tax wealth advice all run on.

It is **append-only on the lot grain.** A lot opens on acquisition and persists; the lot record is not overwritten as the lot is partially closed — a partial close updates the status and writes the disposal date / realised gain on the closing tranche, leaving the lot's identity and acquisition history intact. A lot fully closed by a sale moves to `closed`; a lot adjusted by a wash sale carries the basis adjustment on the *replacement* lot. The lot history of a position is the set of lots that ever existed against it.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `tax_lot_id` | varchar | Primary key. |
| `client_entity_id` | varchar (FK → E-01) | The client / household the lot is held for, in the client role of Legal Entity. |
| `instrument_id` | varchar (FK → E-02) | The instrument the lot is in. |
| `acquisition_transaction_id` | varchar (FK → E-05) | The transaction that opened the lot — the buy, the reinvested-dividend transaction, the corporate-action-adjusted basis event. |
| `acquisition_date` | date | The date the lot was acquired. |
| `quantity` | decimal | The lot's quantity at open; reduced as the lot is partially closed. |
| `cost_basis_amount` | decimal | The lot's cost basis — purchase price net of fees, plus reinvested-dividend and corporate-action adjustments. |
| `cost_basis_currency` | char | The currency the cost basis is denominated in. |
| `lot_relief_method` | varchar | The lot-selection convention governing how the lot is drawn against — `specific_id` / `fifo` / `lifo` / `hifo` / `min_tax`. |
| `wash_sale_adjustment_amount` | decimal | The wash-sale-disallowed-loss adjustment carried into the lot's basis where the lot is a replacement lot under the wash-sale rule; null otherwise. |
| `holding_period_class` | varchar | The holding-period qualification — `short_term` / `long_term` — determined by the acquisition date and the jurisdiction's short-term threshold. |
| `disposal_date` | date | The date the lot was closed; null while the lot is open. |
| `realised_gain_loss_amount` | decimal | The realised gain or loss on close; null while the lot is open. |
| `status` | varchar | `open` / `closed` / `partially_closed`. |

## Notes

- **Append-only on the lot grain.** A lot opens once and persists. The lot record is the open-to-close history of one acquisition tranche; partial closes update the open quantity and write disposal records on the closing tranches, but do not overwrite the lot's identity. A correction to a posted lot is a new record, not an overwrite — the same discipline E-07 Valuation, E-19 Risk Measurement and E-20 Performance Result follow at the holding / measurement grain.
- **`lot_relief_method` is part of the lot's identity.** The method selected at acquisition (or at close, under specific-ID) governs the order in which the lot is drawn against in a sale. A change of method does not retroactively re-tag the lot; the field records the method in force when the lot was opened.
- **`wash_sale_adjustment_amount` is the load-bearing tax record.** When a sale at a loss is followed within the wash-sale window (30 days before / 30 days after, under IRC §1091 in the US — equivalent regimes elsewhere) by an acquisition of a substantially-identical security, the loss is disallowed and the disallowed amount is added to the basis of the replacement lot. The replacement lot carries the adjustment on this field; the disallowed-loss carry across lots is the lot-by-lot tax record an audit reads.
- **The lot grain sits underneath the ABOR holding.** E-04 with `book = abor` carries the aggregated holding; the Tax Lot record is the lot-level decomposition of it. A holding's open lots sum to its open quantity; the cost basis on the holding rolls up from the lot basis.

## Out of scope

- The aggregated holding the lots roll up to — that is E-04 Holding / Position (`book = abor`); E-32 is the lot-level grain underneath, not the holding.
- The transaction that opens or closes the lot — that is E-05 Transaction (the buy, the sell, the corporate-action event); E-32 references the originating transaction through `acquisition_transaction_id`, it is not the transaction.
- The strategic tax position the lots feed — that is SD-17.4 Investment & Portfolio Tax's withholding-reclaim, treaty and characterisation discipline; E-32 is the operational lot record SD-17.4 runs over, not the strategic-tax artefact.
- The tax-loss harvesting decision — that is the SD-05.2 / SD-15.15 operation that consumes the lot record to surface harvestable losses; E-32 is the lot record the decision runs over.
- The per-client tax-reporting form — that is the regulated form SD-12.17 produces (the US 1099-B, the UK SA108, the per-jurisdiction equivalents); E-32 is the lot record the form is built from.

## Owned and consumed by

- **Owned by:** SD-12.17 Tax-Lot Accounting — the back-office operational tax-bookkeeping engine that opens lots on every buy, closes them on every sell under the selected lot-relief method, and applies the wash-sale adjustment.
- **Consumed by:** SD-17.4 Investment & Portfolio Tax (the strategic tax position the lot record feeds — treaty positions, withholding-reclaim eligibility, tax characterisation), SD-15.14 Client & Investor Reporting (the per-client tax-reporting form and the cost-basis statement), SD-15.15 Financial & Wealth Planning (the after-tax wealth advice and the tax-loss-harvesting candidate surface).

## Open extensions

- The substantially-identical-security sub-model — the precise definition of the wash-sale-triggering replacement under IRC §1091 and the equivalents (HMRC bed-and-breakfasting, the EU national variants).
- The cross-account wash-sale propagation — how a wash-sale event in one client account interacts with an adjacent account in the same household.
- The relationship between the lot grain and the corporate-action basis adjustments (PB-07) that mutate it.
- The per-jurisdiction lot-record variation — the data fields a non-US jurisdiction's tax form requires that the US 1099-B set does not.
