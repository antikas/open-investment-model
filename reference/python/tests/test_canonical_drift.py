"""The schema-drift check, pytest-hosted — clean on the ten, across both surfaces.

The negative ("fails on a planted drift") leg is proven separately: a planted
drift is added to a schema or a model file and the check is run, then reverted.
Here we assert the check is CLEAN on the committed ten (Pydantic schemas AND dbt
staging SQL), and we exercise the drift-detection machinery directly with synthetic
drifted schemas and synthetic staging SQL so the "fails on drift" behaviour is
itself tested and does not depend on a manual plant.

The **money-critical decimal->float retype** is asserted on BOTH surfaces (a
``decimal`` model column realised as ``float`` / cast ``as double precision`` ->
``type_mismatch``), with positive controls (a genuine ``decimal(p,s)`` on a
``decimal`` column, and a genuine ``double precision`` on the ``float``
``confidence_score`` -> CLEAN). These are revert-sensitive: remove or loosen the
type cross-check and they go RED.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import Field

from agentinvest_canonical_model.base import CanonicalEntity, OwnershipPattern
from agentinvest_canonical_model.drift import (
    StagingDrift,
    StagingParseError,
    check_entity,
    check_entity_staging,
    parse_model_attribute_schema,
    parse_staging_projection,
    repo_root,
    run_drift_check,
    run_staging_drift_check,
    staging_path_for,
)
from agentinvest_canonical_model.entities import (
    E01LegalEntity,
    E04HoldingPosition,
    E07Valuation,
)


def test_drift_check_clean_on_all_realised() -> None:
    """The committed schemas match their model files — zero drift.

    Thirteen realised entities: the original ten, the reconciliation substrate's
    E-05 Transaction + E-06 Cash Flow Event, and E-24 Reconciliation Break (the
    engine-owned finding the reconciliation engine emits; its Pydantic schema is
    drift-checked here even though it has no dbt staging model).
    """
    results = run_drift_check()
    assert len(results) == 13
    drifted = [r for r in results if not r.clean]
    assert not drifted, "\n".join(
        f"{r.entity_id}: missing={r.missing_from_schema} extra={r.extra_in_schema} "
        f"type={r.type_mismatches}"
        for r in drifted
    )


def test_model_files_parse_to_nonempty_attribute_schemas() -> None:
    """Each model file's '## Attribute schema' table parses to >0 columns."""
    root = repo_root()
    for cls in (E01LegalEntity,):
        cols = parse_model_attribute_schema(root / cls.MODEL_FILE)
        assert cols  # E-01 has 10 columns
        assert "entity_id" in cols
        assert cols["entity_id"] == "varchar"
        assert cols["first_seen_at"] == "date"


def test_drift_check_catches_a_missing_column() -> None:
    """A schema missing a model-file column is reported as drift (positive test)."""

    class DriftedLegalEntity(CanonicalEntity):
        # Deliberately omits `status` and `first_seen_at` from E-01's schema.
        entity_id: str = Field(description="...")
        entity_name: str = Field(description="...")
        entity_type: str = Field(description="...")
        lei: str | None = None
        domicile: str | None = None
        parent_entity_id: str | None = None
        known_aliases: list[str] = Field(default_factory=list)
        external_ids: dict[str, str] = Field(default_factory=dict)

        ENTITY_ID = "E-01"
        MODEL_FILE = "model/entities/core/E-01-legal-entity.md"
        OWNERSHIP = OwnershipPattern.SINGLE
        PARTITION_KEY = None
        GRAIN = ()

    result = check_entity(DriftedLegalEntity, repo_root())
    assert not result.clean
    assert "status" in result.missing_from_schema
    assert "first_seen_at" in result.missing_from_schema


