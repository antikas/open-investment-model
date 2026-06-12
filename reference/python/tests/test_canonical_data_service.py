"""The ``canonicalData`` Restate service handlers — the Operator UI inspector's READ-ONLY seam.

These tests drive the ``canonicalData`` handlers (``list_tables`` / ``sample_table``) through a
faithful fake ``restate.Context`` — the SAME seam the Operator UI reaches over the ingress. The
load-bearing safety property the inspector MUST hold: it is READ-ONLY with NO injection surface —
the sampled table is validated against a store-derived allowlist, an unknown / crafted / injection
name is REFUSED (404) before any sample SQL, and there is no free-form SQL from the client.

The store-INDEPENDENT tests (the reject-unknown-keys guard + the load-bearing injection rejections)
run whether or not the marts are provisioned — the allowlist validation derives from the store, so
an injection name that cannot match any real table is rejected even on a present store, and a
non-dict / off-contract body is rejected before any read. The integration tests (real list + real
capped sample) skip cleanly when the store is unprovisioned.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
import restate
from restate.exceptions import TerminalError

from agentinvest_demo.canonical_inspect import SAMPLE_LIMIT_MAX, list_canonical_tables
from agentinvest_demo.marts import MartsUnavailableError
from agentinvest_tools.canonical_data_service import (
    list_tables,
    sample_table,
)
from agentinvest_tools.request_serde import PassThroughJsonSerde


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


def _list(ctx: FakeContext, req: Any) -> Any:
    return asyncio.run(list_tables(cast(restate.Context, ctx), req))


def _sample(ctx: FakeContext, req: Any) -> Any:
    return asyncio.run(sample_table(cast(restate.Context, ctx), req))


def _store_available() -> bool:
    """True iff the canonical store can be read (duckdb installed + the marts built)."""
    try:
        list_canonical_tables()
    except MartsUnavailableError:
        return False
    return True


pytestmark = pytest.mark.filterwarnings("ignore")


# --- THE LOAD-BEARING INJECTION / ALLOWLIST REJECTION (store-independent) --------------------
#
# The inspector's read-only / no-injection boundary: an unknown or crafted table name is REFUSED
# (404) before any sample SQL — never interpolated. These run on a present OR absent store: a
# crafted name cannot match any real allowlisted table, so it is rejected either way. This is the
# test the re-audit's P role attacks; it is the centre of the safety claim.


def test_sample_rejects_injection_table_name() -> None:
    """A classic SQL-injection table name → TerminalError(404), NOT a query — the load-bearing case.

    The crafted name is not a plain ``schema.table`` identifier pair (it carries SQL punctuation),
    so it is refused at the identifier guard before any membership check — never interpolated.
    """
    injections = [
        "main_marts.mart_fund_nav; drop table main_marts.mart_fund_nav",
        "main_marts.mart_fund_nav--",
        "main_staging.stg_e01_legal_entity union select * from main_raw.raw_e01_legal_entity",
        "'; delete from main_marts.mart_fund_nav; --",
        "main_marts.mart_fund_nav where 1=1",
        "(select 1)",
    ]
    for name in injections:
        with pytest.raises(TerminalError) as excinfo:
            _sample(FakeContext(), {"table": name})
        assert getattr(excinfo.value, "status_code", None) == 404, (
            f"injection name {name!r} must be a clean 404 rejection, not interpolated"
        )


def test_sample_rejects_unknown_but_well_formed_table_name() -> None:
    """A well-formed but NON-EXISTENT / non-allowlisted table name → TerminalError(404).

    A plain-identifier name that is not in the store-derived inspectable set (a different schema, a
    table that does not exist, the RAW layer which is not reader-facing) is refused — it never
    reaches the engine as a sample. Store-independent: it cannot match any real allowlisted table.
    """
    not_allowed = [
        "main_raw.raw_e01_legal_entity",  # the raw layer is not inspectable
        "main_marts.mart_does_not_exist",  # a mart-prefixed name that does not exist
        "main_staging.stg_e99_nonsense",  # a staging-prefixed name that does not exist
        "information_schema.tables",  # a real table but not in the inspectable layer
        "main_marts",  # not a schema.table pair
        "mart_fund_nav",  # bare table, no schema
    ]
    for name in not_allowed:
        with pytest.raises(TerminalError) as excinfo:
            _sample(FakeContext(), {"table": name})
        # A non-allowlisted name is a clean rejection, NEVER a query: 404 when the store is present
        # (genuinely not in the derived allowlist) or 422 when the store is absent (the allowlist
        # cannot be derived). Either way it is refused before any sample SQL — never interpolated.
        status = getattr(excinfo.value, "status_code", None)
        assert status in (404, 422), (
            f"{name!r} is not inspectable and must be a clean rejection (404/422), not a query"
        )


# --- THE REJECT-UNKNOWN-KEYS HARDENING (store-independent) -----------------------------------
#
# The same fiduciary-surface input-validation hardening as navData (OIM-185): the request types are
# Pydantic models with extra="forbid", validated in the handler body, so an off-contract key is a
# clean 400. These need NO store.


def test_list_tables_unknown_key_is_terminal_400() -> None:
    """An off-contract key on listTables → TerminalError(400) (listTables takes no arguments)."""
    with pytest.raises(TerminalError) as excinfo:
        _list(FakeContext(), {"bogus": 1})
    assert getattr(excinfo.value, "status_code", None) == 400
    assert "invalid request" in str(excinfo.value).lower()


def test_sample_unknown_key_is_terminal_400() -> None:
    """An off-contract key on sampleTable → TerminalError(400), before any read."""
    with pytest.raises(TerminalError) as excinfo:
        _sample(FakeContext(), {"table": "main_marts.mart_fund_nav", "rogue": "x"})
    assert getattr(excinfo.value, "status_code", None) == 400
    assert "invalid request" in str(excinfo.value).lower()


def test_sample_non_dict_body_is_terminal_400() -> None:
    """A non-object body (a JSON array) to sampleTable → a clean terminal 400, not a 500."""
    with pytest.raises(TerminalError) as excinfo:
        _sample(FakeContext(), ["not", "an", "object"])
    assert getattr(excinfo.value, "status_code", None) == 400


# --- MALFORMED-BODY → CLEAN 400 (OIM-187: the serde never raises) ----------------------------
#
# Drive the FULL wire path on BOTH handlers — the shared ``PassThroughJsonSerde.deserialize`` over
# the raw bytes (must NOT raise) then the REAL handler over its result. A malformed-JSON / non-UTF8
# body → a clean ``TerminalError(400)``, never a status-less 500 — store-independent (the 400 fires
# before any read).


@pytest.mark.parametrize("body", [b"{bad", b'{"x":', b'"unterminated', b"\xff\xfe", b"\x80\x81"])
def test_list_tables_malformed_or_non_utf8_body_is_terminal_400(body: bytes) -> None:
    """listTables: a malformed-JSON / non-UTF8 body → a clean 400, never a 500."""
    deserialised = PassThroughJsonSerde().deserialize(body)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _list(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


@pytest.mark.parametrize("body", [b"{bad", b'{"x":', b'"unterminated', b"\xff\xfe", b"\x80\x81"])
def test_sample_malformed_or_non_utf8_body_is_terminal_400(body: bytes) -> None:
    """sampleTable: a malformed-JSON / non-UTF8 body → a clean 400, never a 500."""
    deserialised = PassThroughJsonSerde().deserialize(body)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _sample(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


# --- DEEP-NEST BODY → CLEAN 400 (OIM-187 cycle-2: the never-raise invariant is now structural) -
#
# A deeply-nested JSON body makes ``json.loads`` raise ``RecursionError`` (a ``RuntimeError``
# subclass, NOT a ``ValueError``) — the cycle-1 enumerated ``except`` tuple did NOT catch it → a
# status-less 500. The cycle-2 fold catches the WHOLE parse-failure class (``except Exception``) →
# the serde returns the raw text as a non-dict ``str`` the handler 400s. REVERT-SENSITIVE.

# A few-KB craftable payload: 20000 levels of nesting, well past the C scanner's depth budget.
DEEP_NEST_BODY = b"[" * 20000 + b"]" * 20000


def test_list_tables_deep_nest_body_is_terminal_400() -> None:
    """listTables: a deeply-nested JSON body → a clean 400, never a status-less 500."""
    deserialised = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _list(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


def test_sample_deep_nest_body_is_terminal_400() -> None:
    """sampleTable: a deeply-nested JSON body → a clean 400, never a status-less 500."""
    deserialised = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _sample(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


def test_serde_never_raises_on_deep_nest_body() -> None:
    """The structural never-raise invariant: a deep-nest body that trips ``RecursionError`` inside
    ``json.loads`` does NOT escape ``deserialize`` — it returns a (str) value. Revert-sensitive."""
    out = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise (was RecursionError)
    assert isinstance(out, str)


# --- integration: the real list + the real capped sample (need the store) -------------------


@pytest.mark.skipif(not _store_available(), reason="store not provisioned")
def test_list_tables_lists_marts_and_staging_with_counts() -> None:
    """listTables returns the real marts + realised staging entities, each with a row count."""
    out = _list(FakeContext(), {})
    assert out["computedBy"] == "python:canonicalData"
    names = {t["name"] for t in out["tables"]}
    # The three published marts are present.
    assert "main_marts.mart_fund_nav" in names
    assert "main_marts.mart_portfolio_holdings" in names
    assert "main_marts.mart_performance_appraisal" in names
    # At least one realised staging entity is present.
    assert any(
        t["layer"] == "staging" and t["name"].startswith("main_staging.stg_")
        for t in out["tables"]
    )
    # Every table carries a non-negative integer row count and a known layer.
    for t in out["tables"]:
        assert isinstance(t["rowCount"], int) and t["rowCount"] >= 0
        assert t["layer"] in ("mart", "staging")


@pytest.mark.skipif(not _store_available(), reason="store not provisioned")
def test_sample_table_returns_capped_headers_and_rows() -> None:
    """sampleTable returns the headers + a capped sample of REAL rows for an allowed table."""
    out = _sample(FakeContext(), {"table": "main_marts.mart_fund_nav"})
    assert out["name"] == "main_marts.mart_fund_nav"
    assert out["computedBy"] == "python:canonicalData"
    assert "fund_id" in out["columns"]
    # The sample is capped and never exceeds the row count.
    assert out["limit"] <= SAMPLE_LIMIT_MAX
    assert out["sampled"] == len(out["rows"])
    assert out["sampled"] <= out["rowCount"]
    # Each row has one cell per column.
    for row in out["rows"]:
        assert len(row) == len(out["columns"])


@pytest.mark.skipif(not _store_available(), reason="store not provisioned")
def test_sample_table_clamps_limit_to_cap() -> None:
    """A limit above the cap is clamped to SAMPLE_LIMIT_MAX (never an uncapped dump)."""
    out = _sample(FakeContext(), {"table": "main_staging.stg_e01_legal_entity", "limit": 9999})
    assert out["limit"] == SAMPLE_LIMIT_MAX
    assert out["sampled"] <= SAMPLE_LIMIT_MAX
