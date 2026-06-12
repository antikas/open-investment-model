# E-25 — Account

The account structure portfolios are held and settled through — custody and safekeeping accounts on one side, bank and cash accounts on the other. One shared account master, key-partitioned by `account_type`, aligned to the FIBO Account concept.

## Purpose

A portfolio's holdings sit in **safekeeping accounts** at custodians and depositories; its cash sits in **bank accounts** with signatory mandates. Both are account structures portfolios map to, both are opened, controlled and closed, and both had been process artefacts rather than modelled entities — two Service Domains independently surfaced the same gap and asked for one shared account entity. The Account is that entity: a single account master, with a type discriminator distinguishing the safekeeping side from the bank-account side, that portfolios link to and that transactions settle through.

Modelling it as one entity with a key partition — rather than two near-identical account entities — follows the model's established pattern (E-04 Holding / Position partitioned by `book`): the schema is shared, the instance set is partitioned by `account_type`, and the two sides have co-equal, separate owners. The entity aligns to the FIBO `fibo-fbc-pas-caa:Account` concept rather than re-defining what an account is.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `account_id` | varchar | Primary key. |
| `account_type` | varchar | The partition key — `safekeeping` (a custody / safekeeping account) / `cash` (a bank / cash account). Part of the account's identity. |
| `account_number` | varchar | The account number or reference at the holder. |
| `holder_entity_id` | varchar (FK → E-01) | The custodian, sub-custodian or depositary (safekeeping side) or the bank (cash side) — a Legal Entity in the relevant role. |
| `portfolio_links` | array (FK → E-03) | The portfolios or mandates the account is held for; an account may serve one or several. |
| `currency` | char | The account currency, for a cash account; the reporting currency for a safekeeping account. |
| `account_status` | varchar | `opening` / `active` / `dormant` / `closing` / `closed`. |
| `segregation` | varchar | The segregation designation on the safekeeping side — `segregated` / `omnibus`; null on the cash side. |
| `signatory_mandate` | document (JSON) | The authorised signatories and authority limits on the cash side; null on the safekeeping side. |
| `settlement_instruction_ref` | varchar | The standing settlement instruction (SSI) detail associated with the account, where one applies. |
| `opened_date` | date | When the account was opened. |
| `closed_date` | date | When the account was closed; null while active. |

## Notes

- **Key-partitioned by `account_type`.** A safekeeping account and a cash account are the same kind of thing — an account portfolios map to — distinguished by their type. The `account_type` partition determines which side's owner is the authoritative source, the same pattern E-04 uses on `book`.
- The type discriminator carries the side-specific structure: `segregation` is meaningful only on the safekeeping side, `signatory_mandate` only on the cash side. The schema holds both; an instance populates the fields its type uses.
- The account is the structure portfolios are held and settled *through*; it is distinct from the portfolio itself (E-03, the capital container) and from the holder (E-01, the custodian or bank in role). Aligning to FIBO's Account concept keeps OpenIM from re-defining a concept FIBO already models.

## Out of scope

- The portfolio or mandate whose capital the account holds — that is E-03 Portfolio / Mandate; the Account is the custody or bank structure E-03 maps to, not the capital container itself.
- The custodian, depositary or bank that holds the account — that is E-01 Legal Entity in the custodian / bank role, referenced through `holder_entity_id`.
- The positions and cash balances held in the account — those are E-04 Holding / Position and E-06 Cash Flow Event; the Account is the container they sit in, not the holdings themselves.

## Owned and consumed by

- **Owned by:** key-partitioned by `account_type`, co-equal. **SD-12.5 Custody & Safekeeping Oversight** is the authoritative source for `account_type = safekeeping`; **SD-11.7 Bank Account & Mandate Administration** for `account_type = cash`. Neither holds schema authority over the other; the schema is the model's, defined here. The full pattern is documented in [`ownership-map.md`](../../ownership-map.md).
- **Consumed by:** SD-12.4 Trade Settlement (settlement through the account), SD-11.2 Liquidity Management (cash accounts), SD-12.1 Investment Book of Record (IBOR), SD-12.10 Reconciliation (account-level reconciliation against the holder), SD-16.2 Owner & Investor Reporting.

## Open extensions

- The account-hierarchy sub-model — sub-accounts, omnibus structures and the mapping of a single portfolio across multiple accounts.
- The signatory-mandate model as its own structure — the authority matrix and its approval workflow.
- The standing-settlement-instruction (SSI) model in full, beyond the reference held here.
