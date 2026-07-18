# FO-09 — Omnibus Account

The account record an intermediary — a distributor, platform, nominee, or sub-transfer agent — holds at the fund's register. The fund sees a single registered position per share class per intermediary; the intermediary keeps the per-investor accounts behind its own register. FO-09 is the fund-side account master for that relationship: the account identification, the underlying unit-class link, and the servicing fee terms (12b-1 distribution fee, sub-TA fee, revenue-share, platform fee) the manager pays the intermediary for investor servicing within the omnibus.

**Specialises:** E-25 Account. An omnibus account is an account — a register/nominee account relationship, key-partitioned in E-25 by `account_type = register` — at the fund-register grain, not the institutional safekeeping or cash grain. FO-09 specialises E-25 because the defining question it answers is "what registered account does this intermediary hold at the fund, and on what fee terms?" not "how many units does the intermediary hold?" The units-held dimension is already FO-03 Investor Unitholding, where the intermediary is the legal holder of record. FO-09 is the account master the fund uses to govern the distribution relationship: the account identification, the fee-flow terms and the look-through boundary. The register partition is owned by SD-15.4 Distribution Strategy & Channel Management — distinct from the `safekeeping` partition (SD-12.5 Custody & Safekeeping Oversight) and the `cash` partition (SD-11.7 Bank Account & Mandate Administration).

**Why E-25 Account rather than E-04 Holding / Position or the FO register grain (FO-03).**

The parent choice matters. Three candidates:

- **E-04 Holding / Position** would make FO-09 a position record — but the omnibus *position* is already FO-03 (the per-investor, per-class register position where the investor is the intermediary). FO-09 is not a second position at the same grain. Placing it under E-04 would conflate the account master with the position it carries. The two are distinct: the FO-03 row for the intermediary is the *state* of the position; FO-09 is the *account structure* that governs the relationship and its fee terms.

- **FO-03 Investor Unitholding** as the direct parent (a "register sub-record") is tempting — each omnibus account corresponds to a set of FO-03 rows. But FO-03 is the per-investor, per-class register row; it is a position, not an account. The fee-flow terms belong to the account relationship, not to any individual position row. Making FO-09 a child of FO-03 would put the fee terms on the wrong grain (they attach to the intermediary relationship, not to a single FO-03 row) and would create a cross-class problem (the same omnibus account may span several share classes, each with its own FO-03 row).

