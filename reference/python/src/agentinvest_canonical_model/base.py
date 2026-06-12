"""Shared base + metadata for the canonical-model schemas.

Every canonical schema declares, in a typed ``ModelFileLink`` on its
``model_config["json_schema_extra"]``, the link back to its OpenIM model file
(``model/entities/E-NN-*.md``) and the ownership/grain shape the model file
declares. The schema-drift check (``drift.py``) reads this metadata to locate the
model file and cross-check the attribute set; the orchestrator and tools read the
schemas themselves. Keeping the linkage *on the schema* (not in a side-table)
means a new entity cannot be added without declaring where its contract lives.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class OwnershipPattern(StrEnum):
    """The four ownership patterns from ``model/ownership-map.md``.

    Carried as schema metadata so a consumer (and the drift check) can see, on
    the schema itself, whether an entity is single-owner, key-partitioned,
    faceted or co-owned — and, for key-partitioned entities, which column is the
    partition key.
    """

    SINGLE = "single"
    KEY_PARTITIONED = "key_partitioned"
    FACETED = "faceted"
    CO_OWNED = "co_owned"


class CanonicalEntity(BaseModel):
    """Base class for every canonical-model entity schema.

    - ``extra="forbid"`` — an instance may not carry a field the schema does not
      declare. The canonical model is closed: an undeclared attribute is drift,
      caught at instance-validation time as well as by the drift check.
    - ``frozen=True`` — canonical records are values. The append-only entities
      (E-07/E-19/E-20) are *never* mutated in place; a restatement is a new row
      (a new instance), matching the model files' append-only declaration.
    - ``str_strip_whitespace`` / ``validate_assignment`` keep the typed contract
      honest at the edges where raw CSV/seed text crosses in.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # --- model-file linkage metadata (read by drift.py; subclasses override) ---
    # Declared as ClassVars on the base so (a) Pydantic treats them as class
    # attributes, not fields, and (b) the drift check and consumers can read them
    # off the base type. Each concrete entity overrides all five.
    ENTITY_ID: ClassVar[str] = ""
    MODEL_FILE: ClassVar[str] = ""
    OWNERSHIP: ClassVar[OwnershipPattern] = OwnershipPattern.SINGLE
    PARTITION_KEY: ClassVar[str | None] = None
    GRAIN: ClassVar[tuple[str, ...]] = ()
