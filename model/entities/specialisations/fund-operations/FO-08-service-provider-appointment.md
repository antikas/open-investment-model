# FO-08 — Service-Provider Appointment

The first-class record of which E-01 Legal Entity is appointed to which FO-01 Fund Product in which service-provider role, and over which dates. One row per (fund-product, service provider, role): a fund with a custodian, a depositary, an administrator, a transfer agent, a trustee, an auditor, a prime broker, a ManCo/AIFM and an investment manager carries nine appointment rows, each with its own lifecycle.

**Specialises:** a relationship entity extending the core entity model. FO-08 is not itself a holdable instrument or a transaction event; it is the appointment edge between FO-01 (the issued fund) and E-01 (the appointed party). Structurally it resembles the Party Relationship pattern noted as an open extension on E-01 — applied here at the fund-operations grain, where the relationship has its own lifecycle (appointed / terminated dates, status) and the role enum is the defining discriminator.

**Single owner:** SD-17.8 Vendor, Outsourcing & Service-Provider Oversight — the appointing and commercial-oversight SD that holds the due-diligence, SLA and exit-plan lifecycle for each provider. SD-13.2 Entity & Counterparty Master owns the E-01 party records the appointment references; it does not own the appointment relationship itself. The appointment is a single-writer record: SD-17.8 creates and terminates rows; consumer SDs read them.

**Design rationale — entity rather than attribute set.** Three characteristics require the appointment to be a first-class entity rather than a field on FO-01 or a role tag on E-01: (1) a fund has *many* service providers simultaneously across multiple roles; (2) each appointment has its own dated lifecycle — `appointed_date`, optional `terminated_date`, and `status` — that must be auditable independently; and (3) the role enum discriminates what each provider does with the fund's assets or operations, and that discriminator is the basis on which SD-12.5, SD-12.9 and SD-12.15 consume the record. A field on FO-01 cannot hold multiple appointments per role type over time; a role tag on E-01 cannot bind to a specific fund; only a row-per-(fund, provider, role) entity can.

## Purpose

A fund product sits inside a web of appointed parties with defined roles. The regulator and the fund's board hold the management company, AIFM or adviser responsible for ensuring the right parties are appointed and performing. The operational service-provider ecosystem is:

- a **custodian** — safekeeps the fund's assets; operates the sub-custody network in each market.
- a **depositary** — distinct from the custodian under UCITS and AIFMD: the depositary provides independent oversight of the fund's NAV accuracy, cashflow integrity and investor-dealing compliance, and delegates the asset-safekeeping function to the custodian. The depositary's duty is regulatory oversight; the custodian's duty is safekeeping. Conflating them misscopes SD-12.5, which manages the interface with both but in different operational modes — SD-12.5's asset-level holdings-verification function runs against the custodian's record; its dealing-oversight interaction runs against the depositary's NAV and cashflow-monitoring output.
- a **fund administrator** — strikes the NAV, keeps the fund's books; for many managers, the administrator and transfer agent are from one firm (SS&C, State Street, BNY, Northern Trust).
- a **transfer agent** — maintains the investor register, processes subscriptions and redemptions, issues contract notes.
- a **trustee** — the independent fiduciary of a unit trust or similar structure; fulfils the trustee-oversight role BD-16's governance surface relies on.
- an **auditor** — conducts the annual audit of the fund's financial statements.
- a **prime broker** — provides financing, securities lending, settlement and sometimes custody for hedge funds and alternative strategies.
- a **ManCo/AIFM** — the regulated management company or alternative investment fund manager that carries overall regulatory responsibility for the fund. The ManCo/AIFM retains regulatory responsibility at all times; it may delegate portfolio management to an investment manager. This role is the open-ended analogue of PM-02 GP / Management Company (which models the closed-end GP that exercises discretion directly): a ManCo/AIFM carries responsibility but delegates the investment decision; a GP exercises discretion directly without delegation. The two roles are peers across the fund-form boundary, not substitutes.
- an **investment manager** — runs the money under delegation from the ManCo/AIFM. The investment manager exercises portfolio management under the authority the ManCo/AIFM has granted; the ManCo/AIFM retains regulatory responsibility. The `delegates_to_entity_id` field on the ManCo/AIFM appointment row records this delegation, pointing to the E-01 record of the investment manager. A fund operated directly by a single GP or adviser (no delegation) carries only an `investment_manager` appointment with no ManCo/AIFM delegation edge.

