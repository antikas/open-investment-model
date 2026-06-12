"""The append-only E-24 break store — insert-only, immutable (OIM-162 cycle-1, load-bearing test 4).

Proves the break store is append-only insert-only: a break is persisted at ``status = open``, an
idempotent re-append does not double-insert, and there is NO update / NO status-transition / NO
correcting-entry / NO book-mutation path — asserted both behaviourally (a re-append is idempotent)
and structurally (the module exposes only ``append_breaks`` + read paths; no mutation API exists).

The store tests use a tmp duckdb file (``AGENTINVEST_RECON_STORE_PATH`` is honoured via the
``store_path`` argument), so they never touch the real engine-owned store and need no canonical
store. Store-gated only on duckdb being importable.
"""

from __future__ import annotations

import importlib
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import agentinvest_tools.bd12_recon.break_store as break_store_module
from agentinvest_tools.bd12_recon import (
    BreakFinding,
    append_breaks,
    count_breaks,
    read_breaks,
)
from agentinvest_tools.bd12_recon.break_store import BreakStoreUnavailableError

AS_OF = date(2026, 3, 31)


def _duckdb_available() -> bool:
    try:
        importlib.import_module("duckdb")
    except ImportError:
        return False
    return True


DUCKDB = pytest.mark.skipif(not _duckdb_available(), reason="duckdb not installed")


def _finding(ref: str, cause: str = "data_error") -> BreakFinding:
    return BreakFinding(
        reconciliation_type="position",
        record_a_ref=ref,
        record_b_ref=f"custodian:{ref}",
        as_of_date=AS_OF,
        difference_amount=Decimal("123.45"),
        difference_qty=None,
        cause_classification=cause,  # type: ignore[arg-type]
        materiality="medium",
    )


@DUCKDB
def test_append_persists_breaks_at_status_open(tmp_path: Path) -> None:
    """An appended break is persisted at status=open, identified_date=as_of, age_days=0."""
    store = tmp_path / "recon.duckdb"
    ids = append_breaks([_finding("POS-1"), _finding("POS-2")], run_id="r1", store_path=store)
    assert len(ids) == 2
    stored = read_breaks(store)
    assert len(stored) == 2
    for b in stored:
        assert b.status == "open"
        assert b.identified_date == AS_OF
        assert b.age_days == 0


@DUCKDB
def test_reappend_of_the_same_run_is_idempotent_not_a_double_insert(tmp_path: Path) -> None:
    """Re-appending the SAME run does not double-insert — the deterministic run-scoped ids dedupe.

    This is the insert-only-and-idempotent property: a replay (or a re-run of the same as-of) writes
    the SAME break ids, which the primary key rejects — so the store never grows on a re-append and
    never mutates an existing row. The count after two appends of the same run equals one append.
    """
    store = tmp_path / "recon.duckdb"
    findings = [_finding("POS-1"), _finding("POS-2")]
    append_breaks(findings, run_id="r1", store_path=store)
    assert count_breaks(store) == 2
    # Re-append the SAME run — idempotent, no double-insert.
    append_breaks(findings, run_id="r1", store_path=store)
    assert count_breaks(store) == 2


@DUCKDB
def test_different_runs_append_distinct_breaks(tmp_path: Path) -> None:
    """Two distinct runs append distinct breaks (the run id scopes the break ids)."""
    store = tmp_path / "recon.duckdb"
    append_breaks([_finding("POS-1")], run_id="r1", store_path=store)
    append_breaks([_finding("POS-1")], run_id="r2", store_path=store)
    assert count_breaks(store) == 2  # same finding, two runs → two distinct break events


def test_break_store_has_no_mutation_path() -> None:
    """STRUCTURAL: the break store exposes NO update / status-transition / correcting-entry API.

    The append-only/immutable property is realised by the ABSENCE of a mutation path. This test
    asserts the module's public surface is insert + read only — there is no ``update_break``,
    ``transition_status``, ``resolve_break``, ``write_correcting_entry``, ``delete_break`` or any
    other mutation entry point (those are OIM-163, behind the breach gate — not this cycle). If a
    future cycle adds one, this test fails loudly so the append-only contract cannot be silently
    broken.
    """
    # The callables DEFINED in this module (not imported types/helpers from elsewhere).
    import inspect

    defined = {
        name
        for name, obj in vars(break_store_module).items()
        if not name.startswith("_")
        and inspect.isfunction(obj)
        and obj.__module__ == break_store_module.__name__
    }
    # The break store's defined functions must be exactly this insert + read + path-resolve set —
    # any function NOT on this allowlist is an unexpected entry point (a mutation path is one).
    # The allowlist is explicit so a future cycle adding an ``update_break`` / ``resolve_break`` /
    # ``transition_status`` / ``write_correcting_entry`` fails this test loudly. (The legitimate
    # ``resolve_break_store_path`` is a PATH resolver, not a break resolver — it is allowed.)
    allowed = {"append_breaks", "read_breaks", "count_breaks", "resolve_break_store_path"}
    unexpected = defined - allowed
    assert not unexpected, (
        f"the break store has an unexpected (potential mutation) entry point: {unexpected}"
    )
    # The write surface is exactly append_breaks; the reads are read_breaks / count_breaks.
    assert "append_breaks" in defined
    assert "read_breaks" in defined
    assert "count_breaks" in defined


def test_break_store_source_contains_no_update_or_delete_sql() -> None:
    """STRUCTURAL: the break-store module's executed SQL is INSERT + SELECT + CREATE only.

    Parses the module's AST and inspects every string LITERAL passed to ``con.execute(...)`` — the
    only place SQL is run. The append path uses ``insert ... on conflict do nothing`` (insert-only);
    the reads use ``select``; the table is ``create table if not exists``. A mutation SQL verb
    (``update`` / ``delete`` / ``alter`` / ``drop``) in any executed string would mean a write path
    exists — the test fails so the immutable-event contract is enforced at the SQL level, not just
    the API level. (Scoping to executed SQL strings means the docstring prose — which legitimately
    explains there is NO update path — does not trip the check.)
    """
    import ast

    def _literal_text(node: ast.AST) -> str:
        """The literal text of a string node — a plain ``Constant`` OR the literal parts of an
        f-string (``JoinedStr``), so an ``f\"\"\"create table {x} ...\"\"\"`` is still scanned."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return "".join(
                v.value
                for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
        return ""

    src = Path(break_store_module.__file__).read_text(encoding="utf-8")
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
    assert executed_sql, "expected at least one con.execute(...) SQL string in the break store"
    for sql in executed_sql:
        for verb in ("update ", "delete ", "alter table", "drop table"):
            assert verb not in sql, f"executed SQL must not contain '{verb}': {sql!r}"


@DUCKDB
def test_read_breaks_on_absent_store_is_a_clean_error(tmp_path: Path) -> None:
    """Reading an absent store is a clean BreakStoreUnavailableError; count is zero (no error)."""
    store = tmp_path / "nonexistent.duckdb"
    assert count_breaks(store) == 0
    with pytest.raises(BreakStoreUnavailableError):
        read_breaks(store)
