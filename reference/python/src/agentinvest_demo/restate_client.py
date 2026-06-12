"""The demo's dispatch client — invokes a named Service Operation over the Restate substrate.

This is the **service / substrate** end of the pipeline. It POSTs the ``execute_so`` envelope
(``{"soId", "args"}``) to the ``bd09`` service over the Restate ingress — the same journaled,
terminal-error-classified path the MCP surface uses. It does **not** re-implement or locally
re-compute any tool: the figure comes back from the ``bd09`` service over the substrate, carrying
the service's provenance (``computedBy = python:bd09``) — that provenance is the demo's proof the
call round-tripped through the service over the substrate rather than being computed in-process.

Each call is wall-clock timed so the demo can report per-operation latency. A deterministic
failure (a bad argument, an unknown operation, a malformed envelope) comes back as a terminal
HTTP 4xx and is surfaced as a clear error, never a fabricated success.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

# The Restate ingress the journaled bd09 handlers are reachable on (the same default the MCP
# surface uses). Overridable for a non-default ingress port.
INGRESS_URL = os.environ.get("AGENTINVEST_RESTATE_INGRESS_URL", "http://localhost:8080")
BD09_SERVICE_NAME = "bd09"


class DispatchError(RuntimeError):
    """A Service-Operation dispatch failed — a terminal 4xx, a transport error, or a bad response.

    Carries the operation id and the underlying detail so the demo can surface what failed
    (a deterministic 4xx from the service is an input/envelope problem; a transport error means
    the substrate or the ``bd09`` registration is not reachable).
    """


@dataclass(frozen=True)
class ExecuteSoCall:
    """The result of one ``execute_so`` dispatch — the tool result, the provenance, the latency.

    ``computed_by`` is the service's provenance stamp (``python:bd09``); ``provenance`` is the
    ``{soId, tool, methodology}`` the service derived from the tool's own output. ``latency_s`` is
    the wall-clock round-trip time of this single call (the latency the demo reports + asserts).
    """

    so_id: str
    result: dict[str, Any]
    provenance: dict[str, Any]
    computed_by: str
    latency_s: float


@dataclass
class RestateDispatcher:
    """A thin client dispatching ``execute_so`` to the ``bd09`` service over the Restate ingress.

    Holds the ingress URL and an httpx client; ``execute_so`` POSTs one envelope and times the
    round-trip. ``ingress_healthy`` lets a caller (the CLI, a test) check the substrate + the
    ``bd09`` registration before running the task, so a missing substrate is a clear message
    rather than a dispatch error mid-pipeline.
    """

    ingress_url: str = INGRESS_URL
    timeout_s: float = 30.0

    def ingress_healthy(self) -> bool:
        """True iff the ``bd09`` service answers ``list_capabilities`` over the ingress.

        A successful ``list_capabilities`` proves the substrate is up AND the ``bd09`` service is
        registered (the two preconditions for the task). Used as the warm-up / readiness probe.
        """
        try:
            resp = httpx.post(
                f"{self.ingress_url}/{BD09_SERVICE_NAME}/list_capabilities",
                timeout=5.0,
            )
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def execute_so(self, so_id: str, args: dict[str, Any]) -> ExecuteSoCall:
        """Dispatch one named Service Operation to ``bd09.execute_so`` over the ingress, timed.

        POSTs ``{"soId": so_id, "args": args}``; a terminal 4xx (a deterministic input/envelope
        error classified by the service) or a transport failure is raised as ``DispatchError``.
        On success returns the typed result plus the service's provenance and the round-trip
        latency. The compute happens in the ``bd09`` service over the substrate — this client
        never re-runs the tool.
        """
        envelope = {"soId": so_id, "args": args}
        start = time.perf_counter()
        try:
            resp = httpx.post(
                f"{self.ingress_url}/{BD09_SERVICE_NAME}/execute_so",
                json=envelope,
                timeout=self.timeout_s,
            )
        except httpx.HTTPError as exc:
            raise DispatchError(
                f"{so_id}: could not reach the bd09 service at {self.ingress_url} — is the "
                f"substrate up and bd09 registered? ({exc})"
            ) from exc
        latency_s = time.perf_counter() - start

        if resp.status_code >= 400:
            raise DispatchError(
                f"{so_id}: bd09.execute_so returned terminal {resp.status_code}: {resp.text}"
            )

        payload = resp.json()
        provenance = payload.get("provenance", {})
        computed_by = str(payload.get("computedBy", ""))
        if computed_by != f"python:{BD09_SERVICE_NAME}":
            # The provenance is the proof the call went through the service over the substrate.
            # A missing/wrong stamp means the result did not come from the bd09 service path.
            raise DispatchError(
                f"{so_id}: result is missing the bd09 service provenance "
                f"(computedBy={computed_by!r}); the call did not round-trip through the service"
            )
        return ExecuteSoCall(
            so_id=so_id,
            result=payload["result"],
            provenance=provenance,
            computed_by=computed_by,
            latency_s=latency_s,
        )
