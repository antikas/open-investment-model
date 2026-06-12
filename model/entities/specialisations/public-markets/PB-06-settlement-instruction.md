# PB-06 — Settlement Instruction

The instruction to exchange securities for cash and complete a trade — the final stage of the trade lifecycle, sent to a custodian or settlement agent and matched against the counterparty.

**Specialises:** E-05 Transaction (`transaction_type = trade`). Settlement is the last lifecycle stage after Allocation (PB-05): the contractual obligation to deliver or receive. It corresponds to the ISO 20022 securities-settlement (`sese`) family — the settlement-instruction and settlement-status messages — and to the legacy ISO 15022 MT54x messages (MT540–MT543).

## Purpose

A trade is not complete when it is executed and allocated; it is complete when the securities and cash have actually changed hands. PB-06 is the record of that final obligation and its progress. It exists as a distinct entity because settlement is operationally separate from execution — it happens days later (T+1 in most major markets), it runs through a different infrastructure (custodians, central securities depositories, settlement agents), and it **fails** in ways execution does not. A settlement fail — securities or cash not delivered on the contractual date — carries cost, counterparty exposure and, increasingly, regulatory penalty, and the firm needs it as a first-class, monitorable record, not an attribute buried on a trade.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `settlement_instruction_id` | varchar | Primary key. |
| `allocation_id` | varchar (FK → PB-05) | The allocation being settled — settlement is at the per-portfolio grain. |
| `instrument_id` | varchar (FK → E-02) | The instrument being delivered or received. |
| `portfolio_id` | varchar (FK → E-03) | The portfolio whose position settles. |
| `settlement_type` | varchar | `dvp` (delivery versus payment) / `rvp` (receive versus payment) / `free_of_payment` / `fop_delivery`. |
| `direction` | varchar | `deliver` / `receive` — securities out or securities in. |
| `quantity` | decimal | The quantity of securities to settle. |
| `settlement_amount` | decimal | The cash leg — for a bond, the dirty amount including accrued interest. |
| `settlement_currency` | char | The currency of the cash leg. |
| `contractual_settlement_date` | date | The date settlement is contractually due. |
| `actual_settlement_date` | date | The date settlement actually completed; null while pending or failing. |
| `custodian_entity_id` | varchar (FK → E-01) | The custodian or settlement agent actioning the instruction, in the `custodian` role. |
| `counterparty_entity_id` | varchar (FK → E-01) | The settlement counterparty, in the `counterparty` role. |
| `place_of_settlement` | varchar | The CSD or depository where settlement occurs (BIC / identifier). |
| `settlement_status` | varchar | `instructed` / `matched` / `settled` / `failing` / `cancelled`. |
| `fail_reason` | varchar | Where `failing` — `lack_of_securities` / `lack_of_cash` / `unmatched` / `counterparty_fail` / `on_hold`. |
| `ssi_reference` | varchar | The Standing Settlement Instruction profile applied — the pre-agreed account-and-place detail. |

## Notes

- Settlement is at the **allocation grain**, not the execution grain — each portfolio settles its own share, against its own custodian, under its own Standing Settlement Instruction.
- A `failing` instruction is monitored, not corrected by edit — the status moves to `settled` when the fail resolves, or the fail is closed out (a buy-in). The fail lifecycle is operational (SD-12.4) and is itself an auditable chain.
- DvP eliminates principal risk by making the securities and cash legs simultaneous; `free_of_payment` settlement (a transfer with no matching cash leg, e.g. an in-specie move) is the explicit exception and is flagged as such.
- Shortening settlement cycles (T+1) compress the window between execution and settlement, which raises the operational stakes of every prior lifecycle stage — a late allocation now directly causes a fail.

## Out of scope

- The allocation being settled — that is PB-05 Allocation; settlement is at the per-portfolio allocation grain, referenced through `allocation_id`.
- The market fill that preceded settlement — that is PB-04 Execution; settlement is operationally separate, happening days later through custodians and CSDs.
- The cash leg as a recorded movement — that is a core E-06 Cash Flow Event; PB-06 carries the `settlement_amount` obligation, not the cash record.
- The Standing Settlement Instruction modelled as its own reference entity — named as an open extension; the entity holds it as the inline `ssi_reference`.

## Owned and consumed by

- **Owned by:** SD-12.4 Trade Settlement.
- **Consumed by:** SD-12.5 Custody & Safekeeping Oversight, SD-12.10 Reconciliation, SD-11.1 Cash Management (the cash leg), SD-07.2 Credit & Counterparty Risk Management (settlement-counterparty exposure), SD-12.1 Investment Book of Record (IBOR).

## Open extensions

- The settlement-fail lifecycle — fail, penalty accrual, buy-in — as an explicit event sub-model.
- The Standing Settlement Instruction (SSI) modelled as its own reference entity rather than an inline reference.
- Partial settlement, and the relationship between an instruction and its partial settlements.
