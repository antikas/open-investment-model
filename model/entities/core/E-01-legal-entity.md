# E-01 — Legal Entity

The universal party master. Every organisation OpenIM holds a record of is a Legal Entity — the investing institution itself, the issuers of the securities it holds, its trading and service counterparties, the managers it allocates to, its custodians, its index providers, the private companies it holds through funds. There is one master for all of them, and what distinguishes them is the **role** each plays, not a separate entity.

## Why one party master

The first cut of OpenIM had separate masters for GP, fund administrator, counterparty and portfolio company. That is the private-markets habit, and it does not generalise: a fixed-income manager's core exposure is to bond *issuers*, an equity manager faces *brokers* and *custodians*, every investor faces trading *counterparties*. Modelling each as its own master multiplies structure and breaks the moment one organisation plays two roles — a bank that is both a counterparty and an issuer, a firm that is both a manager and, through its own listed shares, an issuer.

The generalised model has **one Legal Entity master** and a **role** model on top of it. This is also the FIBO-faithful shape — FIBO Business Entities models the legal entity, and a role is distinct from the entity that bears it. E-01 aligns to FIBO Business Entities (see [`../../fibo-alignment.md`](../../fibo-alignment.md)).

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `entity_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for the legal entity. |
| `entity_name` | varchar | Canonical legal name. |
| `entity_type` | varchar | The kind of organisation — corporation, partnership, fund, government body, trust, etc. |
| `lei` | varchar | Legal Entity Identifier, where one exists. |
| `domicile` | varchar | Primary jurisdiction. |
| `parent_entity_id` | varchar (FK → self) | The parent in a corporate group; null at the top. Carries the hierarchy that group-level exposure aggregation needs. |
| `known_aliases` | array | Names the entity has been seen under (the in-record view of E-13 Entity Alias). |
| `external_ids` | map | External-system identifiers (the in-record view of E-14 External Identifier). |
| `status` | varchar | `active` / `inactive` / `merged` / `dissolved`. |
| `first_seen_at` | date | When the investor first encountered this entity. |

## The role model

A Legal Entity plays one or more **roles**. A role is how the entity relates to the investor or to the investment process:

| Role | What it means |
|---|---|
| `investor` | The investing institution itself (and, where it has them, its own internal vehicles). |
| `issuer` | Issues a security the investor holds — a sovereign, a corporate, an agency. The credit behind a bond. |
| `counterparty` | Faced in a transaction — a broker, a dealer, an OTC derivative counterparty, a securities-lending counterparty, a clearing house. |
| `manager` | Manages capital for the investor — an external long-only manager, a hedge fund manager, or (in the private-markets pack) a GP. |
| `custodian` | Safekeeps the investor's assets. |
| `administrator` | Administers a fund or vehicle (specialised in the private-markets pack as Fund Administrator, PM-03). |
| `portfolio_company` | An operating company the investor holds exposure to (specialised in the private-markets pack as Portfolio Company, PM-04). |
| `index_provider` | Provides a benchmark or index. |

A role can carry role-specific attributes — a counterparty role carries a credit rating (as a classification, E-12) and is the unit of counterparty-exposure aggregation; a manager role carries the relationship start date. Where a role has substantial structure of its own — a fund administrator's delivery method and data-quality tier, a portfolio company's look-through lineage — that structure lives in a **specialisation entity** that specialises E-01 for that role. Where a role has no extra structure — counterparty, issuer, index provider — the role is all there is, and there is no separate entity.

## The golden key

`entity_id` is OpenIM-assigned and internal, for the same reason every OpenIM master is internally keyed: external identifiers (LEI, registry numbers) are unstable, incomplete in private markets, and non-interoperable. The LEI is held as an attribute and as an E-14 External Identifier; it is never the primary key.

## Resolution

Legal entities resolve through the three-tier cascade common to every OpenIM master — exact external-identifier match, alias / normalised-name match, then a steward review queue for the unresolved. Resolution difficulty varies sharply by role: counterparties, issuers and managers are largely regulated entities with LEIs and resolve easily; private portfolio companies have no universal identifier and are the hard case (see PM-04).

## Out of scope

- The *role* a Legal Entity plays — issuer, counterparty, manager, custodian — is not a separate entity; a role with no extra structure is just an attribute of E-01, and a role with substantial structure lives in a specialisation (PM-02 GP, PM-03 Fund Administrator, PM-04 Portfolio Company).
- A fund or vehicle as a *holdable thing* — that is E-02 Instrument / Asset (and PM-01 Fund & Vehicle); a fund is a Legal Entity here only when it plays a role such as committing LP.
- The names and external identifiers a Legal Entity has been seen under in normalised, queryable form — those are E-13 Entity Alias and E-14 External Identifier, of which E-01 carries only the in-record `known_aliases` / `external_ids` view.
- A change of the entity behind a fund — a merger, rebrand or acquisition — that is PM-11 Manager Succession Event.

## Owned and consumed by

- **Owned by:** SD-13.2 Entity & Counterparty Master.
- **Consumed by:** effectively every domain — issuers by SD-07.2 Credit & Counterparty Risk and the fixed-income domains; counterparties by SD-06 Trading & Execution and SD-11.4 Margin & Collateral Operations; managers by BD-03 Manager & Fund Investment; and the investor and its vehicles by the portfolio and reporting domains — specifically SD-12.15 Transfer Agency & Investor Dealing (the registered investors in the fund) and the reporting domains.

## Open extensions

- **Alias / external-identifier canonicality.** E-13 Entity Alias and E-14 External Identifier are canonical for the names and external identifiers a Legal Entity has been seen under; the in-record `known_aliases` array and `external_ids` map on E-01 are a declared denormalised read-cache, derivable from E-13 / E-14 and regenerated from them, not an independent source.
- A standalone **Party Role** entity, if the inline role model proves too thin — roles with their own lifecycle (a counterparty relationship opening and closing) may warrant it.
- **Party Relationship** — relationships between entities beyond the corporate parent hierarchy (manager-of-fund, successor-of, guarantor-of).
- The concrete FIBO Business Entities concept mapping.
