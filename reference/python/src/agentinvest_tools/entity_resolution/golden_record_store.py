"""The append-only golden-record store — engine-owned, insert-only, immutable.

The canonical golden record for every cluster the deterministic cascade resolved (Tier-1 / Tier-2).
Keyed by the OpenIM-internal ``entity_id`` (E-01's golden-key discipline — NEVER an external id),
carrying the survived canonical fields (name / lei / domicile) + per-field provenance (which source
won each field, serialised as JSON). This is the resolution capability's of-record output.

This store is the ``break_store.py`` pattern VERBATIM (the append-only discipline):

- persists each golden record as an immutable event at ``status = resolved`` — the resolved state.
  Each row: ``golden_id`` (run-scoped, deterministic), the internal ``entity_id``, the survived
  fields, the contributing source_record_ids (comma-joined), the per-field provenance JSON,
  ``status``;
- is **insert-only** — there is NO update method, NO ``status``-transition method, NO delete. A
  re-resolution producing a refined golden record is a NEW append; this store never
  mutates an existing row. The API surface is ``append_golden_records`` + ``read_golden_records`` +
  ``count_golden_records`` only;
- is **ENGINE-OWNED and SEPARATE from the dbt canonical store** — its OWN duckdb file
  (``AGENTINVEST_GOLDEN_RECORD_STORE_PATH`` override, else a checkout-keyed default DISTINCT from
  the canonical / break / proposal / review stores), so ``dbt build`` never writes or clobbers it
  (idempotency preserved). Not a dbt model; gitignored.

THE GOLDEN KEY IS NEVER AN EXTERNAL ID. ``entity_id`` is the internal golden key (E-01's
discipline);
the LEI is a SURVIVED ATTRIBUTE, never the key. A net-new entity is NOT written here — it
goes through the steward flow first (a net-new golden key is a curated decision); this store holds
only the records that resolved to an EXISTING master's golden key, so it never invents a key.

THE IMMUTABILITY IS STRUCTURAL, NOT ADVISORY. The only write path is an INSERT (``insert ... on
conflict do nothing``). No UPDATE / DELETE / ALTER / DROP SQL exists in this module — proven by the
absence of a mutation path AND by an AST scan of the executed SQL
(``test_entity_resolution_stores``).

SYNTHETIC, FINDINGS-ONLY. The golden records are over a synthetic resolution oracle —
never a production resolution.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

_GOLDEN_TABLE = "resolution_golden_record"
_GOLDEN_SCHEMA = "main"


class GoldenRecordStoreUnavailableError(RuntimeError):
    """The engine-owned golden-record store cannot be opened — duckdb missing, or an open
    failure."""


@dataclass(frozen=True)
class GoldenRecordRow:
    """The of-record golden record to append — keyed by the INTERNAL entity_id (never external)."""

    entity_id: str
    entity_name: str | None
    lei: str | None
    domicile: str | None
    source_record_ids: tuple[str, ...]
    provenance_json: str  # JSON: [{field, value, source_record_id, source_system}, ...]


@dataclass(frozen=True)
class StoredGoldenRecord:
    """One persisted golden-record event read back — the immutable record."""

    golden_id: str
    entity_id: str
    entity_name: str | None
    lei: str | None
    domicile: str | None
    source_record_ids: tuple[str, ...]
    provenance_json: str
    status: str


def _repo_root_token(repo_root: Path) -> str:
    """The checkout-keyed token — sha256 prefix of the repo-root path (the break-store rule)."""
    return hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:12]


def resolve_golden_store_path() -> Path:
    """Resolve the engine-owned golden-record duckdb path — the env override, else a keyed default.

    ``AGENTINVEST_GOLDEN_RECORD_STORE_PATH`` wins; otherwise a checkout-keyed default
    (``resolution-golden-<token>.duckdb``) DISTINCT from the canonical / break / proposal / review
    stores so ``dbt build`` never touches it. Never hard-coded.
    """
    override = os.environ.get("AGENTINVEST_GOLDEN_RECORD_STORE_PATH")
    if override:
        return Path(override)
    repo_root = Path(__file__).resolve().parents[5]
    parent = os.environ.get("AGENTINVEST_VENV_PARENT")
    base = Path(parent) if parent else Path.home() / ".local" / "share" / "agentinvest"
    return base / "duckdb" / f"resolution-golden-{_repo_root_token(repo_root)}.duckdb"


def _connect(path: Path, read_only: bool):  # type: ignore[no-untyped-def]
    """Open the golden store (creating file + table on a read-write open), or raise. duckdb is
    lazy."""
    try:
        import duckdb  # noqa: PLC0415 - lazy: the data toolchain is an optional layer
    except ImportError as exc:  # pragma: no cover
        raise GoldenRecordStoreUnavailableError(
            "the 'duckdb' package is not installed — install the data toolchain "
            "(uv sync --group dbt) to use the golden-record store"
        ) from exc

    if read_only and not path.exists():
        raise GoldenRecordStoreUnavailableError(
            f"the golden-record store does not exist at {path} — nothing has been appended yet"
        )
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        con = duckdb.connect(str(path), read_only=read_only)
    except Exception as exc:  # pragma: no cover
        raise GoldenRecordStoreUnavailableError(
            f"could not open the golden-record store at {path}: {exc}"
        ) from exc
    if not read_only:
        _ensure_table(con)
    return con


def _ensure_table(con) -> None:  # type: ignore[no-untyped-def]
    """Create the append-only golden table if absent — the ONLY DDL. INSERT is the only write
    path."""
    con.execute(
        f"""
        create table if not exists {_GOLDEN_SCHEMA}.{_GOLDEN_TABLE} (
            golden_id          varchar primary key,
            entity_id          varchar,
            entity_name        varchar,
            lei                varchar,
            domicile           varchar,
            source_record_ids  varchar,
            provenance_json    varchar,
            status             varchar
        )
        """
    )


def _golden_id(run_id: str, seq: int) -> str:
    """A deterministic, run-scoped golden id — ``GR-<run_id>-<seq>`` (idempotent re-append)."""
    return f"GR-{run_id}-{seq:04d}"


def append_golden_records(
    records: list[GoldenRecordRow],
    run_id: str,
    store_path: Path | None = None,
) -> list[str]:
    """Append golden records as immutable ``status = resolved`` events — INSERT-ONLY.

    Each record is persisted at ``status = resolved``, keyed by the internal ``entity_id`` (the LEI
    is a survived attribute, never the key). The golden id is deterministic + run-scoped, so
    re-appending the SAME run is idempotent (the PK rejects the dup). There is NO update path: a
    golden record, once appended, is never modified (a refined re-resolution is a new append).
    Returns the appended ids.
    """
    path = store_path or resolve_golden_store_path()
    con = _connect(path, read_only=False)
    appended: list[str] = []
    try:
        for seq, rec in enumerate(records):
            gid = _golden_id(run_id, seq)
            con.execute(
                f"""
                insert into {_GOLDEN_SCHEMA}.{_GOLDEN_TABLE} (
                    golden_id, entity_id, entity_name, lei, domicile,
                    source_record_ids, provenance_json, status
                )
                values (?, ?, ?, ?, ?, ?, ?, 'resolved')
                on conflict (golden_id) do nothing
                """,
                [
                    gid,
                    rec.entity_id,
                    rec.entity_name,
                    rec.lei,
                    rec.domicile,
                    ",".join(rec.source_record_ids),
                    rec.provenance_json,
                ],
            )
            appended.append(gid)
    finally:
        con.close()
    return appended


def read_golden_records(store_path: Path | None = None) -> list[StoredGoldenRecord]:
    """Read all golden records back, ordered by golden_id — READ-ONLY (no mutation path)."""
    path = store_path or resolve_golden_store_path()
    con = _connect(path, read_only=True)
    try:
        rows = con.execute(
            f"""
            select golden_id, entity_id, entity_name, lei, domicile,
                source_record_ids, provenance_json, status
            from {_GOLDEN_SCHEMA}.{_GOLDEN_TABLE}
            order by golden_id
            """
        ).fetchall()
    finally:
        con.close()
    out: list[StoredGoldenRecord] = []
    for r in rows:
        src = str(r[5])
        out.append(
            StoredGoldenRecord(
                golden_id=str(r[0]),
                entity_id=str(r[1]),
                entity_name=None if r[2] is None else str(r[2]),
                lei=None if r[3] is None else str(r[3]),
                domicile=None if r[4] is None else str(r[4]),
                source_record_ids=tuple(s for s in src.split(",") if s),
                provenance_json=str(r[6]),
                status=str(r[7]),
            )
        )
    return out


def count_golden_records(store_path: Path | None = None) -> int:
    """Count the golden records — READ-ONLY. Zero (not an error) when the store is absent."""
    path = store_path or resolve_golden_store_path()
    if not path.exists():
        return 0
    con = _connect(path, read_only=True)
    try:
        row = con.execute(f"select count(*) from {_GOLDEN_SCHEMA}.{_GOLDEN_TABLE}").fetchone()
    finally:
        con.close()
    return int(row[0]) if row else 0


def provenance_to_json(provenance: object) -> str:
    """Serialise the cascade's per-field provenance tuple to JSON for the store column.

    Accepts a sequence of objects exposing ``field_name`` / ``value`` / ``source_record_id`` /
    ``source_system`` (the cascade's ``GoldenFieldProvenance``); returns a compact JSON array.
    """
    items = []
    for p in provenance:  # type: ignore[attr-defined]
        items.append(
            {
                "field": getattr(p, "field_name", ""),
                "value": getattr(p, "value", None),
                "source_record_id": getattr(p, "source_record_id", ""),
                "source_system": getattr(p, "source_system", ""),
            }
        )
    return json.dumps(items)
