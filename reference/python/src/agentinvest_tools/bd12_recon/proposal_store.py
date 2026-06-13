"""The append-only LLM-proposal store — engine-owned, insert-only, immutable.

The propose-only LLM's ENTIRE writable universe (the deterministic spine). The LLM classifier
(``proposer.py``) never writes the of-record cause — it PROPOSES, and every proposal is captured
here as an immutable append-only event (the experience-flywheel CAPTURE stage: nothing is
fire-and-forget). This store is the second engine-owned append-only table, the ``break_store.py``
pattern verbatim:

- persists each proposal as an immutable event at ``status = proposed`` — the captured-but-not-acted
  state. Every LLM call lands one row: ``break_id``, model id, evidence-snapshot ref, prompt hash,
  proposed cause, rationale, confidence, timestamp, ``status = proposed``;
- is **insert-only** — there is NO update method, NO ``status``-transition method, NO delete. A
  proposal, once captured, is never modified. The API surface is ``append_proposals`` +
  ``read_proposals`` + ``count_proposals`` only. (A proposal is PROMOTED into a deterministic rule
  by
  a HUMAN-GATED CODE CHANGE — never a runtime ``status`` flip here; this
  store has no promote path, by construction.)
- is **ENGINE-OWNED and SEPARATE from the dbt canonical store AND from the break store** — its OWN
  duckdb file (``AGENTINVEST_PROPOSAL_STORE_PATH`` override, else a checkout-keyed default DISTINCT
  from both ``canonical-<token>.duckdb`` and ``recon-store-<token>.duckdb``), so ``dbt build`` never
  writes or clobbers it (idempotency preserved) and the of-record break store is untouched. Not a
  dbt
  model; gitignored.

THE IMMUTABILITY IS STRUCTURAL, NOT ADVISORY. The table is created with the proposal schema; the
only
write path is an INSERT (``insert … on conflict do nothing``). There is no UPDATE / DELETE / ALTER /
DROP SQL in this module — the append-only property is proven by the absence of a mutation path AND
by
an AST scan of the executed SQL (``test_bd12_recon_proposal_store``).

THE LLM CANNOT WRITE OF-RECORD (the architecture invariant). This store holds PROPOSALS at
``status = proposed``; it is NOT the break store, NOT the canonical layer, NOT any state the system
acts on. The of-record reconciliation cause lives in the break store (``break_store.py``), which the
proposer never writes. The spine holds: the LLM's only persisted output is an annotation here.

SYNTHETIC, FINDINGS-ONLY. The proposals are over the synthetic ``unexplained`` residue —
never a production reconciliation, never an acted-on classification.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from agentinvest_tools.bd12_recon.proposer import CauseProposal

# The proposals table — the captured-LLM-proposal schema, at the status=proposed grain.
_PROPOSAL_TABLE = "recon_cause_proposal"
_PROPOSAL_SCHEMA = "main"


class ProposalStoreUnavailableError(RuntimeError):
    """The engine-owned proposal store cannot be opened — duckdb missing, or a genuine open failure.

    Distinct from ``BreakStoreUnavailableError`` (the of-record break store) and
    ``MartsUnavailableError`` (the canonical store): the proposal store is a SEPARATE engine-owned
    file, so its availability is its own concern. The message is actionable.
    """


@dataclass(frozen=True)
class StoredProposal:
    """One captured proposal read back from the store — the immutable record."""

    proposal_id: str
    break_id: str
    reconciliation_type: str
    record_a_ref: str
    model_id: str
    snapshot_ref: str
    prompt_hash: str
    proposed_cause: str
    confidence: Decimal | None
    rationale: str
    of_record_cause: str
    created_at: str
    status: str


def _repo_root_token(repo_root: Path) -> str:
    """The checkout-keyed token — sha256 prefix of the repo-root path (the break-store rule)."""
    return hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:12]


def resolve_proposal_store_path() -> Path:
    """Resolve the engine-owned proposal-store duckdb path — the env override, else a keyed default.

    ``AGENTINVEST_PROPOSAL_STORE_PATH`` (a launcher / CI / test override) wins; otherwise a
    checkout-keyed default under the same ext4 parent the other stores use, but a DISTINCT file
    (``proposal-store-<token>.duckdb``) so it never collides with ``canonical-<token>.duckdb`` or
    ``recon-store-<token>.duckdb`` and ``dbt build`` never touches it. Never hard-coded.
    """
    override = os.environ.get("AGENTINVEST_PROPOSAL_STORE_PATH")
    if override:
        return Path(override)
    repo_root = Path(__file__).resolve().parents[5]
    parent = os.environ.get("AGENTINVEST_VENV_PARENT")
    base = Path(parent) if parent else Path.home() / ".local" / "share" / "agentinvest"
    return base / "duckdb" / f"proposal-store-{_repo_root_token(repo_root)}.duckdb"


def _connect(path: Path, read_only: bool):  # type: ignore[no-untyped-def]
    """Open the proposal store (creating the file + table on a read-write open), or raise.

    duckdb is imported lazily so this module imports without the data toolchain. A read-write open
    ensures the table exists (the append path creates it on first use); a read-only open requires
    the
    file to exist already.
    """
    try:
        import duckdb  # noqa: PLC0415 - lazy: the data toolchain is an optional layer
    except ImportError as exc:  # pragma: no cover
        raise ProposalStoreUnavailableError(
            "the 'duckdb' package is not installed — install the data toolchain "
            "(uv sync --group dbt) to use the proposal store"
        ) from exc

    if read_only and not path.exists():
        raise ProposalStoreUnavailableError(
            f"the proposal store does not exist at {path} — no proposals have been appended yet"
        )
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        con = duckdb.connect(str(path), read_only=read_only)
    except Exception as exc:  # pragma: no cover
        raise ProposalStoreUnavailableError(
            f"could not open the proposal store at {path}: {exc}"
        ) from exc
    if not read_only:
        _ensure_table(con)
    return con


def _ensure_table(con) -> None:  # type: ignore[no-untyped-def]
    """Create the append-only proposal table if absent — the proposal schema, status=proposed grain.

    The ONLY DDL in this module. No ALTER, no migration — the table is created once and only ever
    INSERTed into. The append-only/immutable property is realised by there being no other write
    path.
    """
    con.execute(
        f"""
        create table if not exists {_PROPOSAL_SCHEMA}.{_PROPOSAL_TABLE} (
            proposal_id          varchar primary key,
            break_id             varchar,
            reconciliation_type  varchar,
            record_a_ref         varchar,
            model_id             varchar,
            snapshot_ref         varchar,
            prompt_hash          varchar,
            proposed_cause       varchar,
            confidence           decimal(5, 4),
            rationale            varchar,
            of_record_cause      varchar,
            created_at           varchar,
            status               varchar
        )
        """
    )


def _proposal_id(break_id: str, run_id: str, seq: int) -> str:
    """A deterministic, run-scoped proposal id — stable for the same proposal in the same run.

    ``PROP-<run_id>-<seq>``: the run id scopes a proposer run; the sequence orders within it. A
    deterministic id means an idempotent re-append of the SAME run does not double-insert (the
    primary
    key rejects the duplicate), which keeps the store insert-only-and-idempotent.
    """
    return f"PROP-{run_id}-{seq:04d}"


def append_proposals(
    proposals: list[CauseProposal],
    run_id: str,
    store_path: Path | None = None,
) -> list[str]:
    """Append captured proposals as immutable ``status = proposed`` events — INSERT-ONLY.

    Each proposal is persisted at ``status = proposed`` (the captured-but-not-acted state). The
    proposal id is deterministic + run-scoped, so re-appending the SAME run is idempotent (the
    primary
    key rejects a duplicate — no double-insert, no mutation). There is NO update path: a proposal,
    once captured, is never modified. Returns the appended proposal ids (in input order).

    The LLM proposal is captured here ONLY — it never enters the break store, the canonical layer,
    or
    any of-record state (the deterministic spine). Promotion of a proposal into a deterministic rule
    is a HUMAN-GATED CODE CHANGE, never a runtime write here.
    """
    path = store_path or resolve_proposal_store_path()
    con = _connect(path, read_only=False)
    appended: list[str] = []
    try:
        for seq, p in enumerate(proposals):
            pid = _proposal_id(p.break_id, run_id, seq)
            con.execute(
                f"""
                insert into {_PROPOSAL_SCHEMA}.{_PROPOSAL_TABLE} (
                    proposal_id, break_id, reconciliation_type, record_a_ref, model_id,
                    snapshot_ref, prompt_hash, proposed_cause, confidence, rationale,
                    of_record_cause, created_at, status
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed')
                on conflict (proposal_id) do nothing
                """,
                [
                    pid,
                    p.break_id,
                    p.reconciliation_type,
                    p.record_a_ref,
                    p.model_id,
                    p.snapshot_ref,
                    p.prompt_hash,
                    p.proposed_cause,
                    p.confidence,
                    p.rationale,
                    p.of_record_cause,
                    p.created_at or datetime.now().isoformat(timespec="seconds"),
                ],
            )
            appended.append(pid)
    finally:
        con.close()
    return appended


def read_proposals(store_path: Path | None = None) -> list[StoredProposal]:
    """Read all captured proposals back, ordered by proposal_id — READ-ONLY (no mutation path)."""
    path = store_path or resolve_proposal_store_path()
    con = _connect(path, read_only=True)
    try:
        rows = con.execute(
            f"""
            select proposal_id, break_id, reconciliation_type, record_a_ref, model_id,
                snapshot_ref, prompt_hash, proposed_cause, confidence, rationale,
                of_record_cause, created_at, status
            from {_PROPOSAL_SCHEMA}.{_PROPOSAL_TABLE}
            order by proposal_id
            """
        ).fetchall()
    finally:
        con.close()
    return [
        StoredProposal(
            proposal_id=str(r[0]),
            break_id=str(r[1]),
            reconciliation_type=str(r[2]),
            record_a_ref=str(r[3]),
            model_id=str(r[4]),
            snapshot_ref=str(r[5]),
            prompt_hash=str(r[6]),
            proposed_cause=str(r[7]),
            confidence=None if r[8] is None else Decimal(str(r[8])),
            rationale=str(r[9]),
            of_record_cause=str(r[10]),
            created_at=str(r[11]),
            status=str(r[12]),
        )
        for r in rows
    ]


def count_proposals(store_path: Path | None = None) -> int:
    """Count the captured proposals — READ-ONLY. Zero (not an error) when the store is absent."""
    path = store_path or resolve_proposal_store_path()
    if not path.exists():
        return 0
    con = _connect(path, read_only=True)
    try:
        row = con.execute(
            f"select count(*) from {_PROPOSAL_SCHEMA}.{_PROPOSAL_TABLE}"
        ).fetchone()
    finally:
        con.close()
    return int(row[0]) if row else 0