def test_drift_check_catches_a_retyped_column() -> None:
    """A column realised at the wrong type is reported as type drift (positive test)."""

    class RetypedLegalEntity(CanonicalEntity):
        entity_id: str = Field(description="...")
        entity_name: str = Field(description="...")
        entity_type: str = Field(description="...")
        lei: str | None = None
        domicile: str | None = None
        parent_entity_id: str | None = None
        known_aliases: list[str] = Field(default_factory=list)
        external_ids: dict[str, str] = Field(default_factory=dict)
        status: str = Field(description="...")
        # `first_seen_at` is `date` in the model file — realise it as int (drift).
        first_seen_at: int = Field(description="WRONG TYPE")

        ENTITY_ID = "E-01"
        MODEL_FILE = "model/entities/core/E-01-legal-entity.md"
        OWNERSHIP = OwnershipPattern.SINGLE
        PARTITION_KEY = None
        GRAIN = ()

    result = check_entity(RetypedLegalEntity, repo_root())
    assert not result.clean
    assert any("first_seen_at" in mm for mm in result.type_mismatches)


def test_drift_check_catches_a_stray_field() -> None:
    """A schema field not in the model file is reported as a rename/stray (positive test)."""

    class StrayFieldLegalEntity(CanonicalEntity):
        entity_id: str = Field(description="...")
        entity_name: str = Field(description="...")
        entity_type: str = Field(description="...")
        lei: str | None = None
        domicile: str | None = None
        parent_entity_id: str | None = None
        known_aliases: list[str] = Field(default_factory=list)
        external_ids: dict[str, str] = Field(default_factory=dict)
        status: str = Field(description="...")
        first_seen_at: date = Field(description="...")
        invented_column: str = Field(description="not in the model file")

        ENTITY_ID = "E-01"
        MODEL_FILE = "model/entities/core/E-01-legal-entity.md"
        OWNERSHIP = OwnershipPattern.SINGLE
        PARTITION_KEY = None
        GRAIN = ()

    result = check_entity(StrayFieldLegalEntity, repo_root())
    assert not result.clean
    assert "invented_column" in result.extra_in_schema


def test_drift_check_catches_a_decimal_to_float_pydantic_retype() -> None:
    """MONEY-CRITICAL: a model-`decimal` column realised as `float` is type drift.

    E-07's `value_usd` is `decimal` in the model file (exact money). Realise it as
    `float` (the fiduciary-worst silent retype) and the Pydantic-surface check must
    report a `type_mismatch`. Revert-sensitive: if `_TYPE_MAP` stopped keeping
    `decimal` and `float` disjoint, this would go green.
    """

    class FloatValuation(CanonicalEntity):
        valuation_id: str = Field(description="...")
        position_id: str = Field(description="...")
        instrument_id: str | None = None
        valuation_date: date = Field(description="...")
        # `value_usd` is `decimal` in the model file — realise it as float (DRIFT).
        value_usd: float = Field(description="WRONG: money as float")
        method: str = Field(description="...")
        valuation_level: str = Field(description="...")
        source: str = Field(description="...")
        confidence_score: float | None = None

        ENTITY_ID = "E-07"
        MODEL_FILE = "model/entities/core/E-07-valuation.md"
        OWNERSHIP = OwnershipPattern.KEY_PARTITIONED
        PARTITION_KEY = "method"
        GRAIN = ("valuation_date",)

    result = check_entity(FloatValuation, repo_root())
    assert not result.clean
    assert any("value_usd" in mm for mm in result.type_mismatches), result.type_mismatches


def test_pydantic_positive_control_decimal_stays_clean() -> None:
    """POSITIVE CONTROL: the real E-07 schema (decimal money, float confidence) is CLEAN.

    Proves the decimal->float test above fails on the DRIFT, not on the type-check
    itself: the faithful schema (value_usd Decimal, confidence_score float) passes.
    """
    result = check_entity(E07Valuation, repo_root())
    assert result.clean, f"type={result.type_mismatches}"
    # And E-04, whose money columns are all Decimal, is clean too.
    assert check_entity(E04HoldingPosition, repo_root()).clean


# ---------------------------------------------------------------------------
# The staging-SQL surface.
# ---------------------------------------------------------------------------


