# E-27 — Sample Co-Owned Entity

A co-owned entity fixture — two co-equal owners — for the parser tests.

**Specialises:** E-09 Asset Class.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `coowned_id` | varchar | Primary key. |
| `parent_id` | varchar (FK → self) | Self-referential parent (literal notation). |
| `corrects_id` | varchar (FK → E-27, self-ref) | Self-referential correction (id notation). |
| `subject_id` | varchar (FK → {E-09, E-99, PM-99}) | Polymorphic FK across three entity types. |

## Owned and consumed by

- **Owned by:** co-owned by **SD-99.1 Sample With Service Operations** and **SD-99.2 Sample Without Service Operations** — a single concept with two co-equal owners.
- **Consumed by:** SD-99.1 Sample With Service Operations.
