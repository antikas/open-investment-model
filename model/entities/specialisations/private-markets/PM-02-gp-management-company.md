# PM-02 — GP / Management Company

The external manager an investor commits capital to in the private-markets model. Well-known as an entity, but structurally subtle.

**Specialises:** E-01 Legal Entity, in the `manager` role. PM-02 adds the private-markets-specific structure that role needs — the branded-firm / management-company / per-fund-GP distinction, and the relationship to funds.

## The three things a "manager" can mean

- **The branded firm** — the name everyone uses. Neither a single legal entity nor necessarily the management company.
- **The management company** — the operating entity that employs people, owns the brand, manages multiple funds.
- **The per-fund GP entity** — a legal entity (often an LLC) specific to a single fund. A large firm has dozens.

OpenIM masters the manager at the **management-company level** as a Legal Entity in the manager role, and links downward to the per-fund GP entities and upward to the branded firm. A fund (PM-01) references the GP master through `gp_id`.

## Why it is comparatively easy

GP mastering is low-difficulty: managers are few (dozens, not thousands), onboarded proactively when the investor first commits, and have a stable public identity, usually with an LEI. The subtleties are the branded-firm / management-company / GP-entity distinction, and **manager succession** — mergers, rebrands and acquisitions (PM-11).

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `gp_id` | varchar | **Golden key**, at management-company level (also the `entity_id` of the Legal Entity in the manager role). |
| `gp_name` | varchar | Canonical firm name. |
| `known_aliases` | array | Every name the firm has been seen under, including historical names after a merger or rebrand. |
| `lei` | varchar | LEI of the management company. |
| `domicile` | varchar | Primary jurisdiction. |
| `relationship_start_date` | date | When the investor first committed to a fund managed by this firm. |
| `external_ids` | map | Data-vendor manager IDs. |

## Resolution

Three-tier matching; unresolved volume is low. The common non-trivial case is a firm appearing under a historical name after a succession event — resolved by adding the historical name to `known_aliases` (E-13) and, where a genuine entity change occurred, recording a Manager Succession Event (PM-11).

## Out of scope

- The generic party master a GP specialises — that is E-01 Legal Entity in the `manager` role; PM-02 adds only the private-markets-specific structure that role needs.
- A change in the manager entity behind a fund — a merger, rebrand or acquisition — that is PM-11 Manager Succession Event; PM-02 holds firm identities, PM-11 holds the transitions between them.
- The funds a GP manages — those are PM-01 Fund & Vehicle, which references the GP through `gp_id`.
- The fund administrator — a distinct service-provider role — that is PM-03 Fund Administrator, not the GP.

## Owned and consumed by

- **Owned by:** SD-13.2 Entity & Counterparty Master.
- **Populated via:** SD-03.1 Manager Sourcing & Pipeline, SD-03.5 Fund Commitment & Subscription.
- **Consumed by:** SD-03.2 Manager Research & Selection, SD-03.6 GP & Manager Monitoring, SD-03.8 Re-Up & Manager Relationship Management, SD-09.2 Performance Attribution, PM-01 Fund & Vehicle.

## Open extensions

- The per-fund GP-entity sub-structure beneath the management company.
- The full relationship between PM-02 and PM-11 Manager Succession Event.
