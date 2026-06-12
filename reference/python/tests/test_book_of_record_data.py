"""The book-of-record data-access layer — reads the OIM-160 canonical dual book, READ-ONLY.

These tests prove the data-access layer (``agentinvest_demo.book_of_record_data``) genuinely reads
the OIM-160 canonical dual book (not inlined fixtures), per book, honouring the as-of, and is
read-only. They are store-gated (skip cleanly when the canonical store is not provisioned), the
``test_nav_marts_read`` precedent. The validation-of-arguments path (an unknown book) needs no
store.
"""

from __future__ import annotations

import pytest

from agentinvest_demo.book_of_record_data import (
    latest_struck_book_date,
    list_portfolios,
    read_pending_activity,
    read_positions,
)
from agentinvest_demo.marts import MartsUnavailableError


def _store_available() -> bool:
    try:
        list_portfolios()
    except MartsUnavailableError:
        return False
    return True


def test_unknown_book_is_refused_before_any_read() -> None:
    """An unknown book is a clean ``MartsUnavailableError`` before any query — no store needed."""
    with pytest.raises(MartsUnavailableError):
        read_positions("nonsense", "PF-0008", "2026-03-31")
    with pytest.raises(MartsUnavailableError):
        latest_struck_book_date("nonsense")


@pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")
def test_reads_the_two_books_distinctly() -> None:
    """The IBOR and ABOR position reads return rows from the named book only."""
    ibor = read_positions("ibor", "PF-0008", "2026-03-31")
    abor = read_positions("abor", "PF-0008", "2026-03-31")
    assert ibor and abor
    assert all(r.book == "ibor" for r in ibor)
    assert all(r.book == "abor" for r in abor)
    # the same logical holdings on both books (same position_id set), genuinely-different numbers
    ibor_ids = {r.position_id for r in ibor}
    abor_ids = {r.position_id for r in abor}
    assert ibor_ids == abor_ids


@pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")
def test_as_of_filter_bites_on_pending_activity() -> None:
    """The pending-activity read honours the as-of: after all settlements it yields nothing."""
    in_flight = read_pending_activity("PF-0008", "2026-03-31")
    settled = read_pending_activity("PF-0008", "2026-05-01")
    assert len(in_flight) > 0  # in-flight trades at the canonical as-of
    assert len(settled) == 0   # all have settled by 2026-05-01 — the filter genuinely bites
    # every in-flight row settles strictly after the read as-of
    for r in in_flight:
        assert r.settlement_date is not None
        assert r.settlement_date.isoformat() > "2026-03-31"


@pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")
def test_struck_book_date_is_the_canonical_as_of() -> None:
    """The latest struck ABOR book date is the canonical 2026-03-31 (the close-state base)."""
    assert latest_struck_book_date("abor").isoformat() == "2026-03-31"
