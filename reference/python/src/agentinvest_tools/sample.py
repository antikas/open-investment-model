"""Sample module for the Python workspace toolchain proof.

This module carries the canonical computation the cross-language RPC smoke test
exercises end-to-end: a simple (Dietz-style) period return. It is a *pure*
function with no Restate dependency so the unit test (pytest) can verify it
directly, and so the Restate service (py_tools_service.py) is a thin typed
wrapper over it. OIM-103+ replaces this sample with the real BD-09 return tools.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimpleReturnInput:
    """Inputs to a simple period-return computation.

    Mirrors the TS-side ``SimpleReturnInput`` in
    ``reference/ts/src/rpc/py-tools-contract.ts`` — the shared cross-language
    contract. Drift between the two is a contract break the smoke test catches.
    """

    beginning_value: float
    ending_value: float
    cash_flow: float


def compute_simple_return(inp: SimpleReturnInput) -> float:
    """Compute a simple (Dietz-style) period return as a decimal fraction.

    return = (ending - beginning - cash_flow) / (beginning + cash_flow)

    The external cash flow is treated as occurring at the start of the period
    (the simplest Dietz variant) so the denominator is the beginning value plus
    the flow. This is deliberately the textbook simple form — OIM-103 brings the
    modified-Dietz and time-weighted tools the model's BD-09 actually owns.
    """
    denominator = inp.beginning_value + inp.cash_flow
    if denominator == 0:
        raise ValueError("simple return undefined when (beginning_value + cash_flow) == 0")
    return (inp.ending_value - inp.beginning_value - inp.cash_flow) / denominator
