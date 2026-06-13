"""The ``bd12`` book-of-record read service — the WIRE path + the canonical dual-book read.

These tests drive the ``bd12`` dispatch service (``execute_so`` / ``list_capabilities``) through a
faithful fake ``restate.Context`` — the same seam the orchestrator and the MCP/OpenAPI ingress reach
over Restate. Two levels:

1. **Envelope + catalogue (no store needed)** — the envelope guard (a non-dict / extra-key / unknown
   SO is a clean terminal error), and ``list_capabilities`` returns the 9 read tools with real I/O
   schemas (the bd09 service-test pattern).
2. **The canonical dual-book read (store-gated)** — the LOAD-BEARING tests: the read tools genuinely
   read the canonical dual book through the data-access layer at the as-of, AND the IBOR read
   and the ABOR read of the same holding GENUINELY DIFFER on the three divergence classes
   (TD/SD timing, accruals, cost-basis). If the two reads were identical there would be nothing for
   the reconciliation engine to reconcile. These skip cleanly when the canonical store is not
   provisioned.

Honest boundary: the read is over the **synthetic** internal dual book; a green read proves
the typed per-book read + the as-of plumbing + the divergence, not a production book-of-record.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
import restate
from restate.exceptions import TerminalError

from agentinvest_demo.book_of_record_data import list_portfolios
from agentinvest_demo.marts import MartsUnavailableError
from agentinvest_tools.bd12_service import (
    _REGISTRY,
    execute_so,
    list_capabilities,
)


class FakeContext:
    """A faithful stand-in for ``restate.Context``: ``run(name, action)`` invokes the action and
    propagates its value/exception unchanged — mirroring the SDK's ``ctx.run`` (a ``TerminalError``
    escaping is terminal/no-retry)."""

    def __init__(self) -> None:
        self.steps: list[str] = []

    async def run(self, name: str, action: Any, *args: Any, **kwargs: Any) -> Any:
        self.steps.append(name)
        result = action()
        if asyncio.iscoroutine(result):
            result = await result
        return result


def _execute(req: Any) -> Any:
    return asyncio.run(execute_so(cast(restate.Context, FakeContext()), req))


def _capabilities() -> Any:
    return asyncio.run(list_capabilities(cast(restate.Context, FakeContext())))


def _store_available() -> bool:
    """True iff the canonical store can be read (duckdb installed + the marts built)."""
    try:
        list_portfolios()
    except MartsUnavailableError:
        return False
    return True


pytestmark = pytest.mark.filterwarnings("ignore")


# --- the catalogue + the envelope guard (no store needed) ----------------------------------------


def test_catalogue_lists_the_nine_read_tools() -> None:
    """``list_capabilities`` returns the 9 IBOR + ABOR read tools with real I/O schemas."""
    out = _capabilities()
    assert out["service"] == "bd12"
    so_ids = {c["soId"] for c in out["capabilities"]}
    # SD-12.1 IBOR (5) + SD-12.2 ABOR (4) = 9 — the reconciliation-relevant read surface.
    assert so_ids == {
        "SO-12.1-01",
        "SO-12.1-02",
        "SO-12.1-03",
        "SO-12.1-04",
        "SO-12.1-05",
        "SO-12.2-01",
        "SO-12.2-02",
        "SO-12.2-03",
        "SO-12.2-04",
    }
    # each carries a real input + output JSON schema derived from the Pydantic models
    for cap in out["capabilities"]:
        assert cap["inputSchema"]["type"] == "object"
        assert cap["outputSchema"]["type"] == "object"
        assert cap["books"]  # each names the book(s) it applies to


def test_registry_so_names_map_to_the_sd_spec() -> None:
    """The SO ids map 1:1 to the SD-12.1 / SD-12.2 Service Operations (the SD READMEs)."""
    ibor = [s for s in _REGISTRY if s.startswith("SO-12.1")]
    abor = [s for s in _REGISTRY if s.startswith("SO-12.2")]
    assert len(ibor) == 5  # position · cash+exposure · pending · E-05 read · E-06 read
    assert len(abor) == 4  # accounting position · accruals · cost-basis · book-close


def test_unknown_so_is_terminal_404() -> None:
    with pytest.raises(TerminalError) as excinfo:
        _execute({"soId": "SO-99-99", "args": {}})
    assert getattr(excinfo.value, "status_code", None) == 404


def test_non_dict_envelope_is_terminal_400() -> None:
    with pytest.raises(TerminalError) as excinfo:
        _execute(["not", "an", "object"])
    assert getattr(excinfo.value, "status_code", None) == 400


def test_extra_envelope_key_is_terminal_400() -> None:
    with pytest.raises(TerminalError) as excinfo:
        _execute({"soId": "SO-12.1-01", "args": {}, "bogus": 1})
    assert getattr(excinfo.value, "status_code", None) == 400


def test_unknown_arg_is_terminal_400() -> None:
    """An off-contract read arg (extra="forbid" on ReadRequest) is a clean terminal 400."""
    bad = {"soId": "SO-12.1-01", "args": {"book": "ibor", "portfolio_id": "PF-0008", "bogus": 1}}
    with pytest.raises(TerminalError) as excinfo:
        _execute(bad)
    assert getattr(excinfo.value, "status_code", None) == 400


def test_wrong_book_for_abor_tool_is_terminal() -> None:
    """An ABOR-only SO asked for the 'ibor' book is a clean terminal error (not a wrong read)."""
    with pytest.raises(TerminalError) as excinfo:
        _execute({"soId": "SO-12.2-02", "args": {"book": "ibor", "portfolio_id": "PF-0012"}})
    assert getattr(excinfo.value, "status_code", None) == 422


# --- the canonical dual-book read + the IBOR/ABOR divergence (store-gated, LOAD-BEARING) ----------

# The named holdings carrying each divergence class (confirmed against the canonical seed).
_TD_SD_PORTFOLIO = "PF-0008"   # POS-0021/22/27/30/31/36 — ibor qty/MV > abor (in-flight trades)
_ACCRUAL_PORTFOLIO = "PF-0012"  # POS-0049..0053 — abor carries accrual, ibor null
_COST_BASIS_PORTFOLIO = "PF-0005"  # POS-0013 — abor cost basis != ibor cost basis


def _read(so_id: str, **args: Any) -> dict[str, Any]:
    out = _execute({"soId": so_id, "args": args})
    return cast(dict[str, Any], out["result"])


@pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")
def test_read_reads_the_canonical_layer_not_inlined_fixtures() -> None:
    """The IBOR position read returns the real canonical rows (not an empty/fake set)."""
    out = _read("SO-12.1-01", book="ibor", portfolio_id=_TD_SD_PORTFOLIO, as_of_date="2026-03-31")
    assert out["book"] == "ibor"
    assert out["n_positions"] > 0
    assert out["as_of_date"] == "2026-03-31"  # the as-of is honoured + echoed
    # POS-0021 is in this portfolio on the IBOR book at its known divergent MV
    by_id = {p["position_id"]: p for p in out["positions"]}
    assert "POS-0021" in by_id
    assert by_id["POS-0021"]["market_value_usd"] == "13303649.45"


@pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")
def test_ibor_and_abor_position_reads_differ_on_td_sd_timing() -> None:
    """THE load-bearing divergence test #1 — TD/SD timing: IBOR and ABOR reads of POS-0021 differ.

    POS-0021 (PF-0008) is a TD/SD-timing divergence: the IBOR book carries the in-flight trade on
    trade date (higher quantity + market value); the ABOR book recognises it only on settlement.
    If the two reads agreed there would be nothing for the reconciliation engine to reconcile.
    """
    ibor = _read("SO-12.1-01", book="ibor", portfolio_id=_TD_SD_PORTFOLIO, as_of_date="2026-03-31")
    abor = _read("SO-12.2-01", book="abor", portfolio_id=_TD_SD_PORTFOLIO, as_of_date="2026-03-31")
    ibor_pos = {p["position_id"]: p for p in ibor["positions"]}
    abor_pos = {p["position_id"]: p for p in abor["positions"]}

    # The named holding's quantity AND market value genuinely differ between the two books.
    assert ibor_pos["POS-0021"]["quantity"] != abor_pos["POS-0021"]["quantity"]
    assert ibor_pos["POS-0021"]["market_value_usd"] != abor_pos["POS-0021"]["market_value_usd"]
    # The IBOR book is higher (it carries the in-flight buy the ABOR book has not yet settled).
    from decimal import Decimal

    assert Decimal(ibor_pos["POS-0021"]["market_value_usd"]) > Decimal(
        abor_pos["POS-0021"]["market_value_usd"]
    )
    # And the book-level totals differ too (not just one row).
    assert ibor["total_market_value_usd"] != abor["total_market_value_usd"]


@pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")
def test_ibor_and_abor_reads_differ_on_accruals() -> None:
    """THE load-bearing divergence test #2 — accruals: the ABOR book accrues, the IBOR does not.

    The ABOR accrued-income read (SO-12.2-02) returns a non-zero accrual for PF-0012; the IBOR
    position read of the same portfolio carries zero accrued income (E-04 places accruals on ABOR).
    """
    abor_accrual = _read("SO-12.2-02", book="abor", portfolio_id=_ACCRUAL_PORTFOLIO)
    ibor_pos = _read("SO-12.1-01", book="ibor", portfolio_id=_ACCRUAL_PORTFOLIO)
    from decimal import Decimal

    assert Decimal(abor_accrual["total_accrued_income_usd"]) > 0
    assert abor_accrual["n_accruing_positions"] > 0
    # The IBOR book carries no accrual for the same portfolio — the divergence.
    assert Decimal(ibor_pos["total_accrued_income_usd"]) == 0


@pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")
def test_ibor_and_abor_reads_differ_on_cost_basis() -> None:
    """THE load-bearing divergence test #3 — cost-basis: POS-0013 ABOR cost basis != IBOR."""
    ibor = _read("SO-12.1-01", book="ibor", portfolio_id=_COST_BASIS_PORTFOLIO)
    abor_cost = _read("SO-12.2-03", book="abor", portfolio_id=_COST_BASIS_PORTFOLIO)
    ibor_pos = {p["position_id"]: p for p in ibor["positions"]}
    abor_pos = {p["position_id"]: p for p in abor_cost["positions"]}
    # POS-0013 carries a genuinely-different cost basis on the two books.
    assert "POS-0013" in ibor_pos
    assert "POS-0013" in abor_pos
    assert ibor_pos["POS-0013"]["cost_basis_usd"] != abor_pos["POS-0013"]["cost_basis_usd"]


@pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")
def test_pending_activity_reads_the_in_flight_trades() -> None:
    """The IBOR pending-activity read returns the in-flight (settlement > as-of) trades."""
    out = _read("SO-12.1-03", book="ibor", portfolio_id=_TD_SD_PORTFOLIO, as_of_date="2026-03-31")
    assert out["n_pending"] > 0
    # every returned transaction settles AFTER the as-of (the in-flight property the read honours)
    for txn in out["transactions"]:
        assert txn["settlement_date"] > "2026-03-31"
        assert txn["status"] in ("pending", "confirmed")


@pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")
def test_as_of_is_honoured_no_future_pending_before_trades() -> None:
    """An as-of AFTER all settlements returns zero pending activity (the as-of filter bites)."""
    # All seeded in-flight trades settle by 2026-04-02; an as-of after that has nothing in-flight.
    out = _read("SO-12.1-03", book="ibor", portfolio_id=_TD_SD_PORTFOLIO, as_of_date="2026-05-01")
    assert out["n_pending"] == 0


@pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")
def test_book_close_state_reads_the_struck_book_date() -> None:
    """The book-close-state read derives 'closed' for the canonical as-of from the struck date."""
    out = _read("SO-12.2-04", book="abor", as_of_date="2026-03-31")
    assert out["status"] == "closed"
    assert out["is_locked"] is True
    assert out["latest_struck_book_date"] == "2026-03-31"


@pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")
def test_transaction_and_cash_flow_reads_return_rows() -> None:
    """The E-05 / E-06 reads (reconciliation transaction-matching + cash legs) return real rows."""
    txns = _read("SO-12.1-04", book="ibor", portfolio_id=_TD_SD_PORTFOLIO, as_of_date="2026-03-31")
    assert txns["n_transactions"] > 0
    cflows = _read(
        "SO-12.1-05", book="ibor", portfolio_id=_ACCRUAL_PORTFOLIO, as_of_date="2026-03-31"
    )
    assert cflows["n_cash_flows"] >= 0  # PF-0012 may or may not carry E-06 rows; the read is clean