def test_staging_drift_check_clean_on_all_realised() -> None:
    """The committed staging models match their model files — zero drift.

    The real-surface proof across all thirteen realised entities (the original ten,
    E-05/E-06, and E-24): a green here means the check is CORRECT (it passes the
    faithful staging models AND surfaces the one legitimately-unstaged entity), not
    merely that synthetic drift trips it. E-24 Reconciliation Break is engine-owned
    (the break store is a separate duckdb file, NOT a dbt model), so it has no
    `stg_e24_*.sql` and is reported `no_staging_model` — a surfaced coverage gap that
    is `clean` (not a column/type drift) and does not fail the build.
    """
    results = run_staging_drift_check()
    assert len(results) == 13
    drifted = [r for r in results if not r.clean]
    assert not drifted, "\n".join(
        f"{r.entity_id} ({r.staging_file}): missing={r.missing_from_staging} "
        f"extra={r.extra_in_staging} type={r.type_mismatches}"
        for r in drifted
    )


def test_only_e24_is_legitimately_unstaged() -> None:
    """Every realised entity is staged EXCEPT E-24 — the one engine-owned entity.

    The staging layer carries one `stg_eNN_*.sql` per dbt-materialised realised entity:
    the original ten plus the substrate's stg_e05_transaction + stg_e06_cash_flow_event.
    E-24 Reconciliation Break is **engine-owned** — the reconciliation engine inserts
    breaks into a SEPARATE duckdb break store (so `dbt build` never writes or clobbers
    it), so E-24 has no staging model BY DESIGN. The drift check reports it
    `no_staging_model` (a surfaced gap, `clean=True`), which is the correct, honest
    state — not a drift. The no-staging-model code path is also exercised by
    `test_unstaged_entity_is_surfaced` with a synthetic entity.
    """
    results = run_staging_drift_check()
    unstaged = [r.entity_id for r in results if r.no_staging_model]
    assert unstaged == ["E-24"], f"unexpected unstaged set: {unstaged}"
    for r in results:
        if r.entity_id == "E-24":
            assert r.staging_file is None
            assert r.clean is True  # a surfaced coverage gap is not a column/type drift
        else:
            assert r.staging_file is not None


def test_staging_collection_columns_accept_varchar_carrier() -> None:
    """E-01 `known_aliases` (array) / `external_ids` (map) cast `as varchar` are CLEAN.

    The documented flat-text staging carrier (normalisation deferred to the
    staging/marts layer) is accepted by the compat rule — NOT a loosening of
    money/scalar checks. This is why the real surface is clean WITHOUT editing the SQL
    or the model file.
    """
    result = check_entity_staging(E01LegalEntity, repo_root())
    assert result.clean, f"type={result.type_mismatches}"


def _write_staging(tmp_path: Path, stem: str, projections: list[str]) -> Path:
    """Write a minimal synthetic `stg_*.sql` (CTE wrapper + select projection list)."""
    staging_dir = tmp_path / "reference" / "dbt" / "models" / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"    {p}," for p in projections)
    body = body.rstrip(",")  # drop the trailing comma on the last projection
    sql = (
        f"-- synthetic {stem}\n"
        "with source as (\n"
        "    select * from {{ ref('raw') }}\n"
        ")\n\n"
        "select\n"
        f"{body}\n"
        "from source\n"
    )
    path = staging_dir / f"{stem}.sql"
    path.write_text(sql, encoding="utf-8")
    return path


def test_parse_staging_projection_handles_the_type_shapes(tmp_path: Path) -> None:
    """The parser reads parenthesised, two-word and plain SQL types -> raw type strings."""
    path = _write_staging(
        tmp_path,
        "stg_parse_shapes",
        [
            "cast(src_money as decimal(18, 2))   as money",
            "cast(src_conf  as double precision) as conf",
            "cast(src_id    as varchar)          as id",
            "cast(src_d     as date)             as d",
            "cast(src_n     as integer)          as n",
            "cast(src_flag  as boolean)          as flag",
        ],
    )
    cols = parse_staging_projection(path)
    assert cols == {
        "money": "decimal",
        "conf": "double precision",
        "id": "varchar",
        "d": "date",
        "n": "integer",
        "flag": "boolean",
    }


def test_staging_parser_stop_and_surface_on_unreadable_projection(tmp_path: Path) -> None:
    """A non-`cast(... as ...) as col` projection raises (STOP-and-surface, no silent miss)."""
    path = _write_staging(
        tmp_path,
        "stg_e99_synthetic",
        ["cast(a as varchar) as a", "b + c as derived"],  # the 2nd is not a cast projection
    )
    with pytest.raises(StagingParseError):
        parse_staging_projection(path)


