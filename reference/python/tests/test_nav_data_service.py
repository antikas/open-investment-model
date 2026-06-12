"""The ``navData`` Restate service handlers — the WIRE path the navCalculation workflow uses.

These tests drive the ``navData`` service HANDLERS (``get_fund_nav_components`` /
``get_fund_holdings_gross``) through a faithful fake ``restate.Context`` — the SAME seam the
TS workflow reaches over the ingress. This is the level the cycle-1 audit found a gap at: the
past-as-of refusal was unit-tested only on the bare Python *function* (``read_fund_nav_components``
called directly), which BYPASSED the handler — and the handler DROPPED the ``navKnowledgeDate``
field, so a past date returned a CURRENT NAV (HTTP 200) on the wire instead of the 422 refusal.

The fold (OIM-133 cycle-2) forwards ``navKnowledgeDate`` from the handler to the read. These
tests assert the refusal fires AT THE HANDLER (the wire path), closing that gap:

- ``test_past_as_of_is_refused_on_the_wire`` — the load-bearing wire-level test: a non-null
  ``navKnowledgeDate`` through the HANDLER raises a ``TerminalError`` (422), NOT a silently-struck
  current NAV. This is the test that the cycle-1 unit test did NOT cover (it bypassed the handler).
- the snake_case variant is NOT honoured (the wire field is ``navKnowledgeDate``; a snake_case
  ``nav_knowledge_date`` is not the contract field and is ignored — so it must NOT smuggle a past
  date past the refusal as a current strike either; documented behaviour).
- ``get_fund_holdings_gross`` is the independent holdings roll-up the workflow reconciles against.

The handler wraps the read in ``ctx.run``; the fake ``Context`` invokes the action and propagates
its result/exception exactly as the SDK does (a ``TerminalError`` escaping ``ctx.run`` is terminal,
not retried). Integration tests over the real store skip cleanly when the store is unprovisioned.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, cast

import pytest
import restate
from restate.exceptions import TerminalError

from agentinvest_demo.marts import MartsUnavailableError
from agentinvest_demo.nav_marts_read import list_fund_ids
from agentinvest_tools.nav_data_service import (
    get_fund_holdings_gross,
    get_fund_nav_components,
)
from agentinvest_tools.request_serde import PassThroughJsonSerde


class FakeContext:
    """A faithful stand-in for ``restate.Context``: ``run(name, action)`` invokes the action and
    propagates its value/exception unchanged — mirroring the SDK's ``ctx.run`` (a ``TerminalError``
    escaping is terminal/no-retry; any other escaping exception would be retried)."""

    def __init__(self) -> None:
        self.steps: list[str] = []

    async def run(self, name: str, action: Any, *args: Any, **kwargs: Any) -> Any:
        self.steps.append(name)
        result = action()
        if asyncio.iscoroutine(result):
            result = await result
        return result


def _components(ctx: FakeContext, req: Any) -> Any:
    return asyncio.run(get_fund_nav_components(cast(restate.Context, ctx), req))


def _holdings(ctx: FakeContext, req: Any) -> Any:
    return asyncio.run(get_fund_holdings_gross(cast(restate.Context, ctx), req))


def _store_available() -> bool:
    """True iff the canonical store can be read (duckdb installed + the marts built)."""
    try:
        list_fund_ids()
    except MartsUnavailableError:
        return False
    return True


pytestmark = pytest.mark.filterwarnings("ignore")


# --- THE WIRE-LEVEL PAST-AS-OF REFUSAL (the cycle-1 gap, now closed) ------------------------
#
# Needs NO store: the refusal is checked before any read, so it fires whether or not the marts
# are provisioned. This is the test the cycle-1 unit test did NOT have — it drives the HANDLER
# (which forwards navKnowledgeDate), not the bare function.


def test_past_as_of_is_refused_on_the_wire() -> None:
    """A non-null ``navKnowledgeDate`` through the HANDLER → TerminalError(422), not a current NAV.

    THE load-bearing wire-level test. At the cycle-1 baseline the handler dropped the field and a
    past date returned the CURRENT NAV with HTTP 200. The fold forwards the field; the OIM-111
    refusal now fires on the wire path the workflow uses — the honest boundary holds end-to-end.
    """
    with pytest.raises(TerminalError) as excinfo:
        _components(FakeContext(), {"fundId": "PF-0001", "navKnowledgeDate": "2020-01-01"})
    # The terminal error is the 422 refusal naming the past-as-of bound.
    assert getattr(excinfo.value, "status_code", None) == 422
    assert "past-as-of" in str(excinfo.value).lower()


def test_past_as_of_refused_for_any_fund_on_the_wire() -> None:
    """The refusal is field-driven, not fund-specific — any fund + a past date refuses on the wire.

    A past date over the handler refuses regardless of which fund is named.
    """
    for fund_id in ("PF-0001", "PF-0002", "PF-0003"):
        with pytest.raises(TerminalError):
            _components(FakeContext(), {"fundId": fund_id, "navKnowledgeDate": "2019-12-31"})


# --- THE REJECT-UNKNOWN-KEYS HARDENING (OIM-185) — proven ON THE WIRE -----------------------
#
# The fiduciary-surface input-validation hardening (from OIM-133 cycle-2 P-MINOR-1): the request
# contracts were bare TypedDicts, which do NOT reject extra keys at runtime, so an off-contract key
# (e.g. snake_case `nav_knowledge_date` instead of the contract `navKnowledgeDate`) was silently
# ignored — a current NAV under a mis-keyed request. The request types are now Pydantic models with
# `extra="forbid"`, validated IN THE HANDLER BODY, so an unrecognised key is a clean TerminalError
# (400) on the wire. These tests drive the HANDLER (not the bare read function), the same seam the
# silent-drop bug hid behind. They need NO store: the guard runs before any read.
#
# Honest boundary: a DEFENSIVE input-validation hardening. The real contract fields were already
# enforced (no fiduciary number was ever wrong); this closes the silent-mis-key class — an unknown
# key now fails loud rather than being ignored.


def test_components_unknown_key_is_terminal_400_on_the_wire() -> None:
    """An off-contract key on getFundNavComponents → TerminalError(400), not a silent current NAV.

    The exact OIM-133 P-MINOR-1 archetype: a caller passing snake_case ``nav_knowledge_date`` (NOT
    the contract field ``navKnowledgeDate``) used to get a CURRENT NAV with no error. It now fails
    loud at the handler before any read — the silent-mis-key class is closed on the wire.
    """
    with pytest.raises(TerminalError) as excinfo:
        _components(
            FakeContext(),
            {"fundId": "PF-0001", "nav_knowledge_date": "2020-01-01"},  # snake_case, off-contract
        )
    assert getattr(excinfo.value, "status_code", None) == 400
    assert "invalid request" in str(excinfo.value).lower()


def test_components_arbitrary_unknown_key_is_terminal_400_on_the_wire() -> None:
    """Any unrecognised key (not just the snake_case mis-key) is a clean terminal 400 on the wire.

    The reject-unknown-keys guard rejects ANY extra key, not only the OIM-133 snake_case archetype.
    """
    with pytest.raises(TerminalError) as excinfo:
        _components(FakeContext(), {"fundId": "PF-0001", "bogusKey": 1})
    assert getattr(excinfo.value, "status_code", None) == 400


def test_holdings_unknown_key_is_terminal_400_on_the_wire() -> None:
    """An off-contract key on getFundHoldingsGross → TerminalError(400) on the wire.

    The same reject-unknown-keys hardening as getFundNavComponents, on the sibling handler.
    """
    with pytest.raises(TerminalError) as excinfo:
        _holdings(FakeContext(), {"fundId": "PF-0001", "rogue": "x"})
    assert getattr(excinfo.value, "status_code", None) == 400
    assert "invalid request" in str(excinfo.value).lower()


def test_components_non_dict_body_is_terminal_400_on_the_wire() -> None:
    """A non-object body (a JSON array/string) to the handler → a clean terminal 400, not a 500."""
    with pytest.raises(TerminalError) as excinfo:
        _components(FakeContext(), ["not", "an", "object"])
    assert getattr(excinfo.value, "status_code", None) == 400


# --- MALFORMED-BODY → CLEAN 400 (OIM-187: the serde never raises) ----------------------------
#
# Drive the FULL wire path on BOTH handlers — the shared ``PassThroughJsonSerde.deserialize`` over
# the raw bytes (the transport-body parse; must NOT raise) then the REAL handler over its result. A
# malformed-JSON / non-UTF8 body must surface as a clean ``TerminalError(400)``, never a status-less
# 500 / uncaught ``UnicodeDecodeError`` — store-independent (the 400 fires before any read).


@pytest.mark.parametrize("body", [b"{bad", b'{"x":', b'"unterminated', b"\xff\xfe", b"\x80\x81"])
def test_components_malformed_or_non_utf8_body_is_terminal_400(body: bytes) -> None:
    """getFundNavComponents: a malformed-JSON / non-UTF8 body → a clean 400, never a 500."""
    deserialised = PassThroughJsonSerde().deserialize(body)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _components(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


@pytest.mark.parametrize("body", [b"{bad", b'{"x":', b'"unterminated', b"\xff\xfe", b"\x80\x81"])
def test_holdings_malformed_or_non_utf8_body_is_terminal_400(body: bytes) -> None:
    """getFundHoldingsGross: a malformed-JSON / non-UTF8 body → a clean 400, never a 500."""
    deserialised = PassThroughJsonSerde().deserialize(body)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _holdings(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


# --- DEEP-NEST BODY → CLEAN 400 (OIM-187 cycle-2: the never-raise invariant is now structural) -
#
# A deeply-nested JSON body makes ``json.loads`` raise ``RecursionError`` (a ``RuntimeError``
# subclass, NOT a ``ValueError``) — the cycle-1 enumerated ``except`` tuple did NOT catch it, so it
# escaped → a status-less 500. The cycle-2 fold catches the WHOLE parse-failure class
# (``except Exception``) → the serde returns the raw text as a non-dict ``str`` the handler 400s.
# REVERT-SENSITIVE: re-narrowing the catch makes the deep-nest body raise out of ``deserialize``.

# A few-KB craftable payload: 20000 levels of nesting, well past the C scanner's depth budget.
DEEP_NEST_BODY = b"[" * 20000 + b"]" * 20000


def test_components_deep_nest_body_is_terminal_400() -> None:
    """getFundNavComponents: a deeply-nested JSON body → a clean 400, never a status-less 500."""
    deserialised = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _components(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


def test_holdings_deep_nest_body_is_terminal_400() -> None:
    """getFundHoldingsGross: a deeply-nested JSON body → a clean 400, never a status-less 500."""
    deserialised = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _holdings(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


def test_serde_never_raises_on_deep_nest_body() -> None:
    """The structural never-raise invariant: a deep-nest body that trips ``RecursionError`` inside
    ``json.loads`` does NOT escape ``deserialize`` — it returns a (str) value. Revert-sensitive."""
    out = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise (was RecursionError)
    assert isinstance(out, str)


def test_valid_keys_pass_the_guard_store_independent() -> None:
    """The valid contract keys are NOT rejected by the reject-unknown-keys guard (no store needed).

    A valid current-strike request ({fundId} only) and a valid past-as-of request must NEVER raise
    a 400 from the new guard. With no store the read raises a 422 (MartsUnavailable) for the current
    strike, and the past-as-of refusal is its own 422 — both ≠ the guard's 400. This proves the
    guard rejects ONLY unknown keys; every valid key still reaches the read/refusal path.
    """
    # A valid current strike: must pass the guard (no 400). It either returns (store present) or
    # raises a 422 (store absent) — never the guard's 400.
    try:
        _components(FakeContext(), {"fundId": "PF-0001"})
    except TerminalError as exc:
        assert getattr(exc, "status_code", None) == 422, "valid current strike must not be a 400"
    # A valid past-as-of request: the OIM-133 refusal fires (422), NOT the guard's 400.
    with pytest.raises(TerminalError) as excinfo:
        _components(FakeContext(), {"fundId": "PF-0001", "navKnowledgeDate": "2020-01-01"})
    assert getattr(excinfo.value, "status_code", None) == 422


# --- integration: the current strike + the independent holdings roll-up (need the store) ------


@pytest.mark.skipif(not _store_available(), reason="store not provisioned")
def test_current_strike_returns_components_on_the_wire() -> None:
    """A current strike (no ``navKnowledgeDate``) through the HANDLER returns the §A1 components."""
    out = _components(FakeContext(), {"fundId": "PF-0001"})
    assert out["fundId"] == "PF-0001"
    assert out["computedBy"] == "python:navData"
    # The §A1 identity holds on the row: gross + accruals − fees == nav_usd.
    rolled = Decimal(out["grossMarketValue"]) + Decimal(out["accruedIncome"]) - Decimal(out["fees"])
    assert rolled == Decimal(out["navUsd"])


@pytest.mark.skipif(not _store_available(), reason="store not provisioned")
def test_holdings_gross_ties_to_nav_mart_gross_cross_mart() -> None:
    """The GENUINE cross-mart reconcile: Σ mart_portfolio_holdings == mart_fund_nav.gross, per fund.

    This is the falsifiable check the workflow's roll-up runs — two marts, two SQL paths. A green
    here proves the holdings-derived gross (an INDEPENDENT path) ties to the fund-NAV mart's gross,
    so the workflow's reconciliation is NOT the within-row X==X tautology the cycle-1 audit found.
    """
    for fund_id in list_fund_ids():
        nav = _components(FakeContext(), {"fundId": fund_id})
        hold = _holdings(FakeContext(), {"fundId": fund_id})
        assert hold["fundId"] == fund_id
        assert hold["computedBy"] == "python:navData"
        # Independent holdings roll-up == the NAV mart's gross (the cross-mart invariant).
        assert Decimal(hold["holdingsGrossMarketValue"]) == Decimal(nav["grossMarketValue"]), (
            f"{fund_id}: holdings-mart gross {hold['holdingsGrossMarketValue']} != "
            f"mart_fund_nav.gross_market_value {nav['grossMarketValue']}"
        )


@pytest.mark.skipif(not _store_available(), reason="store not provisioned")
def test_unknown_fund_holdings_is_terminal_on_the_wire() -> None:
    """An unknown fund to the holdings handler → TerminalError(422) (a clean data condition)."""
    with pytest.raises(TerminalError) as excinfo:
        _holdings(FakeContext(), {"fundId": "PF-9999"})
    assert getattr(excinfo.value, "status_code", None) == 422
