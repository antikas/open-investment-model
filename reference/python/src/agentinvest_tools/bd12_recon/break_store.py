"""The append-only E-24 break store — engine-owned, insert-only, immutable (OIM-162 cycle-1).

The first persisted WRITE in agentINVEST — but it is an **append-only, insert-only, immutable
break-event store** (Kleppmann/Helland log-append: "accountants don't use erasers"), NOT a
state-mutation of a book of record. Appending a *finding* is not mutating the *book*. This store:

- persists each E-24 break finding as an immutable event at ``status = open``, ``identified_date =
  as_of``, ``age_days = 0`` — the freshly-identified state;
- is **insert-only** — there is NO update method, NO ``status``-transition method, NO
correcting-entry
  write, NO delete. The break-lifecycle update (``open`` → ``investigated`` → ``resolved``), the
  correcting entry back to ABOR, and the breach gate are all **OIM-163** (the first state-mutation,
  strictly gated) — none exists here. The API surface is ``append_breaks`` + ``read_breaks`` +
  ``count_breaks`` only;
- is **ENGINE-OWNED and SEPARATE from the dbt canonical store** — it lives in its OWN duckdb file
  (resolved from ``AGENTINVEST_RECON_STORE_PATH``, else a checkout-keyed default beside, but
  DISTINCT from, the canonical store), so ``dbt build`` neither writes nor clobbers it (``dbt
  build`` idempotency is preserved — the break store is invisible to dbt). The store is NOT a dbt
  model and is gitignored.

THE IMMUTABILITY IS STRUCTURAL, NOT ADVISORY. The table is created with the E-24 schema; the only
write path is an INSERT. There is no UPDATE / DELETE code in this module — the append-only property
is proven by the absence of a mutation path AND asserted in the tests (no update / no status
transition / no correcting-entry / no book-mutation method exists).

SYNTHETIC, FINDINGS-ONLY. The breaks persisted are findings over the OIM-160 synthetic data — never
a production reconciliation, never a resolved/gated break.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from agentinvest_tools.bd12_recon.break_finding import BreakFinding

# The break-store table — the E-24 attribute schema, at the freshly-identified (status=open) grain.
_BREAK_TABLE = "recon_break"
_BREAK_SCHEMA = "main"


class BreakStoreUnavailableError(RuntimeError):
    """The engine-owned break store cannot be opened — duckdb missing, or a genuine open failure.

    Distinct from ``MartsUnavailableError`` (the canonical store): the break store is a SEPARATE
    engine-owned file, so its availability is its own concern. The message is actionable.
    """


@dataclass(frozen=True)
class StoredBreak:
    """One persisted E-24 break event read back from the store — the immutable record."""

    break_id: str
    reconciliation_type: str
    record_a_ref: str
    record_b_ref: str
    as_of_date: date
    identified_date: date
    difference_amount: Decimal | None
    difference_qty: Decimal | None
    cause_classification: str
    materiality: str
    age_days: int
    status: str


def _repo_root_token(repo_root: Path) -> str:
    """The checkout-keyed token — sha256 prefix of the repo-root path (the marts.py convention)."""
    return hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:12]


def resolve_break_store_path() -> Path:
    """Resolve the engine-owned break-store duckdb path — the env override, else a keyed default.

    ``AGENTINVEST_RECON_STORE_PATH`` (a launcher / CI / test override) wins; otherwise a
    checkout-keyed default under the same ext4 parent the canonical store uses, but a DISTINCT file
    (``recon-store-<token>.duckdb``) so it never collides with ``canonical-<token>.duckdb`` and
    ``dbt build`` never touches it. Never hard-coded.
    """
    override = os.environ.get("AGENTINVEST_RECON_STORE_PATH")
    if override:
        return Path(override)
    repo_root = Path(__file__).resolve().parents[5]
    parent = os.environ.get("AGENTINVEST_VENV_PARENT")
    base = Path(parent) if parent else Path.home() / ".local" / "share" / "agentinvest"
    return base / "duckdb" / f"recon-store-{_repo_root_token(repo_root)}.duckdb"


def _connect(path: Path, read_only: bool):  # type: ignore[no-untyped-def]
    """Open the break store (creating the file + table on a read-write open), or raise.

    duckdb is imported lazily so this module imports without the data toolchain. A read-write open
    ensures the table exists (the append path creates it on first use); a read-only open requires
    the
    file to exist already.
    """
    try:
        import duckdb  # noqa: PLC0415 - lazy: the data toolchain is an optional layer
    except ImportError as exc:  # pragma: no cover
        raise BreakStoreUnavailableError(
            "the 'duckdb' package is not installed — install the data toolchain "
            "(uv sync --group dbt) to use the break store"
        ) from exc

    if read_only and not path.exists():
        raise BreakStoreUnavailableError(
            f"the break store does not exist at {path} — no breaks have been appended yet"
        )
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        con = duckdb.connect(str(path), read_only=read_only)
    except Exception as exc:  # pragma: no cover
        raise BreakStoreUnavailableError(
            f"could not open the break store at {path}: {exc}"
        ) from exc
    if not read_only:
        _ensure_table(con)
    return con


def _ensure_table(con) -> None:  # type: ignore[no-untyped-def]
    """Create the append-only break table if absent — the E-24 schema, at the status=open grain.

    The ONLY DDL in this module. No ALTER, no migration — the table is created once and only ever
    INSERTed into. The append-only/immutable property is realised by there being no other write
    path.
    """
    con.execute(
        f"""
        create table if not exists {_BREAK_SCHEMA}.{_BREAK_TABLE} (
            break_id             varchar primary key,
            reconciliation_type  varchar,
            record_a_ref         varchar,
            record_b_ref         varchar,
            as_of_date           date,
            identified_date      date,
            difference_amount    decimal(28, 8),
            difference_qty       decimal(28, 8),
            cause_classification varchar,
            materiality          varchar,
            age_days             integer,
            status               varchar
        )
        """
    )


def _break_id(finding: BreakFinding, run_id: str, seq: int) -> str:
    """A deterministic, run-scoped break id — stable for the same finding in the same run.

    ``BRK-<run_id>-<seq>``: the run id scopes a reconcile run; the sequence orders within it. A
    deterministic id means an idempotent re-append of the SAME run does not double-insert (the
    primary key rejects the duplicate), which keeps the store insert-only-and-idempotent.
    """
    return f"BRK-{run_id}-{seq:04d}"


def append_breaks(
    findings: list[BreakFinding],
    run_id: str,
    store_path: Path | None = None,
) -> list[str]:
    """Append break findings to the store as immutable ``status = open`` events — INSERT-ONLY.

    Each finding is persisted at ``status = open``, ``identified_date = as_of_date``, ``age_days =
    0`` (the freshly-identified state). The break id is deterministic + run-scoped, so re-appending
    the SAME run is idempotent (the primary key rejects a duplicate — no double-insert, no
    mutation).
    There is NO update path: a break, once appended, is never modified (the immutable-as-event
    property). Returns the appended break ids (in finding order).

    The ``status`` transition / resolution / correcting-entry are OIM-163 (behind the breach gate) —
    this method writes a NEW open break only; it never updates an existing one.
    """
    path = store_path or resolve_break_store_path()
    con = _connect(path, read_only=False)
    appended: list[str] = []
    try:
        for seq, f in enumerate(findings):
            bid = _break_id(f, run_id, seq)
            # INSERT OR IGNORE: a re-append of the same run is idempotent (the PK rejects the dup),
            # never an UPDATE. This is the ONLY write — insert-only, immutable.
            con.execute(
                f"""
                insert into {_BREAK_SCHEMA}.{_BREAK_TABLE} (
                    break_id, reconciliation_type, record_a_ref, record_b_ref, as_of_date,
                    identified_date, difference_amount, difference_qty, cause_classification,
                    materiality, age_days, status
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'open')
                on conflict (break_id) do nothing
                """,
                [
                    bid,
                    f.reconciliation_type,
                    f.record_a_ref,
                    f.record_b_ref,
                    f.as_of_date,
                    f.as_of_date,  # identified_date = as_of (freshly identified)
                    f.difference_amount,
                    f.difference_qty,
                    f.cause_classification,
                    f.materiality,
                ],
            )
            appended.append(bid)
    finally:
        con.close()
    return appended


def read_breaks(store_path: Path | None = None) -> list[StoredBreak]:
    """Read all persisted breaks back, ordered by break_id — READ-ONLY (no mutation path)."""
    path = store_path or resolve_break_store_path()
    con = _connect(path, read_only=True)
    try:
        rows = con.execute(
            f"""
            select break_id, reconciliation_type, record_a_ref, record_b_ref, as_of_date,
                identified_date, difference_amount, difference_qty, cause_classification,
                materiality, age_days, status
            from {_BREAK_SCHEMA}.{_BREAK_TABLE}
            order by break_id
            """
        ).fetchall()
    finally:
        con.close()
    return [
        StoredBreak(
            break_id=str(r[0]),
            reconciliation_type=str(r[1]),
            record_a_ref=str(r[2]),
            record_b_ref=str(r[3]),
            as_of_date=r[4],
            identified_date=r[5],
            difference_amount=None if r[6] is None else Decimal(str(r[6])),
            difference_qty=None if r[7] is None else Decimal(str(r[7])),
            cause_classification=str(r[8]),
            materiality=str(r[9]),
            age_days=int(r[10]),
            status=str(r[11]),
        )
        for r in rows
    ]


def count_breaks(store_path: Path | None = None) -> int:
    """Count the persisted breaks — READ-ONLY. Zero (not an error) when the store is empty/gone."""
    path = store_path or resolve_break_store_path()
    if not path.exists():
        return 0
    con = _connect(path, read_only=True)
    try:
        row = con.execute(f"select count(*) from {_BREAK_SCHEMA}.{_BREAK_TABLE}").fetchone()
    finally:
        con.close()
    return int(row[0]) if row else 0