def _synthetic_entity(entity_id: str, model_file: str) -> type[CanonicalEntity]:
    """A bare entity carrying just the id + model-file link the staging check reads."""

    class _Synthetic(CanonicalEntity):
        ENTITY_ID = entity_id
        MODEL_FILE = model_file
        OWNERSHIP = OwnershipPattern.SINGLE
        PARTITION_KEY = None
        GRAIN = ()

    return _Synthetic


def _e07_staging_drift(tmp_path: Path, value_usd_cast: str) -> StagingDrift:
    """Cross-check a synthetic E-07 staging model (with a chosen `value_usd` cast).

    Uses the REAL E-07 model file (the SSOT) as the declared schema, and a synthetic
    staging model under a tmp repo root so we never touch the committed SQL.
    """
    real_root = repo_root()
    model_rel = "model/entities/core/E-07-valuation.md"
    # Mirror the real E-07 model file into the tmp root (read-only copy of the SSOT).
    model_src = (real_root / model_rel).read_text(encoding="utf-8")
    model_dst = tmp_path / model_rel
    model_dst.parent.mkdir(parents=True, exist_ok=True)
    model_dst.write_text(model_src, encoding="utf-8")
    _write_staging(
        tmp_path,
        "stg_e07_valuation",
        [
            "cast(valuation_id     as varchar)        as valuation_id",
            "cast(position_id      as varchar)        as position_id",
            "cast(instrument_id    as varchar)        as instrument_id",
            "cast(valuation_date   as date)           as valuation_date",
            f"cast(value_usd        as {value_usd_cast}) as value_usd",
            "cast(method           as varchar)        as method",
            "cast(valuation_level  as varchar)        as valuation_level",
            "cast(source           as varchar)        as source",
            "cast(confidence_score as double precision) as confidence_score",
        ],
    )
    cls = _synthetic_entity("E-07", model_rel)
    return check_entity_staging(cls, tmp_path)


def test_staging_catches_decimal_to_double_precision_retype(tmp_path: Path) -> None:
    """MONEY-CRITICAL: `value_usd` (model `decimal`) cast `as double precision` is type drift.

    The staging analogue of the Pydantic decimal->float test — the fiduciary-worst
    silent retype on the SQL surface. Revert-sensitive: loosen `_STAGING_TYPE_COMPAT`
    so `decimal` accepts `float` and this goes green.
    """
    result = _e07_staging_drift(tmp_path, "double precision")
    assert not result.clean
    assert any("value_usd" in mm for mm in result.type_mismatches), result.type_mismatches


def test_staging_positive_control_decimal_cast_is_clean(tmp_path: Path) -> None:
    """POSITIVE CONTROL: `value_usd` cast `as decimal(18, 2)` (a genuine money cast) is CLEAN.

    Proves the retype test above fails on the DRIFT, not on the cast machinery.
    `confidence_score as double precision` (a genuine model-`float`) is clean too —
    asserted implicitly (this whole staging model is clean).
    """
    result = _e07_staging_drift(tmp_path, "decimal(18, 2)")
    assert result.clean, f"type={result.type_mismatches}"


def test_staging_catches_a_dropped_column(tmp_path: Path) -> None:
    """A staging projection that omits a model-file column is reported (missing)."""
    real_root = repo_root()
    model_rel = "model/entities/core/E-07-valuation.md"
    model_dst = tmp_path / model_rel
    model_dst.parent.mkdir(parents=True, exist_ok=True)
    model_dst.write_text((real_root / model_rel).read_text(encoding="utf-8"), encoding="utf-8")
    _write_staging(
        tmp_path,
        "stg_e07_valuation",
        [
            "cast(valuation_id     as varchar)      as valuation_id",
            "cast(position_id      as varchar)      as position_id",
            "cast(instrument_id    as varchar)      as instrument_id",
            "cast(valuation_date   as date)         as valuation_date",
            "cast(value_usd        as decimal(18, 2)) as value_usd",
            # `method`, `valuation_level`, `source`, `confidence_score` dropped.
        ],
    )
    result = check_entity_staging(_synthetic_entity("E-07", model_rel), tmp_path)
    assert not result.clean
    assert "method" in result.missing_from_staging
    assert "confidence_score" in result.missing_from_staging


