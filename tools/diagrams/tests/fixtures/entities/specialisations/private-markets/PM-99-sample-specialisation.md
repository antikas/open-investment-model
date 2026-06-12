# PM-99 — Sample Specialisation Entity

A specialisation-pack entity fixture for the parser tests.

**Specialises:** E-99 Sample Core Entity.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `sample_pm_id` | varchar | Primary key. |
| `parent_id` | varchar (FK → E-99) | Foreign key to the parent core entity. |

## Owned and consumed by

- **Owned by:** SD-99.2 Sample Without Service Operations.
- **Consumed by:** SD-99.1 Sample With Service Operations.