FO-08 is the record that answers, for any given fund at any point in time: who holds which role, and over which dates. SD-17.8 uses it as the anchor for commercial-oversight lifecycles (due diligence, SLA, exit plans). SD-12.5 reads it to identify which E-01 entity is the appointed depositary and which is the appointed custodian when managing the respective operational interfaces. SD-12.9 reads it to confirm which entity is the administrator delivering NAV feeds. SD-12.15 reads it to confirm which entity is the transfer agent.

## Attribute schema

### Identity and relationship

| Column | Type | Definition |
|---|---|---|
| `appointment_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for this appointment row. |
| `fund_product_id` | varchar (FK → FO-01) | The issued fund this appointment relates to. |
| `provider_entity_id` | varchar (FK → E-01) | The legal entity appointed in this role — held at the party-master grain (E-01 canonical record) regardless of whether the role has a private-markets specialisation entity (PM-03 Fund Administrator). |

### Role

| Column | Type | Definition |
|---|---|---|
| `role` | varchar | The service-provider role this appointment record covers. Enum: `custodian` / `depositary` / `fund_administrator` / `transfer_agent` / `trustee` / `auditor` / `prime_broker` / `manco_aifm` / `investment_manager`. |
| `delegates_to_entity_id` | varchar (FK → E-01, nullable) | For `role = manco_aifm` only: the E-01 record of the investment manager to whom the ManCo/AIFM has delegated portfolio management. Null for all other roles and for ManCo/AIFM appointments where the ManCo itself exercises portfolio management without delegation. |

### Lifecycle

| Column | Type | Definition |
|---|---|---|
| `appointed_date` | date | The date on which this appointment became effective. |
| `terminated_date` | date (nullable) | The date on which this appointment ended. Null for currently active appointments. |
| `status` | varchar | `active` / `terminated` / `under_transition`. |

## Notes

- **One row per (fund, provider, role).** A party that plays two roles for the same fund — for example, a firm that is both the fund administrator and the transfer agent — holds two FO-08 rows, one per role. This preserves the role-level audit trail and allows each appointment to be independently dated and terminated.
- **Historical appointments are retained.** When a provider is replaced, the row's `terminated_date` is populated and `status` is set to `terminated`; a new row is created for the incoming provider. The full history of which party held each role and over which dates is preserved in the append pattern — rows are never deleted or overwritten.
- **The depositary ≠ custodian distinction is structural, not definitional.** The depositary role and the custodian role are separate rows in FO-08. Under UCITS and AIFMD, the depositary has a statutory role independent of custodians — it verifies the NAV calculation, monitors cashflows and investor dealing, and is appointed by the fund independent of the manager. Where the same institution fills both the depositary and custodian roles (a common arrangement for larger global custodians who also hold depositaryship), there are two FO-08 rows for that institution: one `role = depositary`, one `role = custodian`. The operational distinction between the two — SD-12.5 managing two different interfaces with the same firm — is preserved at the row level.
- **The ManCo/AIFM delegation edge.** For an open-ended regulated fund that appoints a ManCo/AIFM to carry regulatory responsibility: the `manco_aifm` appointment row carries `delegates_to_entity_id` pointing to the investment manager if portfolio management is delegated. The investment manager itself also holds an `investment_manager` appointment row. The two rows together model the delegation structure without requiring a new entity: the ManCo retains responsibility; the investment manager operates under delegation; the relationship is an FK edge within the existing FO-08 entity.

## Out of scope

- The commercial terms of the appointment — the service-level agreement, the fee schedule with the provider, the due-diligence findings — those are SD-17.8's operational records (an SLA / service-level entity is an open extension of SD-17.8).
- The party master for the appointed entity — that is E-01 Legal Entity owned by SD-13.2.
- The trustee and depositary as separate structural entities — they are named roles of E-01, not separate entities. The role-has-structure argument that created PM-02 GP / Management Company and PM-03 Fund Administrator does not apply here: the appointment relationship itself is the first-class thing; the party behind it is E-01.
- The sub-custody network — the chain below the custodian's first-tier appointment — is an open extension of SD-12.5, not modelled as additional FO-08 rows.

## Owned and consumed by

- **Owned by:** SD-17.8 Vendor, Outsourcing & Service-Provider Oversight — single owner; the appointing and commercial-oversight function that creates, monitors and terminates each service-provider appointment.
- **Consumed by:** SD-12.5 Custody & Safekeeping Oversight (reads the `role = custodian` and `role = depositary` rows to identify the appointed custodian and depositary for each fund, distinguishing the safekeeping obligation from the independent NAV-and-cashflow oversight obligation); SD-12.9 Fund Accounting & NAV (reads the `role = fund_administrator` row to confirm the appointed administrator delivering the NAV feed and the fund books); SD-12.15 Transfer Agency & Investor Dealing (reads the `role = transfer_agent` row to confirm the appointed transfer agent for each fund product); SD-16.1 Corporate & Fund Governance (reads the `role = trustee`, `role = depositary` and `role = auditor` rows to confirm the fund's key independent appointments for the governing-body oversight surface). The E-01 party records referenced by `provider_entity_id` and `delegates_to_entity_id` are mastered by SD-13.2 Entity & Counterparty Master — SD-13.2 is the source FO-08 reads from, not a consumer of the appointment relationship.

## FIBO alignment

**Partial — role-level reuse; appointment-relationship layer is OpenIM.**

FIBO models the party roles that map onto FO-08's `role` enum:

- `fibo-sec-fund-fund:FundManager` — the entity in the fund-manager role; maps onto the `manco_aifm` and `investment_manager` role values (FIBO does not distinguish ManCo-as-responsible-entity from investment-manager-as-delegate; that distinction is OpenIM's).
- `fibo-sec-fund-fund:FundAdministrator` — the entity in the fund-administrator role; maps onto `fund_administrator`.

What FIBO does not model, and what FO-08 adds:

- The **appointment relationship itself** — a dated, lifecycle-bearing record binding a specific fund to a specific party in a specific role. FIBO models the role as a class; it does not model the appointment as a first-class record with `appointed_date`, `terminated_date` and `status`.
- The **depositary as a distinct role** from the custodian. FIBO's Funds/CIV namespace does not define a Depositary class separate from the Custodian concept.
- The **ManCo/AIFM → investment manager delegation edge** — the `delegates_to_entity_id` FK that records which entity is carrying out portfolio management under delegation from the regulated responsible entity.
- The **trustee, auditor and prime broker roles** in the fund-services context.

## Notes on roles without a named operational consumer SD

Three roles in the `role` enum — `prime_broker`, `manco_aifm`, and `investment_manager` — have no dedicated operational consumer SD listed in the "Owned and consumed by" section. This is the union-model principle at work: the model names every role that can appear in a fund's appointment register, whether or not the current SD set has a per-role consumer explicitly wired.

- **`prime_broker`** — the prime broker provides financing, securities lending, settlement and often custody to hedge funds and alternative strategies. The custody and asset-safekeeping dimension overlaps with SD-12.5's operational interface (the custodian row), and SD-12.5 reads those rows. The prime-brokerage-specific operational surface — portfolio financing, securities-lending books, margin reporting — sits closest to SD-12.13 Securities Lending Operations, which manages the firm's securities-lending and repo book. A formal consumer-SD wiring of the `prime_broker` appointment row to SD-12.13 is a genuine candidate; it is an open extension when the prime-brokerage surface is next developed.
- **`manco_aifm`** — the ManCo/AIFM carries overall regulatory responsibility for the fund; it delegates portfolio management via the `delegates_to_entity_id` FK to the investment manager. The operational surface of the ManCo relationship — the regulatory reporting obligations, the UCITS/AIFMD compliance programme, the fund-board interface — sits in SD-16.1 Corporate & Fund Governance and in the regulatory-reporting and compliance SDs. A formal ManCo-appointment consumer wiring to those SDs is an open extension.
- **`investment_manager`** — the investment manager exercises portfolio management under delegation from the ManCo/AIFM. The wiring to the front-office SDs (BD-05 Portfolio Management, BD-06 Trading & Execution) is conceptual rather than a structured FO-08-consumer edge; those SDs consume E-03 Portfolio / Mandate and E-04 Holding / Position, not the appointment record directly. The appointment record is the governance / oversight artefact; the investment-management operations consume the portfolio and position entities.

These three roles are model-complete (named and defined); the absence of an explicit consumer-SD `**Consumes:**` edge is a deliberate union-model choice, not a gap requiring a new SD to be invented.

## Open extensions

- The sub-custodian network — the chain below the first-tier appointed custodian, where global custodians operate through local sub-custody agents.
- A fourth-party (sub-outsourcing) chain extension — for the administrator that sub-outsources to a technology platform or calculation agent.
- SLA / service-level records attached to each appointment row (an extension of SD-17.8's open SLA entity).
- Appointment-history audit annotations — regulatory-grade records of when a change was made, by whom, and under what authority (the fund-board consent or ManCo decision to change a service provider).
- A formal `prime_broker` → SD-12.13 Securities Lending Operations consumer-SD edge when the prime-brokerage operational surface is next developed.
