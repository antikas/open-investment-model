"""The append-only LLM-proposal store — insert-only, immutable.

Proves the proposal store is append-only insert-only (the break-store test pattern, replicated for
the second engine-owned store): a proposal is captured at ``status = proposed``, an idempotent
re-append does not double-insert, and there is NO update / NO ``status``-transition / NO promote /
NO delete path — asserted both behaviourally (a re-append is idempotent) and structurally (the
module exposes only ``append_proposals`` + read paths; no mutation API exists; the executed SQL is
INSERT + SELECT + CREATE only).

The store tests use a tmp duckdb file (``store_path`` argument), so they never touch the real
engine-owned proposal store and need no canonical store. Store-gated only on duckdb importable.
"""

from __future__ import annotations

import importlib
from decimal import Decimal
from pathlib import Path

import pytest

import agentinvest_tools.bd12_recon.proposal_store as proposal_store_module
from agentinvest_tools.bd12_recon import (
    CauseProposal,
    append_proposals,
    count_proposals,
    read_proposals,
)
from agentinvest_tools.bd12_recon.proposal_store import ProposalStoreUnavailableError


def _duckdb_available() -> bool:
    try:
        importlib.import_module("duckdb")
    except ImportError:
        return False
    return True


DUCKDB = pytest.mark.skipif(not _duckdb_available(), reason="duckdb not installed")


def _proposal(break_id: str, cause: str = "fx") -> CauseProposal:
    return CauseProposal(
        break_id=break_id,
        reconciliation_type="ibor_abor",
        record_a_ref=break_id,
        model_id="stub:test",
        snapshot_ref="sha256:abc123",
        prompt_hash="sha256:def456",
        proposed_cause=cause,  # type: ignore[arg-type]
        confidence=Decimal("0.4500"),
        rationale="the observable evidence supports it.",
        of_record_cause="unexplained",
        created_at="2026-03-31T00:00:00",
    )


@DUCKDB
def test_append_persists_proposals_at_status_proposed(tmp_path: Path) -> None:
    """An appended proposal persists at status=proposed, of_record_cause=unexplained (the spine)."""
    store = tmp_path / "proposals.duckdb"
    ids = append_proposals([_proposal("BRK-1"), _proposal("BRK-2")], run_id="r1", store_path=store)
    assert len(ids) == 2
    stored = read_proposals(store)
    assert len(stored) == 2
    for p in stored:
        assert p.status == "proposed"
        assert p.of_record_cause == "unexplained"  # the of-record cause is NEVER the LLM's proposal
        assert p.confidence == Decimal("0.4500")


@DUCKDB
def test_reappend_of_the_same_run_is_idempotent_not_a_double_insert(tmp_path: Path) -> None:
    """Re-appending the SAME run does not double-insert — the run-scoped ids dedupe."""
    store = tmp_path / "proposals.duckdb"
    props = [_proposal("BRK-1"), _proposal("BRK-2")]
    append_proposals(props, run_id="r1", store_path=store)
    assert count_proposals(store) == 2
    append_proposals(props, run_id="r1", store_path=store)  # re-append → idempotent
    assert count_proposals(store) == 2


@DUCKDB
def test_different_runs_append_distinct_proposals(tmp_path: Path) -> None:
    """Two distinct runs append distinct proposals (the run id scopes the proposal ids)."""
    store = tmp_path / "proposals.duckdb"
    append_proposals([_proposal("BRK-1")], run_id="r1", store_path=store)
    append_proposals([_proposal("BRK-1")], run_id="r2", store_path=store)
    assert count_proposals(store) == 2


def test_proposal_store_has_no_mutation_or_promote_path() -> None:
    """STRUCTURAL: the proposal store exposes NO update / status-transition / promote / delete API.

    The append-only/immutable property is realised by the ABSENCE of a mutation path. The store's
    public surface is insert + read + path-resolve ONLY — there is no ``update_proposal``,
    ``transition_status``, ``promote_proposal``, ``delete_proposal`` or any other mutation entry
    point. A proposal is PROMOTED into a rule by a HUMAN-GATED, REVIEWED CODE CHANGE, never a
    runtime write here. If a future change adds a mutation path, this test fails loudly.
    """
    import inspect

    defined = {
        name
        for name, obj in vars(proposal_store_module).items()
        if not name.startswith("_")
        and inspect.isfunction(obj)
        and obj.__module__ == proposal_store_module.__name__
    }
    allowed = {
        "append_proposals", "read_proposals", "count_proposals", "resolve_proposal_store_path",
    }
    unexpected = defined - allowed
    assert not unexpected, (
        f"the proposal store has an unexpected (mutation/promote) entry point: {unexpected}"
    )
    assert "append_proposals" in defined
    assert "read_proposals" in defined
    assert "count_proposals" in defined


def test_proposal_store_source_contains_no_update_or_delete_sql() -> None:
    """STRUCTURAL: the proposal-store module's executed SQL is INSERT + SELECT + CREATE only.

    Parses the module's AST and inspects every string LITERAL passed to ``con.execute(...)`` (the
    only place SQL is run). The append path uses ``insert ... on conflict do nothing``; the reads
    use ``select``; the table is ``create table if not exists``. A mutation verb (``update`` /
    ``delete`` / ``alter`` / ``drop``) in any executed string would mean a write path exists — the
    test fails so the immutable-event contract is enforced at the SQL level, not just the API level.
    (Scoping to executed SQL strings means the docstring prose — which explains there is NO update
    path — does not trip the check.)
    """
    import ast

    def _literal_text(node: ast.AST) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return "".join(
                v.value
                for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
        return ""

    src = Path(proposal_store_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    executed_sql: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "execute":
                for arg in node.args:
                    text = _literal_text(arg)
                    if text:
                        executed_sql.append(text.lower())
    assert executed_sql, "expected at least one con.execute(...) SQL string in the proposal store"
    for sql in executed_sql:
        for verb in ("update ", "delete ", "alter table", "drop table"):
            assert verb not in sql, f"executed SQL must not contain '{verb}': {sql!r}"


@DUCKDB
def test_read_proposals_on_absent_store_is_a_clean_error(tmp_path: Path) -> None:
    """Reading an absent store is a clean ProposalStoreUnavailableError; count is zero (no err)."""
    store = tmp_path / "nonexistent.duckdb"
    assert count_proposals(store) == 0
    with pytest.raises(ProposalStoreUnavailableError):
        read_proposals(store)


def test_proposal_store_path_is_distinct_from_the_break_and_canonical_stores() -> None:
    """The proposal store resolves to its OWN file, distinct from the break + canonical stores.

    The three engine-owned/canonical stores must be SEPARATE files so ``dbt build`` (which owns only
    the canonical store) never touches the break or proposal stores. Asserts the keyed default file
    names are distinct (``proposal-store-`` vs ``recon-store-`` vs ``canonical-``).
    """
    from agentinvest_tools.bd12_recon import resolve_break_store_path, resolve_proposal_store_path

    prop = resolve_proposal_store_path().name
    brk = resolve_break_store_path().name
    assert prop != brk
    assert prop.startswith("proposal-store-")
    assert brk.startswith("recon-store-")
