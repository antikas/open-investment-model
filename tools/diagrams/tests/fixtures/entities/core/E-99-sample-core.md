# E-99 — Sample Core Entity

A single-owner core entity fixture for the generator's parser tests.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `sample_id` | varchar | Primary key. |
| `asset_class_id` | varchar (FK → E-09) | Foreign key to Asset Class. |

## Owned and consumed by

- **Owned by:** SD-99.1 Sample With Service Operations.
- **Consumed by:** SD-99.2 Sample Without Service Operations.
