"""The ``bd09`` model-free Restate dispatch service — dispatch, envelope-mapping, classification.

Covers the load-bearing properties of OIM-113:

- **registry dispatch** — each of the five SD-09.1 SOs is registered, invocable via ``execute_so``,
  and appears in ``list_capabilities`` with its *real* Pydantic schema (not a stub);
- **envelope-mapping** — ``args`` maps onto each tool's ``extra="forbid"`` Pydantic input; an
  unknown/extra/missing/mistyped argument is rejected;
- **error classification (the load-bearing one)** — every deterministic failure (unknown so_id,
  bad/extra/missing args, the non-conventional-cash-flow fail-loud, an undefined-result compute
  error) is a ``restate.TerminalError`` so Restate does **not** retry it. The no-retry property is
  proven structurally: a deterministic failure must escape the journaled step as a ``TerminalError``
  (terminal) and **never** as a plain exception (which the SDK would retry).

The journaling step is exercised through a faithful fake ``Context`` whose ``run(name, action)``
invokes the action and propagates its result/exception exactly as the SDK does — the SDK turns a
``TerminalError`` escaping ``ctx.run`` into a terminal failure and any *other* escaping exception
into a *retried* transient failure (see ``create_run_coroutine`` in the SDK). So "the dispatch
classifies a deterministic error as terminal" is exactly "a ``TerminalError`` (not a bare
exception) escapes the journaled action" — which these tests assert directly. The end-to-end
journaling through the real Restate server is proven separately (see the report's Restate evidence).
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, cast

import pytest
import restate
from restate.exceptions import TerminalError

from agentinvest_tools.bd09_service import (
    _REGISTRY,
    BD09_SERVICE_NAME,
    ExecuteSoInput,
    ExecuteSoOutput,
    ListCapabilitiesOutput,
    execute_so,
    list_capabilities,
)


class FakeContext:
    """A faithful stand-in for ``restate.Context`` for the service handlers.

    ``run(name, action)`` records the journaled step name and invokes the action, returning its
    value and propagating any exception unchanged — mirroring how the real SDK runs a ``ctx.run``
    action. It deliberately does NOT catch exceptions: a deterministic failure that the dispatch
    layer failed to classify as terminal would escape here as a bare exception, which is exactly
    the (retried-by-Restate) failure mode the tests assert never happens.
    """

    def __init__(self) -> None:
        self.steps: list[str] = []

    async def run(self, name: str, action: Any, *args: Any, **kwargs: Any) -> Any:
        self.steps.append(name)
        result = action()
        if asyncio.iscoroutine(result):
            result = await result
        return result


def _exec(ctx: FakeContext, req: Any) -> ExecuteSoOutput:
    """Drive ``execute_so`` with the fake context (cast to the SDK ``Context`` for typing)."""
    return asyncio.run(execute_so(cast(restate.Context, ctx), cast(ExecuteSoInput, req)))


def _list(ctx: FakeContext) -> ListCapabilitiesOutput:
    """Drive ``list_capabilities`` with the fake context."""
    return asyncio.run(list_capabilities(cast(restate.Context, ctx)))


# --- registry / catalogue ----------------------------------------------------


def test_registry_holds_the_five_bd09_sos() -> None:
    assert sorted(_REGISTRY) == [
        "SO-09-01",
        "SO-09-02",
        "SO-09-03",
        "SO-09-04",
        "SO-09-05",
    ]


def test_list_capabilities_returns_five_with_real_schemas() -> None:
    out = _list(FakeContext())
    assert out["service"] == BD09_SERVICE_NAME
    caps = out["capabilities"]
    assert [c["soId"] for c in caps] == [
        "SO-09-01",
        "SO-09-02",
        "SO-09-03",
        "SO-09-04",
        "SO-09-05",
    ]
    for cap in caps:
        # Real Pydantic schemas, not stubs: each carries named properties matching the tool model.
        assert cap["name"]
        assert cap["summary"]
        assert cap["inputSchema"]["type"] == "object"
        assert cap["inputSchema"]["properties"], f"{cap['soId']} input schema has no properties"
        assert cap["outputSchema"]["type"] == "object"
        assert cap["outputSchema"]["properties"], f"{cap['soId']} output schema has no properties"

    # Spot-check one schema names the real tool fields (proves it is not a placeholder).
    total_return = next(c for c in caps if c["soId"] == "SO-09-01")
    assert "beginning_value" in total_return["inputSchema"]["properties"]
    assert "total_return" in total_return["outputSchema"]["properties"]


# --- each of the five SOs invocable via execute_so ---------------------------


def test_so_09_01_total_return_via_execute_so() -> None:
    ctx = FakeContext()
    out = _exec(
        ctx,
        {
            "soId": "SO-09-01",
            "args": {
                "beginning_value": "100",
                "ending_value": "300",
                "period_days": 100,
                "cash_flows": [{"day": 50, "amount": "50"}],
            },
        },
    )
    # The Modified Dietz worked example: gain 150 / average capital 125 = 120%.
    assert Decimal(out["result"]["total_return"]) == Decimal("1.2")
    assert out["provenance"]["soId"] == "SO-09-01"
    assert out["provenance"]["tool"] == "compute_total_return"
    assert out["provenance"]["methodology"] == "modified-dietz"
    assert out["computedBy"] == f"python:{BD09_SERVICE_NAME}"
    # The tool call was a journaled step keyed by the so_id.
    assert ctx.steps == ["so-SO-09-01"]


def test_so_09_02_time_weighted_return_via_execute_so() -> None:
    out = _exec(
        FakeContext(),
        {
            "soId": "SO-09-02",
            "args": {
                "sub_periods": [
                    {"sub_period_return": "0.07"},
                    {"sub_period_return": "0.049057"},
                ]
            },
        },
    )
    # (1.07)(1.049057) - 1 ~= 0.1224 published TWR.
    assert abs(Decimal(out["result"]["time_weighted_return"]) - Decimal("0.1224")) <= Decimal(
        "0.0001"
    )
    assert out["provenance"]["methodology"] == "true-time-weighted"


def test_so_09_03_money_weighted_return_via_execute_so() -> None:
    out = _exec(
        FakeContext(),
        {
            "soId": "SO-09-03",
            "args": {
                "cash_flows": [
                    {"time": "0", "amount": "-10000"},
                    {"time": "1", "amount": "-5000"},
                    {"time": "2", "amount": "25000"},
                ]
            },
        },
    )
    # Published IRR ~= 35.08%.
    assert abs(Decimal(out["result"]["money_weighted_return"]) - Decimal("0.3508")) <= Decimal(
        "0.0001"
    )
    assert out["provenance"]["methodology"] == "money-weighted-irr"


def test_so_09_04_benchmark_relative_return_via_execute_so() -> None:
    out = _exec(
        FakeContext(),
        {
            "soId": "SO-09-04",
            "args": {"portfolio_return": "0.12", "benchmark_return": "0.10"},
        },
    )
    assert Decimal(out["result"]["active_return"]) == Decimal("0.02")
    assert out["provenance"]["methodology"] == "arithmetic-excess"


def test_so_09_05_contribution_breakdown_via_execute_so() -> None:
    out = _exec(
        FakeContext(),
        {
            "soId": "SO-09-05",
            "args": {
                "segments": [
                    {"segment": "equity", "weight": "0.6", "segment_return": "0.10"},
                    {"segment": "bonds", "weight": "0.4", "segment_return": "0.05"},
                ]
            },
        },
    )
    # 0.6*0.10 + 0.4*0.05 = 0.08.
    assert Decimal(out["result"]["total_return"]) == Decimal("0.08")
    assert out["provenance"]["methodology"] == "contribution-weight-times-return"


# --- error classification: deterministic failures are TerminalError (no retry) ---
#
# The load-bearing class. The Restate SDK retries a *plain* exception escaping a ctx.run step
# (it treats it as transient) and does NOT retry a TerminalError. So a deterministic input error
# left unclassified would retry forever — a hang/cost landmine. Every case below must raise
# TerminalError, NOT a bare ValueError/ValidationError.


# --- the envelope-type guard: a non-dict body is terminal (the ingress completion) -------------
#
# A malformed body that is not a JSON object — a top-level array, string, number or null — is a
# deterministic input error: a raw ``req.get`` on it raises AttributeError *outside* the journaled
# ctx.run step, escapes the compute catch, and (because it is not a TerminalError) is classified
# transient and RETRIED by Restate (a bounded-retry hang on a body that re-sending cannot fix). The
# guard must make every non-dict body a TerminalError at the ingress, never a retry. On the real
# Restate ingress the typed ``ExecuteSoInput`` envelope already rejects a non-object body at
# deserialise (also terminal); these tests assert the in-handler guard directly via the FakeContext
# (which bypasses the SDK serde), exercising the programmatic path.


@pytest.mark.parametrize(
    "bad_body",
    [
        pytest.param([1, 2, 3], id="json-array"),
        pytest.param("just-a-string", id="json-string"),
        pytest.param(42, id="json-number"),
        pytest.param(None, id="json-null"),
        pytest.param(True, id="json-bool"),
    ],
)
def test_non_dict_envelope_is_terminal_not_retried(bad_body: Any) -> None:
    """A non-dict request body → TerminalError (400) at the ingress, NOT a bare exception.

    A bare AttributeError escaping here is exactly what Restate would retry — so the assertion that
    a TerminalError (and nothing else) is raised IS the no-retry proof for the malformed-envelope
    class. Mirrors the deterministic-error-is-terminal proof one layer up (the compute class), now
    closed at the pre-dispatch envelope path.
    """
    with pytest.raises(TerminalError, match="must be a JSON object"):
        _exec(FakeContext(), bad_body)


@pytest.mark.parametrize("body", [b"{bad", b'{"x":', b'"unterminated', b"\xff\xfe", b"\x80\x81"])
def test_malformed_or_non_utf8_envelope_is_terminal_400(body: bytes) -> None:
    """A malformed-JSON / non-UTF8 body to execute_so → a clean 400, never a status-less 500.

    OIM-187 consistency fix: ``ExecuteSoEnvelopeSerde.deserialize`` previously let a malformed body
    raise (a status-less 500); it now catches the parse failure and returns the raw decoded text as
    a ``str`` that ``_coerce_envelope`` rejects as a clean 400 via its existing non-dict branch —
    the same status as the pass-through handlers, while bd09's envelope contract stays its own (not
    the shared serde).
    """
    from agentinvest_tools.bd09_service import ExecuteSoEnvelopeSerde

    deserialised = ExecuteSoEnvelopeSerde().deserialize(body)  # must NOT raise
    with pytest.raises(TerminalError, match="must be a JSON object"):
        _exec(FakeContext(), deserialised)


# --- DEEP-NEST BODY → CLEAN 400 (OIM-187 cycle-2: the never-raise invariant is now structural) -
#
# A deeply-nested JSON body makes ``json.loads`` raise ``RecursionError`` (a ``RuntimeError``
# subclass, NOT a ``ValueError``) — the cycle-1 enumerated ``except`` tuple in
# ``ExecuteSoEnvelopeSerde`` did NOT catch it, so it escaped → a status-less 500 on ``execute_so``.
# The cycle-2 fold catches the WHOLE parse-failure class (``except Exception``) → the serde returns
# the raw text as a non-dict ``str`` that ``_coerce_envelope`` rejects as a clean 400.
# REVERT-SENSITIVE: re-narrowing the catch makes the deep-nest body raise out of ``deserialize``.

# A few-KB craftable payload: 20000 levels of nesting, well past the C scanner's depth budget.
DEEP_NEST_BODY = b"[" * 20000 + b"]" * 20000


def test_deep_nest_envelope_is_terminal_400() -> None:
    """execute_so: a deeply-nested JSON body → a clean 400, never a status-less 500."""
    from agentinvest_tools.bd09_service import ExecuteSoEnvelopeSerde

    deserialised = ExecuteSoEnvelopeSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise
    with pytest.raises(TerminalError, match="must be a JSON object"):
        _exec(FakeContext(), deserialised)


def test_envelope_serde_never_raises_on_deep_nest_body() -> None:
    """The structural never-raise invariant on bd09's envelope serde: a deep-nest body that trips
    ``RecursionError`` inside ``json.loads`` does NOT escape ``deserialize``. Revert-sensitive."""
    from agentinvest_tools.bd09_service import ExecuteSoEnvelopeSerde

    out = ExecuteSoEnvelopeSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise (RecursionError)
    assert isinstance(out, str)


def test_typed_execute_so_input_envelope_round_trips() -> None:
    """The typed ``ExecuteSoInput`` envelope (a Pydantic model) dispatches like a dict.

    The Restate ingress deserialises the JSON body into this model; the handler must accept it. This
    proves the typed-envelope path (which the OpenAPI/MCP surface generates from) and the dict path
    are equivalent.
    """
    from agentinvest_tools.bd09_service import ExecuteSoInput

    out = _exec(
        FakeContext(),
        ExecuteSoInput(
            soId="SO-09-04",
            args={"portfolio_return": "0.12", "benchmark_return": "0.10"},
        ),
    )
    assert Decimal(out["result"]["active_return"]) == Decimal("0.02")


def test_execute_so_input_schema_is_typed_for_the_surface() -> None:
    """The envelope model produces a real JSON Schema (so the generated surface types the envelope).

    The carried-forward residual was an *untyped* envelope: a non-object body slipped past to an
    AttributeError. The typed envelope's schema names ``soId``/``args`` and is an object — this is
    what the auto-generated OpenAPI request schema becomes.
    """
    from agentinvest_tools.bd09_service import ExecuteSoInput

    schema = ExecuteSoInput.model_json_schema()
    assert schema["type"] == "object"
    assert "soId" in schema["properties"]
    assert "args" in schema["properties"]
    assert "soId" in schema["required"]


# --- the envelope-schema guard: the published additionalProperties:false / soId-string enforced ---
#
# P-MINOR-1 (cycle-1 pre-mortem): the auto-generated execute_soRequest schema advertises
# additionalProperties:false (ExecuteSoInput's extra="forbid") + soId as a required STRING, but the
# permissive pass-through serde let an extra-top-level-key / non-string-soId envelope through with
# HTTP 200 — the published contract lied. _coerce_envelope now validates the raw dict through
# ExecuteSoInput.model_validate in the HANDLER BODY (not the serde — that would re-wrap as a 500),
# so a malformed-but-dict envelope is terminal 400, aligning the runtime with the published schema.


def test_extra_top_level_envelope_key_is_terminal_400() -> None:
    """An extra top-level envelope key → terminal 400 (was HTTP 200 at the cycle-1 baseline).

    The published schema carries ``additionalProperties: false``; the runtime now enforces it via
    ``ExecuteSoInput`` (``extra="forbid"``), so a conforming external agent reading the schema and a
    stray-key body now agree — the contract no longer lies.
    """
    with pytest.raises(TerminalError, match="invalid request envelope"):
        _exec(
            FakeContext(),
            {
                "soId": "SO-09-04",
                "args": {"portfolio_return": "0.12", "benchmark_return": "0.10"},
                "rogue": 1,
            },
        )


def test_non_string_so_id_is_terminal_400() -> None:
    """A non-string ``soId`` → terminal 400 (the schema advertises ``soId`` as a string).

    At the cycle-1 baseline a numeric ``soId`` slipped past the envelope and missed the registry as
    a 404 ("unknown SO 'None'"); the schema-typed enforcement now rejects it at the envelope as a
    clear 400, matching the published ``soId: string`` constraint.
    """
    with pytest.raises(TerminalError, match="invalid request envelope"):
        _exec(FakeContext(), {"soId": 123, "args": {}})


def test_valid_envelope_still_round_trips_200() -> None:
    """A valid, schema-conforming envelope is unaffected by the schema guard — it still computes."""
    out = _exec(
        FakeContext(),
        {"soId": "SO-09-04", "args": {"portfolio_return": "0.12", "benchmark_return": "0.10"}},
    )
    assert Decimal(out["result"]["active_return"]) == Decimal("0.02")
    assert out["provenance"]["soId"] == "SO-09-04"


def test_unknown_so_id_is_terminal() -> None:
    with pytest.raises(TerminalError, match="unknown Service Operation"):
        _exec(FakeContext(), {"soId": "SO-99-99", "args": {}})


def test_missing_so_id_is_terminal() -> None:
    """A missing ``soId`` is now an envelope-schema violation → terminal 400.

    The published ``execute_soRequest`` schema requires ``soId``; ``_coerce_envelope`` enforces it
    through ``ExecuteSoInput.model_validate``, so a body with no ``soId`` is a clear
    ``ValidationError`` → ``TerminalError`` (400) at the envelope, not a downstream 404 on a
    ``None`` lookup. Still terminal (no retry) — only the diagnostic and status sharpen.
    """
    with pytest.raises(TerminalError, match="invalid request envelope"):
        _exec(FakeContext(), {"args": {}})


def test_extra_arg_is_terminal_not_retryable() -> None:
    """An unknown arg (extra='forbid' on the tool input) → TerminalError, never a bare exception."""
    with pytest.raises(TerminalError, match="invalid arguments"):
        _exec(
            FakeContext(),
            {
                "soId": "SO-09-01",
                "args": {
                    "beginning_value": "100",
                    "ending_value": "300",
                    "period_days": 100,
                    "bogus_extra": 1,
                },
            },
        )


def test_missing_required_arg_is_terminal() -> None:
    with pytest.raises(TerminalError, match="invalid arguments"):
        _exec(
            FakeContext(),
            {"soId": "SO-09-01", "args": {"beginning_value": "100"}},
        )


def test_mistyped_arg_is_terminal() -> None:
    with pytest.raises(TerminalError, match="invalid arguments"):
        _exec(
            FakeContext(),
            {
                "soId": "SO-09-01",
                "args": {
                    "beginning_value": "not-a-number",
                    "ending_value": "300",
                    "period_days": 100,
                },
            },
        )


def test_non_conventional_irr_is_terminal_no_retry() -> None:
    """THE load-bearing proof — a non-conventional cash-flow series fails FAST and TERMINAL.

    ``-1000, +6000, -11000, +6000`` has three sign changes (three real IRRs). The OIM-112 tool
    fails loud with ``NonConventionalCashFlowError``; the dispatch service classifies it as a
    ``TerminalError`` so Restate does NOT retry it. A bare exception escaping here would be retried
    forever by Restate (a hang/cost landmine on a deterministic input) — so the assertion that a
    ``TerminalError`` (and nothing else) is raised IS the no-retry proof.
    """
    with pytest.raises(TerminalError) as excinfo:
        _exec(
            FakeContext(),
            {
                "soId": "SO-09-03",
                "args": {
                    "cash_flows": [
                        {"time": "0", "amount": "-1000"},
                        {"time": "1", "amount": "6000"},
                        {"time": "2", "amount": "-11000"},
                        {"time": "3", "amount": "6000"},
                    ]
                },
            },
        )
    # The error is terminal and names the fail-loud type + the non-conventional reason.
    assert "NonConventionalCashFlowError" in str(excinfo.value)
    assert "non-conventional" in str(excinfo.value)


def test_deterministic_compute_error_is_terminal() -> None:
    """A conventional series whose IRR is outside the supported bracket → terminal, not retried.

    ``-1, +102`` is conventional (one sign change) but its IRR (10,100%) is above the solver
    bracket, so the tool raises a plain ValueError ('not bracketed'). It must be classified
    terminal, not left to retry.
    """
    with pytest.raises(TerminalError, match="not bracketed"):
        _exec(
            FakeContext(),
            {
                "soId": "SO-09-03",
                "args": {
                    "cash_flows": [
                        {"time": "0", "amount": "-1"},
                        {"time": "1", "amount": "102"},
                    ]
                },
            },
        )


# A conventional (one sign change) but long-dated series: at the solver's lower bracket
# (1 + rate) = 1e-6 underflows to 0.0 for a large time exponent, so the tool raises a
# *ZeroDivisionError* — a deterministic compute failure that is NOT a ValueError. This is the exact
# real-shaped private-markets series (a single long-dated distribution) that escaped the cycle-1
# narrow ``except ValueError`` into an unbounded Restate retry storm.
_ZERO_DIVISION_LONG_DATED_CALL: dict[str, Any] = {
    "soId": "SO-09-03",
    "args": {
        "cash_flows": [
            {"time": "0", "amount": "-1000"},
            {"time": "5000", "amount": "1000000000"},
        ]
    },
}

# Extreme-magnitude direct sub-period returns whose geometric product overflows the Decimal context:
# the tool raises a *decimal.Overflow* (a subclass of ArithmeticError) — again a deterministic
# compute failure that is NOT a ValueError, the second member of the class P named.
_DECIMAL_OVERFLOW_CALL: dict[str, Any] = {
    "soId": "SO-09-02",
    "args": {
        "sub_periods": [
            {"sub_period_return": "1E+500000000"},
            {"sub_period_return": "1E+500000000"},
        ]
    },
}


def test_no_deterministic_failure_escapes_as_bare_exception() -> None:
    """Sweep the deterministic-error *class*: every failing input raises TerminalError, never a bare
    exception. A bare exception escaping ctx.run is exactly what Restate retries — so this is the
    class-level no-retry guarantee. The class is not only the ValueError-shaped failures (bad args,
    the non-conventional IRR) but every deterministic compute exception type, including the
    non-ValueError modes — a ZeroDivisionError (a conventional long-dated series underflowing the
    IRR bracket) and a decimal.Overflow (extreme-magnitude inputs). This test FAILS against a narrow
    ``except ValueError`` (those two escape) and PASSES against the whole-class
    ``except Exception``.
    """
    failing_calls: list[dict[str, Any]] = [
        {"soId": "SO-99-99", "args": {}},  # unknown so_id
        {"soId": "SO-09-01", "args": {"beginning_value": "100", "bad": 1}},  # extra arg
        {"soId": "SO-09-01", "args": {"beginning_value": "100"}},  # missing args
        # non-conventional IRR (a ValueError subclass — caught even by the narrow catch)
        {
            "soId": "SO-09-03",
            "args": {
                "cash_flows": [
                    {"time": "0", "amount": "-1000"},
                    {"time": "1", "amount": "6000"},
                    {"time": "2", "amount": "-11000"},
                    {"time": "3", "amount": "6000"},
                ]
            },
        },
        _ZERO_DIVISION_LONG_DATED_CALL,  # ZeroDivisionError — NOT a ValueError
        _DECIMAL_OVERFLOW_CALL,  # decimal.Overflow — NOT a ValueError
    ]
    for call in failing_calls:
        try:
            _exec(FakeContext(), call)
        except TerminalError:
            pass  # correct — terminal, Restate will not retry
        except BaseException as exc:  # noqa: BLE001 - the whole point is to catch a non-terminal leak
            pytest.fail(
                f"deterministic failure for {call['soId']} escaped as {type(exc).__name__} "
                f"(not TerminalError) — Restate would RETRY this: {exc}"
            )
        else:
            pytest.fail(f"expected a TerminalError for {call['soId']}, none raised")


def test_zero_division_long_dated_series_is_terminal() -> None:
    """A conventional (one-sign-change) long-dated cash-flow series — the real-shaped
    private-markets case — raises ZeroDivisionError in the IRR solver, NOT a ValueError. It must be
    classified terminal (no retry), with the underlying type named in the diagnostic. (Against the
    cycle-1 narrow ``except ValueError`` this ZeroDivisionError escaped ctx.run and Restate retried
    it unboundedly — proven live in the cycle-1 pre-mortem; this locks the regression.)
    """
    with pytest.raises(TerminalError) as excinfo:
        _exec(FakeContext(), _ZERO_DIVISION_LONG_DATED_CALL)
    message = str(excinfo.value)
    assert "ZeroDivisionError" in message
    assert "SO-09-03" in message


def test_decimal_overflow_extreme_input_is_terminal() -> None:
    """Extreme-magnitude inputs overflow the Decimal context — a decimal.Overflow
    (ArithmeticError), NOT a ValueError — and must be classified terminal (no retry), the second
    non-ValueError deterministic mode the pre-mortem named.
    """
    with pytest.raises(TerminalError) as excinfo:
        _exec(FakeContext(), _DECIMAL_OVERFLOW_CALL)
    message = str(excinfo.value)
    assert "Overflow" in message
    assert "SO-09-02" in message