def test_staging_catches_an_extra_column(tmp_path: Path) -> None:
    """A staging projection with a column not in the model file is reported (stray)."""
    real_root = repo_root()
    model_rel = "model/entities/core/E-07-valuation.md"
    model_dst = tmp_path / model_rel
    model_dst.parent.mkdir(parents=True, exist_ok=True)
    model_dst.write_text((real_root / model_rel).read_text(encoding="utf-8"), encoding="utf-8")
    _write_staging(
        tmp_path,
        "stg_e07_valuation",
        [
            "cast(valuation_id     as varchar)        as valuation_id",
            "cast(position_id      as varchar)        as position_id",
            "cast(instrument_id    as varchar)        as instrument_id",
            "cast(valuation_date   as date)           as valuation_date",
            "cast(value_usd        as decimal(18, 2)) as value_usd",
            "cast(method           as varchar)        as method",
            "cast(valuation_level  as varchar)        as valuation_level",
            "cast(source           as varchar)        as source",
            "cast(confidence_score as double precision) as confidence_score",
            "cast(invented         as varchar)        as invented_column",  # not in model file
        ],
    )
    result = check_entity_staging(_synthetic_entity("E-07", model_rel), tmp_path)
    assert not result.clean
    assert "invented_column" in result.extra_in_staging


def test_staging_catches_a_renamed_column(tmp_path: Path) -> None:
    """A renamed staging column surfaces as both a missing (model) and an extra (staging)."""
    real_root = repo_root()
    model_rel = "model/entities/core/E-07-valuation.md"
    model_dst = tmp_path / model_rel
    model_dst.parent.mkdir(parents=True, exist_ok=True)
    model_dst.write_text((real_root / model_rel).read_text(encoding="utf-8"), encoding="utf-8")
    _write_staging(
        tmp_path,
        "stg_e07_valuation",
        [
            "cast(valuation_id     as varchar)        as valuation_id",
            "cast(position_id      as varchar)        as position_id",
            "cast(instrument_id    as varchar)        as instrument_id",
            "cast(valuation_date   as date)           as valuation_date",
            "cast(value_usd        as decimal(18, 2)) as value_amount",  # renamed value_usd
            "cast(method           as varchar)        as method",
            "cast(valuation_level  as varchar)        as valuation_level",
            "cast(source           as varchar)        as source",
            "cast(confidence_score as double precision) as confidence_score",
        ],
    )
    result = check_entity_staging(_synthetic_entity("E-07", model_rel), tmp_path)
    assert not result.clean
    assert "value_usd" in result.missing_from_staging
    assert "value_amount" in result.extra_in_staging


def test_unstaged_entity_is_surfaced(tmp_path: Path) -> None:
    """An entity with a model file but no `stg_` model is surfaced, not crashed-on.

    Exercises the no-staging-model path: a synthetic E-98 with a model file copied
    into the tmp root but NO staging model -> `no_staging_model` True, `clean` True
    (a surfaced gap is not a column/type drift), `staging_file` None.
    """
    model_rel = "model/entities/core/E-98-unstaged.md"
    model_dst = tmp_path / model_rel
    model_dst.parent.mkdir(parents=True, exist_ok=True)
    model_dst.write_text(
        "# E-98 Unstaged\n\n"
        "## Attribute schema\n\n"
        "| Column | Type | Definition |\n"
        "|---|---|---|\n"
        "| `x_id` | varchar | id |\n",
        encoding="utf-8",
    )
    # No stg_e98_*.sql written.
    (tmp_path / "reference" / "dbt" / "models" / "staging").mkdir(parents=True, exist_ok=True)
    result = check_entity_staging(_synthetic_entity("E-98", model_rel), tmp_path)
    assert result.no_staging_model is True
    assert result.staging_file is None
    assert result.clean is True  # a coverage gap is not a drift
    assert staging_path_for(_synthetic_entity("E-98", model_rel), tmp_path) is None
