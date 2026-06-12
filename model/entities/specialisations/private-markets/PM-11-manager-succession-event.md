# PM-11 — Manager Succession Event

A change in the manager entity behind a fund — a merger, rebrand or acquisition. Links a predecessor GP / management company (PM-02) to a successor, with a typed event and an effective date.

## Purpose

A manager is not static over a fund's life. Firms merge, rebrand and are acquired. When that happens, the GP entity behind a fund changes — and performance analysis must remain continuous across the event: a fund's track record does not reset because its manager rebranded. The Manager Succession Event is the record of the transition. PM-02 holds the firm identities; PM-11 holds the transitions between them, so a query can follow a fund's manager lineage through every corporate event.

> The succession pattern generalises beyond private markets — an external long-only or hedge-fund manager can also be acquired. PM-11 is filed in the private-markets pack because GP succession is where it bites hardest and where the source material framed it; an open question is whether to lift it to the core as a general Legal Entity succession event.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `succession_id` | varchar | Primary key. |
| `predecessor_gp_id` | varchar (FK → PM-02) | The manager entity before the event. |
| `successor_gp_id` | varchar (FK → PM-02) | The manager entity after the event. |
| `event_type` | varchar | `merger` / `rebrand` / `acquisition`. |
| `effective_date` | date | When the succession took effect. |
| `source` | varchar | The source the event was captured from. |

## Notes

- The event is **immutable** — a succession that happened is a fact.
- A rebrand also produces a new alias on the GP master (the old name moves to `known_aliases` / E-13 Entity Alias); the succession event records *that* the change happened and when, the alias records the name.

## Out of scope

- The manager entities themselves — those are PM-02 GP / Management Company, referenced as predecessor and successor; PM-11 holds the transition between them, not the firm identities.
- The new name a rebrand produces — that is recorded as an E-13 Entity Alias on the GP master; PM-11 records *that* the change happened and when, the alias records the name.
- Partial successions — a team spin-out taking some funds and not others — named as an open extension; the entity covers whole-firm merger, rebrand and acquisition.
- A general core Legal Entity succession event covering all manager types — an open question; PM-11 is filed in the private-markets pack where GP succession bites hardest.

## Owned and consumed by

- **Owned by:** SD-13.2 Entity & Counterparty Master.
- **Consumed by:** SD-09.2 Performance Attribution (manager-level continuity), SD-03.6 GP & Manager Monitoring, SD-03.8 Re-Up & Manager Relationship Management.

## Open extensions

- Partial successions — a team spin-out that takes some funds and not others.
- Whether to generalise to a core Legal Entity succession event covering all manager types.
