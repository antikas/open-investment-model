"""The typed Python Restate ``pyTools`` service — the cross-language RPC seam.

This is the Python counterpart of the shared contract declared on the TS side in
``reference/ts/src/rpc/py-tools-contract.ts``. A TypeScript orchestrator handler
invokes ``pyTools/computeSimpleReturn`` over Restate's typed RPC; the payload
round-trips as a typed structure. This is the load-bearing OIM-101 proof — every
later Python tool invoked from the TS orchestrator (OIM-103+) rides on it.

Topology (ADR-0054): ``pyTools`` is a model-free Restate *service* — a namespace
+ dispatch boundary in the Python tool+data layer — NOT an "agent". It carries no
reasoning loop. The single orchestrating loop is OIM-104.

The handler is a thin typed wrapper over the pure ``sample.compute_simple_return``
so the maths is unit-tested independently (tests/test_sample.py) and the service
layer only adds the Restate plumbing (a journaled ``ctx.run`` step).
"""

from __future__ import annotations

from typing import Any, TypedDict

import restate
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from restate.exceptions import TerminalError

from agentinvest_tools.request_serde import PassThroughJsonSerde
from agentinvest_tools.sample import SimpleReturnInput, compute_simple_return

PY_TOOLS_SERVICE_NAME = "pyTools"


class SimpleReturnInputDict(BaseModel):
    """Wire shape of the input — JSON keys mirror the TS ``SimpleReturnInput``.

    A **Pydantic model** with ``extra="forbid"`` (not a bare ``TypedDict``): an UNRECOGNISED
    request key is a clean ``TerminalError`` (400) at the handler, never silently ignored — the
    same fiduciary-surface reject-unknown-keys hardening applied to the ``navData`` /
    ``argResolver`` request contracts. All three keys are required (the contract mirrors the TS
    ``SimpleReturnInput`` exactly); only unrecognised keys now reject.
    """

    model_config = ConfigDict(extra="forbid")

    beginningValue: float = Field(description="The beginning value (required).")
    endingValue: float = Field(description="The ending value (required).")
    cashFlow: float = Field(description="The net external cash flow (required).")


class SimpleReturnResultDict(TypedDict):
    """Wire shape of the output — JSON keys mirror the TS ``SimpleReturnResult``."""

    simpleReturn: float
    computedBy: str
    echo: dict[str, float]


py_tools = restate.Service(PY_TOOLS_SERVICE_NAME)


def _coerce_request(req: Any) -> SimpleReturnInputDict:
    """Validate the raw request body against ``SimpleReturnInputDict`` (``extra="forbid"``), or 400.

    A valid body is either an already-built ``SimpleReturnInputDict`` (a typed-ingress path) or a
    plain ``dict`` (the pass-through-serde / unit-test path); the dict is validated through
    ``model_validate`` so an UNRECOGNISED request key is a clean ``TerminalError`` (400). Run in
    the HANDLER BODY (the SDK re-wraps a serde error as a status-less 500); the message is clean.
    """
    if isinstance(req, SimpleReturnInputDict):
        return req
    if not isinstance(req, dict):
        raise TerminalError(
            f"computeSimpleReturn: request body must be a JSON object — got {type(req).__name__}",
            status_code=400,
        )
    try:
        return SimpleReturnInputDict.model_validate(req)
    except ValidationError as exc:
        raise TerminalError(
            f"computeSimpleReturn: invalid request — {exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc


@py_tools.handler(name="computeSimpleReturn", input_serde=PassThroughJsonSerde())
async def compute_simple_return_handler(
    ctx: restate.Context, req: SimpleReturnInputDict
) -> SimpleReturnResultDict:
    """Compute a simple period return for the TS caller, over typed Restate RPC.

    The computation is wrapped in ``ctx.run`` so it is a journaled durable step —
    the same durable-execution property the TS placeholder proves, now exercised
    across the language boundary.

    An UNRECOGNISED request key is a clean ``TerminalError`` (400) before the compute (the
    reject-unknown-keys hardening); the valid contract keys are unchanged.
    """

    request = _coerce_request(req)

    def _compute() -> float:
        return compute_simple_return(
            SimpleReturnInput(
                beginning_value=request.beginningValue,
                ending_value=request.endingValue,
                cash_flow=request.cashFlow,
            )
        )

    simple_return = await ctx.run("compute-simple-return", _compute)

    return {
        "simpleReturn": simple_return,
        "computedBy": "python:pyTools",
        "echo": {
            "beginningValue": request.beginningValue,
            "endingValue": request.endingValue,
            "cashFlow": request.cashFlow,
        },
    }
