"""Schema-drift check — the canonical-model contract enforcer.

Cross-checks each realised entity against the **Attribute schema** table in its
OpenIM model file (``model/entities/core/E-NN-*.md``) — the single source of
truth — across **two surfaces** and **fails on drift** on either:

1. **The Pydantic schema surface** (``check_entity``). A column the model file
   declares but the schema is missing, a field the schema declares but the model
   file does not (a rename or stray), or a column whose model-file type does not
   map to the schema field's realised Python type (``_TYPE_MAP``).
2. **The dbt staging-SQL surface** (``check_entity_staging``). The staging model
   ``reference/dbt/models/staging/stg_eNN_*.sql`` is a ``cast(<src> as <sqltype>)
   as <col>`` projection of the same model file. A column the model file declares
   but the staging projection omits, a projected column the model file does not
   declare, or a column whose staging SQL type does not map to the model-file type
   (``_SQL_TYPE_MAP`` -> the model vocabulary, then ``_staging_type_compatible``).
   The fiduciary-worst drift this catches: a ``decimal`` money column cast ``as
   double precision`` (silently became a float) -> a ``type_mismatch``.

The OpenIM model files are the single source of truth. This check is the
mechanism that keeps the implementation in lock-step with them on both surfaces —
the schema-drift CI validator the implementation plan names (the CI leg is
residual until ``reference/`` has CI; see the runbook). The staging models are
**read, never edited**: a real staging drift is a finding for the coordinator,
not something this check papers over.

Scope: **the ten realised entities only.** It is deliberately NOT a general
73-entity markdown parser — it iterates ``ENTITY_MODELS`` and reads only those
ten model files (and their ten staging models). Generalising to all 73 is a
later item, planned below, not built here.

Usage::

    python -m agentinvest_canonical_model.drift            # PASS/FAIL to stdout, exit 0/1
    # or, pytest-hosted:
    pytest tests/test_canonical_drift.py

The model files (and the dbt staging models) are resolved relative to the
repository root (four parents up from this file:
``reference/python/src/agentinvest_canonical_model/`` -> repo root), overridable
with ``OPENIM_REPO_ROOT`` for an out-of-tree run.

## 73-entity generalisation (planned, NOT built)

Today the check is bound to ``ENTITY_MODELS`` — the ten realised entities, each a
``core/E-NN-*.md`` model file with a hand-written Pydantic schema and a
``stg_eNN_*.sql`` staging model. Generalising to all 73 OpenIM entities is
deferred; the work it requires, concretely:

- **Model-file discovery beyond the core ten.** The other entities live under
  ``model/entities/`` in the specialisation packs — e.g.
  ``model/entities/packs/<pack>/PM-NN-*.md`` (multilateral / form-of-holding
  packs, per ADR-0031), with the ``PM-NN`` / ``PB-NN`` / ``PD-NN`` / ``PR-NN`` id
  forms (private-markets / public / debt / real-asset), not just ``E-NN``. The
  discovery walk must glob every ``E-NN`` *and* every ``Px-NN`` model file and
  derive the id from the filename, not assume the ``core/E-NN`` path shape.
- **Entities with no realised schema and/or no staging model.** Most of the 73
  have neither a Pydantic schema nor a staging model yet. The runner must classify
  each: schema+staging (full cross-check), schema-only, model-file-only
  (documentation entity), and report the coverage honestly rather than crash —
  the unstaged/un-realised state is the *expected* state at 73-entity scale, not a
  drift. (The ten-entity runner already surfaces the "no staging model" case; the
  73 case makes it the common path.)
- **Type-map completeness.** The specialisation packs may introduce model-file
  type keywords the current ``_TYPE_MAP`` / ``_SQL_TYPE_MAP`` do not cover
  (timestamp/datetime, geography, interval, enum-as-its-own-type). Each new
  keyword needs a deliberate mapping (and a decision on, e.g., ``timestamp`` ->
  ``date`` vs its own keyword), surfaced, not silently bucketed.
- **Per-surface coverage matrix.** At 73 the report becomes a matrix (entity x
  {model-file, schema, staging}) with a coverage summary, not a flat ten-row list.

Staged rollout: (1) generalise model-file discovery + id parsing across the packs
behind a flag, reporting coverage only (no fail); (2) extend the type-maps as the
pack files surface new keywords, each mapping reviewed; (3) turn the cross-check
on per-pack as schemas/staging models are realised, failing only where a contract
exists on both sides. It is deferred now because the ten realised entities are the
only ones with a schema *and* a staging model to cross-check — running a 73-entity
parser today would report 63 "no contract" rows and zero added drift coverage,
for a much larger and more brittle parser. The marts layer (OIM-110/111) is a
third surface for a later cycle.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import UnionType
from typing import Union, get_args, get_origin

from agentinvest_canonical_model.base import CanonicalEntity
from agentinvest_canonical_model.entities import ENTITY_MODELS

# The model-file declared type -> the set of acceptable realised Python types.
# A model column of `decimal` must be realised as Decimal (exact money); `float`
# only for the confidence scores; `varchar`/`char` -> str; `array`/`map` ->
# list/dict; `int`/`date`/`boolean` -> themselves. A model type maps to MORE than
# one acceptable Python type only where the model genuinely admits it.
_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "varchar": (str,),
    "char": (str,),
    "decimal": (Decimal,),
    "float": (float,),
    "int": (int,),
    "date": (date,),
    "boolean": (bool,),
    "bool": (bool,),
    "array": (list,),
    "map": (dict,),
}

# A dbt staging SQL type -> the model-file base-type vocabulary (the same keywords
# ``parse_model_attribute_schema`` emits). The staging models cast every column
# ``cast(<src> as <sqltype>) as <col>``; this maps the SQL type back to the model
# vocabulary so a staging column's type can be cross-checked against the model
# file. Crucially DISJOINT on money: ``decimal``/``numeric`` -> ``decimal`` while
# ``double precision``/``double``/``float``/``real`` -> ``float`` — so a ``decimal``
# money column cast ``as double precision`` is caught (it maps to ``float``, which
# is not compatible with the model's ``decimal``). ``timestamp`` maps to ``date``
# (the model vocabulary has no separate timestamp keyword; the staging layer uses
# ``date`` for the as-of columns — documented, revisited at 73-entity scale).
_SQL_TYPE_MAP: dict[str, str] = {
    "varchar": "varchar",
    "char": "varchar",
    "text": "varchar",
    "string": "varchar",
    "decimal": "decimal",
    "numeric": "decimal",
    "double precision": "float",
    "double": "float",
    "float": "float",
    "real": "float",
    "date": "date",
    "timestamp": "date",
    "timestamptz": "date",
    "integer": "int",
    "int": "int",
    "bigint": "int",
    "smallint": "int",
    "boolean": "boolean",
    "bool": "boolean",
    "array": "array",
    "map": "map",
    "json": "map",
    "jsonb": "map",
}

# For a model-file base type, the set of staging-normalised types that are a
# FAITHFUL realisation of it. Mostly identity (``decimal`` staging realises a
# model ``decimal``; ``float`` realises a model ``float``; etc.). Two model types
# admit MORE than their identity, for documented reasons:
#
#   - ``char`` and ``varchar`` are one string family (the model uses ``char`` for
#     fixed-width currency codes; staging casts them ``as varchar``).
#   - ``array`` and ``map`` legitimately serialise to ``varchar`` at the flat
#     staging grain. The staging models keep ``known_aliases`` (array) and
#     ``external_ids`` (map) as ``;``-joined / JSON *text* — the normalised
#     list/map shaping is the OIM-110/111 mart layer, documented in the staging
#     SQL comments. So a model ``array``/``map`` column projected ``as varchar``
#     in staging is the INTENDED flat-text carrier, not drift. (A native ``array``
#     / ``map`` cast would also be accepted.) This is NOT a loosening of the
#     money/scalar checks — ``decimal`` stays disjoint from ``float``.
_STAGING_TYPE_COMPAT: dict[str, frozenset[str]] = {
    "varchar": frozenset({"varchar"}),
    "char": frozenset({"varchar"}),
    "decimal": frozenset({"decimal"}),
    "float": frozenset({"float"}),
    "int": frozenset({"int"}),
    "date": frozenset({"date"}),
    "boolean": frozenset({"boolean"}),
    "bool": frozenset({"boolean"}),
    "array": frozenset({"array", "varchar"}),
    "map": frozenset({"map", "varchar"}),
}

# Where the dbt staging models live, relative to repo root.
_STAGING_DIR = Path("reference/dbt/models/staging")


@dataclass
class EntityDrift:
    """The drift findings for one entity."""

    entity_id: str
    model_file: str
    missing_from_schema: list[str] = field(default_factory=list)  # in model file, not in schema
    extra_in_schema: list[str] = field(default_factory=list)  # in schema, not in model file
    type_mismatches: list[str] = field(default_factory=list)  # column: model-type vs realised-type

    @property
    def clean(self) -> bool:
        return not (self.missing_from_schema or self.extra_in_schema or self.type_mismatches)


@dataclass
class StagingDrift:
    """The drift findings for one entity's dbt staging model vs its model file.

    ``staging_file`` is ``None`` and ``no_staging_model`` is True when the entity
    has a model file + a Pydantic schema but no ``stg_eNN_*.sql`` — a surfaced
    coverage gap, NOT a crash and NOT a silent skip.
    """

    entity_id: str
    model_file: str
    staging_file: str | None
    no_staging_model: bool = False
    missing_from_staging: list[str] = field(default_factory=list)  # in model file, not in staging
    extra_in_staging: list[str] = field(default_factory=list)  # in staging, not in model file
    type_mismatches: list[str] = field(default_factory=list)  # column: model-type vs staging-type

    @property
    def clean(self) -> bool:
        # An entity with no staging model is reported (not clean-or-drift): it is a
        # surfaced gap, neither a pass nor a type/column drift. ``clean`` reflects
        # only the column/type cross-check; ``no_staging_model`` is reported
        # separately and does NOT fail the build (there can legitimately be entities
        # without a staging model — see the 73-entity plan). The CLI exit code keys
        # off the column/type drift, not the coverage gap.
        return not (self.missing_from_staging or self.extra_in_staging or self.type_mismatches)


class StagingParseError(ValueError):
    """A staging-model projection has a shape the parser cannot read.

    Raised rather than silently dropping a column — a STOP-and-surface condition
    (a non-``cast`` projection, a join, an unrecognised line). The runner converts
    it to a reported finding so the CLI fails loudly instead of under-counting.
    """


def repo_root() -> Path:
    """Resolve the OpenIM repository root.

    Default: four parents up from this file
    (``.../reference/python/src/agentinvest_canonical_model/drift.py`` -> repo
    root). Overridable with ``OPENIM_REPO_ROOT`` (absolute path).
    """
    override = os.environ.get("OPENIM_REPO_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[4]


def _normalise_model_type(raw_type: str) -> str:
    """Reduce a model-file type cell to its base type keyword.

    The model files write types like ``varchar``, ``char``, ``decimal``,
    ``int``, ``date``, ``boolean``, ``float``, ``array``, ``map`` — sometimes
    annotated (``varchar (FK -> E-09)``, ``varchar (FK -> self)``). Strip the
    parenthetical annotation and lower-case to the base keyword.
    """
    base = raw_type.split("(", 1)[0].strip().lower()
    return base


def parse_model_attribute_schema(model_path: Path) -> dict[str, str]:
    """Parse the ``## Attribute schema`` markdown table from a model file.

    Returns an ordered mapping of ``column_name -> base_type_keyword``. Reads only
    the table under the ``## Attribute schema`` heading (stops at the next ``##``),
    so the role-model and ownership tables in the same file are not picked up.
    """
    text = model_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find the "## Attribute schema" heading.
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Attribute schema\s*$", line.strip()):
            start = i + 1
            break
    if start is None:
        raise ValueError(f"{model_path}: no '## Attribute schema' section found")

    columns: dict[str, str] = {}
    seen_header = False
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("## "):
            break  # next section — the attribute table is done
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        col_raw = cells[0]
        # Skip the header row (| Column | Type | Definition |) and the | --- | divider.
        if not seen_header:
            if col_raw.lower() == "column":
                seen_header = True
            continue
        if set(col_raw) <= {"-", ":", " "}:
            continue
        # The column name is wrapped in backticks in the model files: `entity_id`.
        col = col_raw.strip("`").strip()
        if not col:
            continue
        type_keyword = _normalise_model_type(cells[1].strip("`"))
        columns[col] = type_keyword

    if not columns:
        raise ValueError(f"{model_path}: '## Attribute schema' table parsed to zero columns")
    return columns


def _realised_field_base_types(annotation: object) -> tuple[type, ...]:
    """Reduce a Pydantic field annotation to its concrete base type(s).

    Strips ``Optional`` / ``X | None``, and reduces parameterised generics
    (``list[str]`` -> ``list``, ``dict[str, str]`` -> ``dict``) to their origin.
    Returns the non-``NoneType`` base types.
    """
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        out: list[type] = []
        for arg in get_args(annotation):
            if arg is type(None):
                continue
            out.extend(_realised_field_base_types(arg))
        return tuple(out)
    if origin is not None:
        # Parameterised generic (list[str], dict[str, str], tuple[...]).
        return (origin,)
    if isinstance(annotation, type):
        return (annotation,)
    return ()


def check_entity(model_cls: type[CanonicalEntity], root: Path) -> EntityDrift:
    """Cross-check one Pydantic schema against its model file's attribute schema."""
    model_path = root / model_cls.MODEL_FILE
    declared = parse_model_attribute_schema(model_path)
    realised = model_cls.model_fields

    result = EntityDrift(entity_id=model_cls.ENTITY_ID, model_file=model_cls.MODEL_FILE)

    declared_cols = set(declared)
    realised_cols = set(realised)

    result.missing_from_schema = sorted(declared_cols - realised_cols)
    result.extra_in_schema = sorted(realised_cols - declared_cols)

    # Type cross-check on the columns present in both.
    for col in sorted(declared_cols & realised_cols):
        model_type = declared[col]
        acceptable = _TYPE_MAP.get(model_type)
        if acceptable is None:
            result.type_mismatches.append(
                f"{col}: model type '{model_type}' is not a recognised model-file type keyword"
            )
            continue
        field_info = realised[col]
        realised_types = _realised_field_base_types(field_info.annotation)
        if not any(rt in acceptable or issubclass(rt, acceptable) for rt in realised_types):
            expected = [t.__name__ for t in acceptable]
            got = [t.__name__ for t in realised_types] or ["<none>"]
            result.type_mismatches.append(
                f"{col}: model declares '{model_type}' (expects {expected}), schema realises {got}"
            )

    return result


