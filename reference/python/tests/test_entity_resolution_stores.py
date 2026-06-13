"""The append-only resolution stores — insert-only, immutable (OIM-199, the break-store test
pattern).

Proves the two engine-owned resolution stores (review-queue + golden-record) are append-only
insert-only (the OIM-162 break/proposal-store discipline, replicated): a record is captured at its
status grain, an idempotent re-append does not double-insert, and there is NO update / NO
status-transition / NO delete path — asserted behaviourally (a re-append is idempotent) and
structurally (each module exposes only append + read paths; the executed SQL is INSERT + SELECT +
CREATE only). The stores use a tmp duckdb file (``store_path`` argument), so they never touch the
real engine-owned stores and need no canonical store. Store-gated only on duckdb importable.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import agentinvest_tools.entity_resolution.golden_record_store as golden_module
import agentinvest_tools.entity_resolution.review_queue_store as review_module
from agentinvest_tools.entity_resolution import (
    GoldenRecordRow,
    GoldenRecordStoreUnavailableError,
    ResolutionReviewStoreUnavailableError,
    ReviewItem,
    append_golden_records,
    append_review_items,
    count_golden_records,
    count_review_items,
    read_golden_records,
    read_review_items,
    resolve_golden_store_path,
    resolve_review_store_path,
)


def _duckdb_available() -> bool:
    try:
        importlib.import_module("duckdb")
    except ImportError:
        return False
    return True


DUCKDB = pytest.mark.skipif(not _duckdb_available(), reason="duckdb not installed")


def _review(src: str) -> ReviewItem:
    return ReviewItem(
        source_record_id=src,
        source_system="administrator",
        raw_name="Apex Global Holdings Ltd",
        raw_domicile="SG",
        tier="tier_3_review",
        signal="conflicting domicile — quarantined",
        as_of_date="2026-01-31",
    )


def _golden(entity_id: str) -> GoldenRecordRow:
    return GoldenRecordRow(
        entity_id=entity_id,
        entity_name="Acme Asset Management LLP",
        lei="5493001KJTIIGC8Y1R12",
        domicile="GB",
        source_record_ids=("ERF-0001", "ERF-0004"),
        provenance_json='[{"field": "entity_name", "value": "Acme Asset Management LLP"}]',
    )


# --- review-queue store ---------------------------------------------------------------------------


@DUCKDB
def test_review_append_persists_at_in_review(tmp_path: Path) -> None:
    store = tmp_path / "review.duckdb"
    ids = append_review_items([_review("ERF-16"), _review("ERF-19")], run_id="r1", store_path=store)
    assert len(ids) == 2
    stored = read_review_items(store)
    assert len(stored) == 2
    for it in stored:
        assert it.status == "in_review"


@DUCKDB
def test_review_reappend_same_run_is_idempotent(tmp_path: Path) -> None:
    store = tmp_path / "review.duckdb"
    items = [_review("ERF-16"), _review("ERF-19")]
    append_review_items(items, run_id="r1", store_path=store)
    assert count_review_items(store) == 2
    append_review_items(items, run_id="r1", store_path=store)
    assert count_review_items(store) == 2


@DUCKDB
def test_review_read_absent_store_clean_error(tmp_path: Path) -> None:
    store = tmp_path / "nope.duckdb"
    assert count_review_items(store) == 0
    with pytest.raises(ResolutionReviewStoreUnavailableError):
        read_review_items(store)


# --- golden-record store --------------------------------------------------------------------------


@DUCKDB
def test_golden_append_persists_at_resolved_keyed_by_entity_id(tmp_path: Path) -> None:
    store = tmp_path / "golden.duckdb"
    ids = append_golden_records([_golden("LE-0001")], run_id="r1", store_path=store)
    assert len(ids) == 1
    stored = read_golden_records(store)
    assert len(stored) == 1
    assert stored[0].entity_id == "LE-0001"  # internal golden key
    assert stored[0].lei == "5493001KJTIIGC8Y1R12"  # survived attribute, not the key
    assert stored[0].status == "resolved"
    assert stored[0].source_record_ids == ("ERF-0001", "ERF-0004")


@DUCKDB
def test_golden_reappend_same_run_is_idempotent(tmp_path: Path) -> None:
    store = tmp_path / "golden.duckdb"
    recs = [_golden("LE-0001"), _golden("LE-0004")]
    append_golden_records(recs, run_id="r1", store_path=store)
    assert count_golden_records(store) == 2
    append_golden_records(recs, run_id="r1", store_path=store)
    assert count_golden_records(store) == 2


@DUCKDB
def test_golden_read_absent_store_clean_error(tmp_path: Path) -> None:
    store = tmp_path / "nope.duckdb"
    assert count_golden_records(store) == 0
    with pytest.raises(GoldenRecordStoreUnavailableError):
        read_golden_records(store)


# --- structural append-only invariants (the AST scan) ---------------------------------------------


def _defined_functions(module: object) -> set[str]:
    import inspect

    return {
        name
        for name, obj in vars(module).items()
        if not name.startswith("_")
        and inspect.isfunction(obj)
        and obj.__module__ == module.__name__  # type: ignore[attr-defined]
    }


def test_review_store_has_no_mutation_path() -> None:
    """STRUCTURAL: the review store exposes NO update / status-transition / delete API."""
    defined = _defined_functions(review_module)
    allowed = {
        "append_review_items",
        "read_review_items",
        "count_review_items",
        "resolve_review_store_path",
    }
    assert not (defined - allowed), f"unexpected (mutation) entry point: {defined - allowed}"


def test_golden_store_has_no_mutation_path() -> None:
    """STRUCTURAL: the golden store exposes NO update / status-transition / delete API."""
    defined = _defined_functions(golden_module)
    allowed = {
        "append_golden_records",
        "read_golden_records",
        "count_golden_records",
        "resolve_golden_store_path",
        "provenance_to_json",
    }
    assert not (defined - allowed), f"unexpected (mutation) entry point: {defined - allowed}"


def _executed_sql(module: object) -> list[str]:
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

    src = Path(module.__file__).read_text(encoding="utf-8")  # type: ignore[attr-defined]
    tree = ast.parse(src)
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "execute":
                for arg in node.args:
                    text = _literal_text(arg)
                    if text:
                        out.append(text.lower())
    return out


def test_review_store_sql_is_insert_select_create_only() -> None:
    """STRUCTURAL: the review-store module's executed SQL contains no mutation verb."""
    sqls = _executed_sql(review_module)
    assert sqls
    for sql in sqls:
        for verb in ("update ", "delete ", "alter table", "drop table"):
            assert verb not in sql, f"executed SQL must not contain '{verb}': {sql!r}"


def test_golden_store_sql_is_insert_select_create_only() -> None:
    """STRUCTURAL: the golden-store module's executed SQL contains no mutation verb."""
    sqls = _executed_sql(golden_module)
    assert sqls
    for sql in sqls:
        for verb in ("update ", "delete ", "alter table", "drop table"):
            assert verb not in sql, f"executed SQL must not contain '{verb}': {sql!r}"


def test_resolution_stores_are_distinct_files_from_each_other_and_the_canonical_store() -> None:
    """The review + golden stores resolve to OWN files, distinct from each other + the
    canonical/break.

    The engine-owned stores must be SEPARATE files so ``dbt build`` (which owns only the canonical
    store) never touches them. Asserts the keyed default file-name prefixes are distinct.
    """
    review = resolve_review_store_path().name
    golden = resolve_golden_store_path().name
    assert review != golden
    assert review.startswith("resolution-review-")
    assert golden.startswith("resolution-golden-")
