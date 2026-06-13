"""The ``pyTools`` Restate service handler — the WIRE path the TS orchestrator reaches.

These tests drive the ``pyTools`` ``computeSimpleReturn`` HANDLER through a faithful fake
``restate.Context`` — the same cross-language RPC seam a TS orchestrator handler invokes over the
ingress. The load-bearing addition: the reject-unknown-keys hardening.

The request contract ``SimpleReturnInputDict`` was a bare ``TypedDict`` (the same class as the
``navData`` / ``argResolver`` gaps) — a ``TypedDict`` does NOT reject extra keys at runtime, so an
off-contract key was silently ignored. It is now a Pydantic model with ``extra="forbid"``,
validated IN THE HANDLER BODY, so an unrecognised key is a clean ``TerminalError`` (400) on the
wire. These tests prove the rejection on the wire AND that the valid contract keys still compute.

Honest boundary: a DEFENSIVE input-validation hardening — the real contract fields were already
enforced; this closes the silent-mis-key class (an unknown key now fails loud).
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
import restate
from restate.exceptions import TerminalError

from agentinvest_tools.py_tools_service import compute_simple_return_handler
from agentinvest_tools.request_serde import PassThroughJsonSerde


class FakeContext:
    """A faithful stand-in for ``restate.Context``: ``run(name, action)`` invokes the action and
    propagates its value/exception unchanged — the same seam the TS orchestrator reaches."""

    def __init__(self) -> None:
        self.steps: list[str] = []

    async def run(self, name: str, action: Any, *args: Any, **kwargs: Any) -> Any:
        self.steps.append(name)
        result = action()
        if asyncio.iscoroutine(result):
            result = await result
        return result


def _compute(ctx: FakeContext, req: Any) -> Any:
    """Drive the ``computeSimpleReturn`` HANDLER (the wire path) — not a helper function."""
    return asyncio.run(compute_simple_return_handler(cast(restate.Context, ctx), req))


def test_valid_request_computes_on_the_wire() -> None:
    """A valid request through the HANDLER computes the simple return (valid keys still work)."""
    out = _compute(
        FakeContext(),
        {"beginningValue": 100.0, "endingValue": 110.0, "cashFlow": 0.0},
    )
    assert out["computedBy"] == "python:pyTools"
    # (110 - 100 - 0) / 100 == 0.10
    assert out["simpleReturn"] == pytest.approx(0.10)
    assert out["echo"] == {"beginningValue": 100.0, "endingValue": 110.0, "cashFlow": 0.0}


def test_unknown_key_is_terminal_400_on_the_wire() -> None:
    """An off-contract key on computeSimpleReturn → TerminalError(400) on the wire, not ignored.

    The reject-unknown-keys hardening: a bare ``TypedDict`` would have silently dropped the extra
    key; the Pydantic ``extra="forbid"`` model validated in the handler body fails loud.
    """
    with pytest.raises(TerminalError) as excinfo:
        _compute(
            FakeContext(),
            {"beginningValue": 100.0, "endingValue": 110.0, "cashFlow": 0.0, "bogus": 1},
        )
    assert getattr(excinfo.value, "status_code", None) == 400
    assert "invalid request" in str(excinfo.value).lower()


def test_non_dict_body_is_terminal_400_on_the_wire() -> None:
    """A non-object body to the handler → a clean terminal 400, never a 500."""
    with pytest.raises(TerminalError) as excinfo:
        _compute(FakeContext(), [1, 2, 3])
    assert getattr(excinfo.value, "status_code", None) == 400


# --- MALFORMED-BODY → CLEAN 400 (the serde never raises) -------------------------------------
#
# Drive the FULL wire path — the shared ``PassThroughJsonSerde.deserialize`` over the RAW BYTES
# first (the transport-body parse the SDK runs), then the REAL handler over its result. A malformed
# JSON / non-UTF8 body must never raise out of the serde (the SDK would re-wrap it as a status-less
# 500); the serde returns a non-dict ``str`` the handler's ``_coerce_request`` rejects as a clean
# ``TerminalError(400)``.


@pytest.mark.parametrize("body", [b"{bad", b'{"x":', b'"unterminated', b"\xff\xfe", b"\x80\x81"])
def test_malformed_or_non_utf8_body_is_terminal_400_on_the_wire(body: bytes) -> None:
    """A malformed-JSON or non-UTF8 transport body → a clean terminal 400, never a 500/uncaught."""
    deserialised = PassThroughJsonSerde().deserialize(body)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _compute(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


def test_serde_never_raises_on_any_body() -> None:
    """The pass-through invariant: ``deserialize`` returns a value for every body, never raises."""
    serde = PassThroughJsonSerde()
    assert serde.deserialize(b"") == {}
    assert serde.deserialize(b'{"beginningValue": 1.0}') == {"beginningValue": 1.0}
    assert serde.deserialize(b"{bad") == "{bad"  # malformed → raw str
    assert isinstance(serde.deserialize(b"\xff\xfe"), str)  # non-UTF8 → decoded str (replace)
    assert serde.deserialize(b"[1,2,3]") == [1, 2, 3]  # valid non-dict → passed through


# --- DEEP-NEST BODY → CLEAN 400 (the never-raise invariant is structural) --------------------
#
# A deeply-nested JSON body makes ``json.loads`` raise ``RecursionError`` (a ``RuntimeError``
# subclass, NOT a ``ValueError``) — an enumerated ``except`` tuple would not catch it, so it would
# escape ``deserialize`` → the SDK would re-wrap it as a status-less 500 (surviving via the
# recursion-limit parse path). Catching the WHOLE parse-failure class (``except Exception``), so the
# serde returns the raw text as a non-dict ``str`` the handler's ``_coerce_request`` rejects as a
# clean 400. These tests are REVERT-SENSITIVE: re-narrowing the catch back to the narrow
# ``(JSONDecodeError, ValueError, UnicodeDecodeError)`` tuple makes the deep-nest body raise
# ``RecursionError`` out of ``deserialize`` again → RED.

# A few-KB craftable payload: 20000 levels of nesting, well past the C scanner's depth budget.
DEEP_NEST_BODY = b"[" * 20000 + b"]" * 20000


def test_deep_nest_body_is_terminal_400_on_the_wire() -> None:
    """computeSimpleReturn: a deeply-nested JSON body → a clean 400, never a status-less 500."""
    deserialised = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _compute(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


def test_serde_never_raises_on_deep_nest_body() -> None:
    """The structural never-raise invariant: a deep-nest body that trips ``RecursionError`` inside
    ``json.loads`` does NOT escape ``deserialize`` — it returns a (str) value. Revert-sensitive."""
    out = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise (was RecursionError)
    assert isinstance(out, str)  # the raw decoded text — a non-dict the handler 400s