# ---------------------------------------------------------------------------
# The dbt staging-SQL surface.
# ---------------------------------------------------------------------------

# One staging projection line: ``cast(<src> as <sqltype>) as <output_col>`` with an
# optional trailing comma. ``<sqltype>`` may be parenthesised (``decimal(18, 2)``)
# or two-word (``double precision``). We capture the raw SQL type and the output
# column, then normalise the type via ``_SQL_TYPE_MAP``.
_CAST_PROJECTION = re.compile(
    r"""^cast\s*\(
        \s*[\w".]+\s+                 # the source column (identifier, maybe quoted)
        as\s+
        (?P<sqltype>[A-Za-z_][\w ]*?)  # the SQL type keyword(s) — letters/_/space
        \s*(?:\([^)]*\))?              # an optional ( precision, scale )
        \s*\)
        \s+as\s+
        (?P<col>"?[\w]+"?)             # the output column alias
        \s*,?\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _normalise_sql_type(raw_sql_type: str) -> str | None:
    """Map a staging SQL type keyword to the model-file base vocabulary.

    ``decimal(18, 2)`` -> ``decimal``; ``double precision`` -> ``float``;
    ``varchar`` -> ``varchar``; ``date`` -> ``date``; etc. Returns ``None`` for an
    unrecognised type (a STOP-and-surface — the runner reports it, does not drop
    the column). The parenthesised precision is already stripped by the regex; here
    we collapse internal whitespace so ``double  precision`` and ``double precision``
    both resolve.
    """
    key = " ".join(raw_sql_type.lower().split())
    return _SQL_TYPE_MAP.get(key)


def parse_staging_projection(staging_path: Path) -> dict[str, str]:
    """Parse a ``stg_eNN_*.sql`` model's projection list -> ``{output_col: raw_sql_type}``.

    Reads the ``select ... from`` block and parses each ``cast(<src> as <sqltype>)
    as <col>`` projection. Comment lines (``-- ...``), the ``with ... as (...)``
    CTE wrapper, the ``select`` / ``from`` keywords and blank lines are skipped. A
    projection line that is NOT a recognised ``cast(... as ...) as col`` shape
    raises ``StagingParseError`` — a STOP-and-surface, so no column is silently
    missed (a non-cast projection, a join, a CTE column, a function call).
    """
    text = staging_path.read_text(encoding="utf-8")
    columns: dict[str, str] = {}

    in_select = False
    for raw_line in text.splitlines():
        # Strip a trailing line comment, then whitespace.
        line = raw_line.split("--", 1)[0].strip()
        if not line:
            continue
        low = line.lower()
        if not in_select:
            # Skip everything up to and including the final `select` keyword: the
            # `with source as ( select * from {{ ref(...) }} )` CTE and any blank
            # lines. The projection list is the `select` that is NOT inside the CTE
            # parens — i.e. a bare `select` line on its own.
            if low == "select":
                in_select = True
            continue
        # We are in the projection list. Stop at the `from` of the outer select.
        if low.startswith("from ") or low == "from":
            break
        # Each projection must be a cast(... as ...) as col.
        m = _CAST_PROJECTION.match(line)
        if not m:
            raise StagingParseError(
                f"{staging_path}: projection line is not a recognised "
                f"`cast(<src> as <type>) as <col>` shape (STOP-and-surface — "
                f"a column could be silently missed): {line!r}"
            )
        col = m.group("col").strip('"')
        sqltype = m.group("sqltype").strip()
        columns[col] = sqltype

    if not in_select:
        raise StagingParseError(
            f"{staging_path}: no bare `select` projection block found "
            f"(STOP-and-surface — the staging model has an unexpected shape)"
        )
    if not columns:
        raise StagingParseError(
            f"{staging_path}: the `select` projection block parsed to zero columns "
            f"(STOP-and-surface)"
        )
    return columns


def _entity_slug(entity_id: str) -> str:
    """``E-07`` -> ``e07``. The staging-file stem prefix for a core ``E-NN`` entity."""
    return "e" + entity_id.split("-", 1)[1].strip().zfill(2)


def staging_path_for(model_cls: type[CanonicalEntity], root: Path) -> Path | None:
    """Resolve the ``stg_eNN_*.sql`` staging model for an entity, or ``None``.

    Globs ``reference/dbt/models/staging/stg_<eNN>_*.sql`` (the convention the
    OIM-103 staging layer follows). Returns the single match, or ``None`` when the
    entity has no staging model (a surfaced gap, not an error). Raises if the glob
    is ambiguous (>1 match) — an unexpected shape worth surfacing.
    """
    slug = _entity_slug(model_cls.ENTITY_ID)
    matches = sorted((root / _STAGING_DIR).glob(f"stg_{slug}_*.sql"))
    if not matches:
        return None
    if len(matches) > 1:
        raise StagingParseError(
            f"{model_cls.ENTITY_ID}: ambiguous staging models {[p.name for p in matches]} "
            f"(expected exactly one stg_{slug}_*.sql)"
        )
    return matches[0]


def check_entity_staging(model_cls: type[CanonicalEntity], root: Path) -> StagingDrift:
    """Cross-check one entity's dbt staging model against its model file.

    Mirrors ``check_entity`` for the staging-SQL surface: column set (missing /
    extra) and per-column type. The staging type is normalised to the model
    vocabulary (``_SQL_TYPE_MAP``) and compared via ``_STAGING_TYPE_COMPAT``, which
    keeps ``decimal`` disjoint from ``float`` (the money guard) while allowing the
    documented ``array``/``map`` -> ``varchar`` flat-text staging carrier. An
    entity with no staging model is reported as ``no_staging_model`` (a surfaced
    gap), not crashed-on.
    """
    model_path = root / model_cls.MODEL_FILE
    declared = parse_model_attribute_schema(model_path)

    staging_path = staging_path_for(model_cls, root)
    result = StagingDrift(
        entity_id=model_cls.ENTITY_ID,
        model_file=model_cls.MODEL_FILE,
        staging_file=(
            str(staging_path.relative_to(root)).replace("\\", "/") if staging_path else None
        ),
    )
    if staging_path is None:
        result.no_staging_model = True
        return result

    projected = parse_staging_projection(staging_path)

    declared_cols = set(declared)
    staging_cols = set(projected)
    result.missing_from_staging = sorted(declared_cols - staging_cols)
    result.extra_in_staging = sorted(staging_cols - declared_cols)

    for col in sorted(declared_cols & staging_cols):
        model_type = declared[col]
        compat = _STAGING_TYPE_COMPAT.get(model_type)
        if compat is None:
            result.type_mismatches.append(
                f"{col}: model type '{model_type}' is not a recognised model-file type keyword"
            )
            continue
        raw_sql_type = projected[col]
        staging_norm = _normalise_sql_type(raw_sql_type)
        if staging_norm is None:
            result.type_mismatches.append(
                f"{col}: staging SQL type '{raw_sql_type}' is not a recognised SQL type "
                f"(STOP-and-surface — unmapped type, not silently passed)"
            )
            continue
        if staging_norm not in compat:
            result.type_mismatches.append(
                f"{col}: model declares '{model_type}' (accepts {sorted(compat)}), "
                f"staging casts '{raw_sql_type}' -> '{staging_norm}'"
            )

    return result


def run_drift_check(root: Path | None = None) -> list[EntityDrift]:
    """Run the Pydantic-surface drift check over all ten entities."""
    root = root or repo_root()
    return [check_entity(cls, root) for cls in ENTITY_MODELS]


def run_staging_drift_check(root: Path | None = None) -> list[StagingDrift]:
    """Run the staging-SQL drift check over all ten entities. One StagingDrift each."""
    root = root or repo_root()
    return [check_entity_staging(cls, root) for cls in ENTITY_MODELS]


def format_report(results: list[EntityDrift]) -> str:
    """Human-readable PASS/FAIL report for the Pydantic-schema surface."""
    lines: list[str] = []
    drifted = [r for r in results if not r.clean]
    lines.append(
        f"canonical-model schema-drift check [Pydantic surface] — {len(results)} entities, "
        f"{len(drifted)} with drift"
    )
    for r in results:
        if r.clean:
            lines.append(f"  OK    {r.entity_id}  ({r.model_file})")
        else:
            lines.append(f"  DRIFT {r.entity_id}  ({r.model_file})")
            for col in r.missing_from_schema:
                lines.append(f"          - column '{col}' in model file is MISSING from the schema")
            for col in r.extra_in_schema:
                lines.append(
                    f"          - field '{col}' in schema is NOT in the model file (rename/stray)"
                )
            for mm in r.type_mismatches:
                lines.append(f"          - type drift: {mm}")
    verdict = "FAIL" if drifted else "PASS"
    lines.append(
        f"{verdict} [Pydantic]: {len(drifted)} entit{'y' if len(drifted) == 1 else 'ies'} drifted"
    )
    return "\n".join(lines)


def format_staging_report(results: list[StagingDrift]) -> str:
    """Human-readable PASS/FAIL report for the dbt staging-SQL surface."""
    lines: list[str] = []
    drifted = [r for r in results if not r.clean]
    unstaged = [r for r in results if r.no_staging_model]
    lines.append(
        f"canonical-model schema-drift check [staging-SQL surface] — {len(results)} entities, "
        f"{len(drifted)} with drift, {len(unstaged)} with no staging model"
    )
    for r in results:
        if r.no_staging_model:
            lines.append(
                f"  GAP   {r.entity_id}  ({r.model_file}) — no staging model "
                f"(stg_{_entity_slug(r.entity_id)}_*.sql); surfaced, not a drift"
            )
            continue
        if r.clean:
            lines.append(f"  OK    {r.entity_id}  ({r.staging_file})")
        else:
            lines.append(f"  DRIFT {r.entity_id}  ({r.staging_file})")
            for col in r.missing_from_staging:
                lines.append(
                    f"          - column '{col}' in model file is MISSING from staging projection"
                )
            for col in r.extra_in_staging:
                lines.append(
                    f"          - column '{col}' in staging is NOT in the model file (stray/rename)"
                )
            for mm in r.type_mismatches:
                lines.append(f"          - type drift: {mm}")
    verdict = "FAIL" if drifted else "PASS"
    lines.append(
        f"{verdict} [staging]: {len(drifted)} entit{'y' if len(drifted) == 1 else 'ies'} drifted; "
        f"{len(unstaged)} unstaged (surfaced)"
    )
    return "\n".join(lines)


def format_combined_report(
    schema_results: list[EntityDrift], staging_results: list[StagingDrift]
) -> str:
    """Both surfaces in one report, with a combined verdict."""
    schema_drift = any(not r.clean for r in schema_results)
    staging_drift = any(not r.clean for r in staging_results)
    overall = "FAIL" if (schema_drift or staging_drift) else "PASS"
    return "\n".join(
        [
            format_report(schema_results),
            "",
            format_staging_report(staging_results),
            "",
            f"OVERALL: {overall} (exit {1 if overall == 'FAIL' else 0}) — "
            f"fails on drift on EITHER surface.",
        ]
    )


def main() -> int:
    schema_results = run_drift_check()
    staging_results = run_staging_drift_check()
    print(format_combined_report(schema_results, staging_results))
    drift = any(not r.clean for r in schema_results) or any(not r.clean for r in staging_results)
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
