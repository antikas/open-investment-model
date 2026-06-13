"""The append-only steward-review-queue store — engine-owned, insert-only, immutable (OIM-199).

Where resolution honesty lives. Every feed record the deterministic cascade CANNOT resolve to
exactly one master at or above the Tier-2 threshold — a genuinely-ambiguous name-key collision, a
conflicting-domicile match, a within-batch net-new collision — lands here as an immutable
``status = in_review`` event, for a human steward to adjudicate. It is NEVER auto-merged: a
quarantine is the correct outcome where the evidence is genuinely insufficient, and forcing it would
be the cardinal mis-merge that silently corrupts the golden master.

This store is the ``break_store.py`` pattern VERBATIM (the OIM-162 append-only discipline):

- persists each quarantined record as an immutable event at ``status = in_review`` — the
  awaiting-steward state. Each row: ``queue_id``, the source record ref, the cascade tier that
  routed it (always ``tier_3_review``), the explainable signal, the as-of run, ``status``;
- is **insert-only** — there is NO update method, NO ``status``-transition method, NO delete. A
  steward's confirmation (``in_review`` -> resolved, the alias write-back to E-13) is a later cycle,
  human-gated; none exists here. The API surface is ``append_review_items`` + ``read_review_items``
  + ``count_review_items`` only;
- is **ENGINE-OWNED and SEPARATE from the dbt canonical store** — its OWN duckdb file
  (``AGENTINVEST_RESOLUTION_REVIEW_STORE_PATH`` override, else a checkout-keyed default DISTINCT
  from the canonical / break / proposal / golden stores), so ``dbt build`` never writes or clobbers
  it
  (idempotency preserved). Not a dbt model; gitignored.

THE IMMUTABILITY IS STRUCTURAL, NOT ADVISORY. The table is created with the queue schema; the only
write path is an INSERT (``insert ... on conflict do nothing``). There is no UPDATE / DELETE / ALTER
/ DROP SQL in this module — the append-only property is proven by the absence of a mutation path AND
by an AST scan of the executed SQL (``test_entity_resolution_stores``).

SYNTHETIC, FINDINGS-ONLY. The quarantined records are over the OIM-199 synthetic resolution oracle —
never a production resolution, never a steward-confirmed merge.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

_REVIEW_TABLE = "resolution_review_queue"
_REVIEW_SCHEMA = "main"


class ResolutionReviewStoreUnavailableError(RuntimeError):
    """The engine-owned review-queue store cannot be opened — duckdb missing, or an open failure."""


@dataclass(frozen=True)
class ReviewItem:
    """One quarantined feed record awaiting steward adjudication — the cascade input to append."""

    source_record_id: str
    source_system: str
    raw_name: str
    raw_domicile: str | None
    tier: str
    signal: str
    as_of_date: str


@dataclass(frozen=True)
class StoredReviewItem:
    """One persisted review-queue event read back — the immutable record."""

    queue_id: str
    source_record_id: str
    source_system: str
    raw_name: str
    raw_domicile: str | None
    tier: str
    signal: str
    as_of_date: str
    status: str


def _repo_root_token(repo_root: Path) -> str:
    """The checkout-keyed token — sha256 prefix of the repo-root path (the break-store rule)."""
    return hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:12]


def resolve_review_store_path() -> Path:
    """Resolve the engine-owned review-queue duckdb path — the env override, else a keyed default.

    ``AGENTINVEST_RESOLUTION_REVIEW_STORE_PATH`` wins; otherwise a checkout-keyed default
    (``resolution-review-<token>.duckdb``) DISTINCT from the canonical / break / proposal / golden
    stores so ``dbt build`` never touches it. Never hard-coded.
    """
    override = os.environ.get("AGENTINVEST_RESOLUTION_REVIEW_STORE_PATH")
    if override:
        return Path(override)
    repo_root = Path(__file__).resolve().parents[5]
    parent = os.environ.get("AGENTINVEST_VENV_PARENT")
    base = Path(parent) if parent else Path.home() / ".local" / "share" / "agentinvest"
    return base / "duckdb" / f"resolution-review-{_repo_root_token(repo_root)}.duckdb"


def _connect(path: Path, read_only: bool):  # type: ignore[no-untyped-def]
    """Open the review store (creating file + table on a read-write open), or raise. duckdb is
    lazy."""
    try:
        import duckdb  # noqa: PLC0415 - lazy: the data toolchain is an optional layer
    except ImportError as exc:  # pragma: no cover
        raise ResolutionReviewStoreUnavailableError(
            "the 'duckdb' package is not installed — install the data toolchain "
            "(uv sync --group dbt) to use the review-queue store"
        ) from exc

    if read_only and not path.exists():
        raise ResolutionReviewStoreUnavailableError(
            f"the review-queue store does not exist at {path} — nothing has been appended yet"
        )
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        con = duckdb.connect(str(path), read_only=read_only)
    except Exception as exc:  # pragma: no cover
        raise ResolutionReviewStoreUnavailableError(
            f"could not open the review-queue store at {path}: {exc}"
        ) from exc
    if not read_only:
        _ensure_table(con)
    return con


def _ensure_table(con) -> None:  # type: ignore[no-untyped-def]
    """Create the append-only review table if absent — the ONLY DDL. INSERT is the only write
    path."""
    con.execute(
        f"""
        create table if not exists {_REVIEW_SCHEMA}.{_REVIEW_TABLE} (
            queue_id          varchar primary key,
            source_record_id  varchar,
            source_system     varchar,
            raw_name          varchar,
            raw_domicile      varchar,
            tier              varchar,
            signal            varchar,
            as_of_date        varchar,
            status            varchar
        )
        """
    )


def _queue_id(run_id: str, seq: int) -> str:
    """A deterministic, run-scoped queue id — ``RQ-<run_id>-<seq>`` (idempotent re-append)."""
    return f"RQ-{run_id}-{seq:04d}"


def append_review_items(
    items: list[ReviewItem],
    run_id: str,
    store_path: Path | None = None,
) -> list[str]:
    """Append quarantined records as immutable ``status = in_review`` events — INSERT-ONLY.

    Each item is persisted at ``status = in_review`` (the awaiting-steward state). The queue id is
    deterministic + run-scoped, so re-appending the SAME run is idempotent (the PK rejects the dup).
    There is NO update path: a quarantined record, once appended, is never modified. The steward
    confirmation / alias write-back is a later, human-gated cycle. Returns the appended ids.
    """
    path = store_path or resolve_review_store_path()
    con = _connect(path, read_only=False)
    appended: list[str] = []
    try:
        for seq, it in enumerate(items):
            qid = _queue_id(run_id, seq)
            con.execute(
                f"""
                insert into {_REVIEW_SCHEMA}.{_REVIEW_TABLE} (
                    queue_id, source_record_id, source_system, raw_name, raw_domicile,
                    tier, signal, as_of_date, status
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, 'in_review')
                on conflict (queue_id) do nothing
                """,
                [
                    qid,
                    it.source_record_id,
                    it.source_system,
                    it.raw_name,
                    it.raw_domicile,
                    it.tier,
                    it.signal,
                    it.as_of_date,
                ],
            )
            appended.append(qid)
    finally:
        con.close()
    return appended


def read_review_items(store_path: Path | None = None) -> list[StoredReviewItem]:
    """Read all quarantined records back, ordered by queue_id — READ-ONLY (no mutation path)."""
    path = store_path or resolve_review_store_path()
    con = _connect(path, read_only=True)
    try:
        rows = con.execute(
            f"""
            select queue_id, source_record_id, source_system, raw_name, raw_domicile,
                tier, signal, as_of_date, status
            from {_REVIEW_SCHEMA}.{_REVIEW_TABLE}
            order by queue_id
            """
        ).fetchall()
    finally:
        con.close()
    return [
        StoredReviewItem(
            queue_id=str(r[0]),
            source_record_id=str(r[1]),
            source_system=str(r[2]),
            raw_name=str(r[3]),
            raw_domicile=None if r[4] is None else str(r[4]),
            tier=str(r[5]),
            signal=str(r[6]),
            as_of_date=str(r[7]),
            status=str(r[8]),
        )
        for r in rows
    ]


def count_review_items(store_path: Path | None = None) -> int:
    """Count the quarantined records — READ-ONLY. Zero (not an error) when the store is absent."""
    path = store_path or resolve_review_store_path()
    if not path.exists():
        return 0
    con = _connect(path, read_only=True)
    try:
        row = con.execute(f"select count(*) from {_REVIEW_SCHEMA}.{_REVIEW_TABLE}").fetchone()
    finally:
        con.close()
    return int(row[0]) if row else 0