- **E-25 Account** is the right parent. An E-25 account is an account portfolios are held and settled through, key-partitioned by `account_type`. The omnibus account is precisely that at the fund-register layer: an account the fund maintains for the intermediary (not for the institution's own safekeeping). FO-09 adds the fund-operations structure — the link to the fund product (FO-01), the share class (FO-02), the intermediary (E-01), and the servicing-fee terms that make the manager's distribution economics reconstructable. The FO-06 precedent (fee accrual specialises E-07 Valuation because the fee is a computed, provenance-bearing value) is the shape: FO-09 specialises E-25 because an omnibus account is a governed, account-relationship record.

## Purpose

A retail or intermediated fund manager distributes its funds through platforms, distributors, nominees and sub-transfer agents. These intermediaries hold units in *omnibus*: the intermediary is the legal holder of record at the fund's register; the underlying investors — the beneficial holders — are behind the intermediary's own system.

The fund sees exactly one registered position per share class per intermediary. The manager cannot see the underlying investors: it does not know who they are, how many units each holds, or when they transact within the omnibus. This is the **omnibus look-through gap** — the figure-of-record boundary that is hardest to bridge.

The omnibus structure has two consequences the model must capture:

1. **The fund's register boundary.** The fund's FO-03 Investor Unitholding register records the intermediary as the legal unitholder. Look-through to the underlying per-investor accounts sits at the intermediary's layer, not the fund's register. FO-09 states this boundary explicitly: the fund's view of the relationship is the omnibus account; the per-investor accounts within it are the intermediary's own record.

2. **The servicing fee flow.** Because the intermediary maintains the per-investor accounts and distributes the fund to its clients, the manager compensates the intermediary for those services. These payments — known variously as 12b-1 distribution fees (US), sub-TA fees (sub-transfer-agency fees), revenue-share payments, trail commissions, or platform fees — are a material part of a retail manager's economics. The terms of these payments attach to the omnibus account relationship: a given rate, basis and definition for each fund/class/intermediary combination. FO-09 carries these terms.

FO-06 Fee Accrual (owned by SD-12.11) computes the servicing-fee amount; FO-09 carries the fee terms those computations reference — the same pattern as FO-02 `class_fee_schedule` carrying the management-fee terms that FO-06 computes from. FO-09 does not duplicate the fee machinery; it is the fee-terms anchor the computation reads.

## The omnibus look-through gap — the figure-of-record boundary

The fund's register terminates at the omnibus account. From the fund's perspective:

- **What the fund knows:** the intermediary's total units held per share class, updated at each dealing cycle via FO-03. The intermediary is the legal holder; the fund's transfer agent maintains one FO-03 row per (intermediary, share class).
- **What the fund does not know:** the underlying investor identities, their individual holdings, or their individual dealing activity. This information lives in the intermediary's own recordkeeping system, inaccessible from the fund's register.
- **The boundary to FO-03 (the manager's direct register):** FO-03 serves both direct investors (each one is a named legal entity in the register) and omnibus accounts (the intermediary as the legal holder of record). The distinction is carried on FO-09: if an FO-03 row links to an FO-09 omnibus account, the investment is intermediated and the look-through is unavailable at the fund level. A direct investor has no FO-09 counterpart.

This boundary is not a model gap — it is a structural feature of fund distribution through intermediaries. OpenIM models the boundary as the data it is: the fund's register ends at the omnibus account, and the manager's economics on the underlying investor base are captured in FO-09's servicing-fee terms. A future look-through extension — where the intermediary provides position-level data to the manager — would introduce a new entity at that grain; FO-09 acknowledges the boundary and the gap explicitly.

## Attribute schema

### Identity and relationship

| Column | Type | Definition |
|---|---|---|
| `omnibus_account_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for this omnibus account relationship. |
| `fund_product_id` | varchar (FK → FO-01) | The fund to which this omnibus account belongs. Required — every omnibus account attaches to a specific issued fund. |
| `share_class_id` | varchar (FK → FO-02) | The share or unit class the omnibus account is registered in. Where the intermediary holds units across multiple classes of the same fund, one FO-09 row exists per share class. Null only where the account is fund-level and class assignment is deferred. |
| `intermediary_entity_id` | varchar (FK → E-01) | The Legal Entity that is the legal holder of record — the intermediary, platform, distributor, nominee or sub-transfer agent. |
| `register_account_ref` | varchar | The account reference or holder code at the fund's transfer agent — the operational identifier used in dealing and distribution confirmations. This is an operational read-cache; the canonical intermediary identity is `intermediary_entity_id` (FK → E-01). |

### Account lifecycle

| Column | Type | Definition |
|---|---|---|
| `account_status` | varchar | Lifecycle state: `active` / `suspended` / `closed`. |
| `opened_date` | date | The date the omnibus account was established at the fund's register. |
| `closed_date` | date | The date the omnibus account was closed; null while active. |

### Servicing fee terms

The manager pays the intermediary for maintaining the per-investor accounts and distributing the fund to end investors. These terms are the *definition* of the fee obligation — the rate and basis the fee computation reads. The computed fee amount for each period is FO-06 Fee Accrual, owned by SD-12.11; FO-09 carries the terms FO-06 refers to.

| Column | Type | Definition |
|---|---|---|
| `servicing_fee_type` | varchar | The type of servicing fee: `12b-1` (US SEC Rule 12b-1 distribution and service fee paid from fund assets) / `sub_ta` (sub-transfer-agency fee, paid for recordkeeping and investor services below the omnibus level) / `revenue_share` (a revenue-sharing payment from the manager to the intermediary, paid from manager revenues outside the fund) / `platform_fee` (a fee paid to a fund platform or supermarket for shelf access and servicing) / `trail` (ongoing trail commission paid on units distributed by the intermediary — typical in markets with retrocession arrangements). A given omnibus account may carry more than one fee type; one FO-09 row per (omnibus_account_id, `servicing_fee_type`), or the `servicing_fee_type` field is multi-valued. |
| `servicing_fee_rate` | decimal | The contractual fee rate — an annual percentage applied to the AUM of the intermediary's omnibus position in the relevant share class. |
| `fee_basis` | varchar | The basis on which the fee rate is applied: `aum` (applied to the value of units held in the omnibus account at each calculation date), `net_new_sales` (applied to net sales into the fund over the period), `flat_per_account` (a fixed fee per underlying account estimated by the intermediary). The most common basis is `aum`. |
| `fee_effective_from` | date | The date from which this fee rate is in force. |
| `fee_effective_to` | date | The date this fee rate is superseded by a revised schedule; null while current. |
| `definition_type` | varchar | `FIXED` (the fee is a scalar rate) / `COMPUTED` (the fee is computed from a structured formula specification). Mirrors the vocabulary on PM-10 Fund Terms and FO-02 `class_fee_schedule`. |
| `formula_spec_ref` | varchar | A reference to the distribution-services agreement or fee-schedule document that defines the servicing fee terms. The provenance pointer; this is not the computed amount — the amount is FO-06. |

### Look-through

| Column | Type | Definition |
|---|---|---|
| `look_through_available` | boolean | Whether the intermediary provides position-level look-through data to the manager (true = the intermediary supplies per-investor holdings data; false = the omnibus account is opaque to the fund). Default false. |
| `look_through_arrangement_ref` | varchar | Where `look_through_available = true`, a reference to the data-sharing arrangement or technology interface under which the intermediary provides look-through data. Null where no look-through exists. |

## Notes

- **One FO-09 row per (fund, share class, intermediary, fee type).** The omnibus account relationship has multiple servicing fee types in practice — a US intermediary may receive both a 12b-1 fee from the fund and a sub-TA payment from the manager; both are separate terms on the same omnibus account. The row-per-fee-type design carries each separately, as FO-06 Fee Accrual uses `fee_type` to partition the computed amounts.
- **FO-09 is the terms anchor; FO-06 is the computed amount.** The pattern mirrors FO-02 `class_fee_schedule` (terms) and FO-06 Fee Accrual (computed amount): FO-09 carries the contractual rate and basis, and FO-06 (owned by SD-12.11) carries the accrued amount for each period. SD-12.11 reads FO-09 for the servicing-fee rate and basis; it does not duplicate the formula.
- **Effective-dating.** The `fee_effective_from` and `fee_effective_to` fields capture the versioned history of the fee terms as distribution agreements are renegotiated. The history of terms is the audit trail; FO-09 rows accumulate rather than overwrite.
- **Boundary to FO-03.** A given FO-03 row (where the `investor_entity_id` is an intermediary) corresponds to one or more FO-09 rows for that intermediary and share class. The FO-03 row records what units the intermediary holds; the FO-09 rows record the account structure and fee terms of the relationship.
- **Revenue-share vs 12b-1.** A 12b-1 fee is paid from fund assets (it reduces the fund's NAV); a revenue-share payment is paid from the manager's own revenues. The `servicing_fee_type` discriminator distinguishes the two — important because 12b-1 flows through the fund's expense structure (affecting the OCF) whereas revenue-share does not.
- **Bare provenance pointers (`look_through_arrangement_ref` and `formula_spec_ref`).** These two fields are varchar provenance pointers rather than typed foreign keys. This is consistent with the FO-02/PM-10 precedent: `formula_spec_ref` on FO-06 points to either a PM-10 `terms_id` or a FO-02 schedule-version token depending on the fund structure; `look_through_arrangement_ref` on FO-09 points to a data-sharing agreement that may be a document reference or a technology-interface identifier, the exact target type being context-dependent. Typed union FKs are named as an open extension across all three fields when the model's FK grammar is extended. The figure-of-record-chain design note (see `docs/design/figure-of-record-chain.md`) consolidates this pattern.

## Out of scope

- The units the intermediary holds in each share class — those are FO-03 Investor Unitholding, where the intermediary is the `investor_entity_id`. FO-09 is the account relationship; FO-03 is the position.
- The computed fee amounts paid to the intermediary — those are FO-06 Fee Accrual records produced by SD-12.11, which reads FO-09's rate and basis. FO-09 carries the terms; FO-06 carries the amounts.
- The underlying per-investor accounts within the omnibus — those are at the intermediary's own recordkeeping layer, not modelled in OpenIM's fund-operations pack by design (the look-through gap). A future look-through entity would model this grain.
- The distribution agreement as a legal document — that is an E-15 Document Metadata record held by SD-13.11. FO-09 carries the fee-rate terms, not the agreement document itself; `formula_spec_ref` is the provenance pointer.

## Owned and consumed by

- **Owned by:** SD-15.4 Distribution Strategy & Channel Management — SD-15.4 governs the firm's distribution model, manages channel economics, and holds the distribution-agreement terms with each intermediary and platform. FO-09 is the first-class entity it owns, promoting the distribution-channel account relationship from a process artefact to a data record with a canonical schema.
- **Consumed by:** SD-12.11 Expense, Fee & Carry Processing (reads FO-09 to identify the applicable servicing-fee type, rate and basis for each omnibus account when computing and verifying the 12b-1, sub-TA, revenue-share or platform-fee amounts — the amounts are FO-06; FO-09 is the terms anchor); SD-12.15 Transfer Agency & Investor Dealing (reads FO-09 to identify which investor accounts in the register are omnibus accounts, distinguish them from direct investor accounts, and apply the appropriate dealing, confirmation and reporting treatment — the TA/dealing boundary); SD-12.9 Fund Accounting & NAV (reads FO-09 to identify 12b-1 fee-type accruals that flow through the fund's expense structure and must be included in the OCF/TER reconstruction — the omnibus position feeds the fund's units-in-issue via FO-03; FO-09 is read to identify the servicing-fee component that enters the NAV).

## FIBO alignment

**Partial — structural alignment at the account and party level; the servicing-fee terms, look-through gap, and omnibus register mechanics are OpenIM.**

- `fibo-fbc-pas-caa:Account` — FIBO's generic Account concept aligns to FO-09's account-relationship record at the conceptual level. FO-09 specialises E-25 Account, which in turn aligns to `fibo-fbc-pas-caa:Account`.
- `cmns-org:LegalEntity` (the OMG Commons base class FIBO imports and refines) aligns to the `intermediary_entity_id` FK → E-01 relationship — the intermediary is a Legal Entity in the distributor / nominee role.

What FIBO does not model, and what FO-09 adds:

- The **omnibus account at fund-register grain** — the registered account relationship between a fund and an intermediary, with the look-through boundary stated explicitly.
- The **servicing fee terms** (12b-1 / sub-TA / revenue-share / platform fee / trail) — the contractual rate, basis and effective-dating that the fee computation reads.
- The **look-through gap** as a first-class attribute — whether look-through data is available and under what arrangement.

## Open extensions

- A look-through entity (sub-account grain) — where an intermediary provides per-investor position-level data to the manager, a sub-entity at that grain recording the individual positions within the omnibus. Dependent on the data-sharing arrangement referenced by `look_through_arrangement_ref`.
- The distribution-services agreement sub-model — linking FO-09 to the executed legal agreement (an E-15 Document Metadata record) and its amendment history.
- The omnibus net settlement model — where the intermediary and manager net subscriptions and redemptions within the omnibus before transmitting only the net dealing order to the fund, FO-09 carries the net-settlement arrangement reference.
