"""agentINVEST Python handler endpoint.

Serves the Python Restate services (``pyTools`` and the ``bd09`` per-Business-Domain
dispatch service) as an ASGI app (via hypercorn) and registers them against the
shared Restate so their handlers are invocable over the ingress. This is the Python
counterpart of the TS ``endpoint.ts``.

The Python endpoint listens on its OWN port (default 9091,
distinct from the TS endpoint's 9090) so the TS and Python deployments are two
separate registrations against the same Restate. On Windows this endpoint runs
INSIDE WSL2 (same network namespace as the Restate server), so Restate reaches
it over ``localhost`` — no WSL2 gateway-IP dance (that is only needed for the
Windows-host TS endpoint).

Run (inside WSL2 on Windows):
    uv run python -m agentinvest_tools.endpoint           # serve + register
    uv run python -m agentinvest_tools.endpoint --no-register
"""

from __future__ import annotations

import asyncio
import os
import sys
import urllib.request

import hypercorn.asyncio
import hypercorn.config
import restate

from agentinvest_orchestrator.service import agentinvestPlanner
from agentinvest_tools.arg_resolver_service import argResolver
from agentinvest_tools.bd09_service import bd09
from agentinvest_tools.bd12_recon_service import bd12Recon
from agentinvest_tools.bd12_service import bd12
from agentinvest_tools.canonical_data_service import canonicalData
from agentinvest_tools.entity_resolution_service import entityResolution
from agentinvest_tools.nav_data_service import navData
from agentinvest_tools.py_tools_service import py_tools

PY_ENDPOINT_PORT = int(os.environ.get("AGENTINVEST_PY_ENDPOINT_PORT", "9091"))
ADMIN_URL = os.environ.get("RESTATE_ADMIN_URL", "http://localhost:9070")
# Restate reaches this endpoint over localhost (same WSL2 network namespace).
DEPLOY_URL = os.environ.get("AGENTINVEST_PY_DEPLOY_URL", f"http://localhost:{PY_ENDPOINT_PORT}")

# agentinvestPlanner — the planning step's service, bound beside bd09. It is a
# model-free SERVICE hosting the one .plan() reasoning loop; the orchestrator calls
# its planTask handler at seam 1 over Restate RPC. The name is agentINVEST-scoped so
# it does not collide with a same-named sibling-project service on the shared dev Restate.
# navData — the NAV-strike workflow's marts-read seam, bound beside bd09. A
# model-free SERVICE: the TS navCalculation workflow calls its getFundNavComponents handler
# to read the per-fund §A1 NAV components from mart_fund_nav. Not an agent; no reasoning loop.
# argResolver — the orchestrator's abstract-arg → concrete-tool-input resolution seam,
# bound beside bd09/navData. A model-free SERVICE: the TS investmentOperation's resolve step calls
# its resolveStepArgs handler to derive the SO-09-01/05 concrete inputs from the marts (REUSING the
# shared marts-read derivation). Not an agent; no reasoning loop.
# canonicalData — the Operator UI inspector's read seam, bound beside navData. A
# model-free, READ-ONLY SERVICE: the Operator UI's Canonical-data inspector calls its listTables /
# sampleTable handlers to browse the dbt-built canonical layer (marts + realised staging entities)
# over the ingress (the Windows Next.js cannot read the WSL2-ext4 duckdb file directly).
# Allowlisted table names + a parameterised capped sample — no free-form SQL / no injection surface.
# bd12 — the BD-12 book-of-record READ service, bound beside bd09. A
# model-free, READ-ONLY SERVICE hosting the SD-12.1 IBOR + SD-12.2 ABOR read tools: each execute_so
# reads the canonical dual book via the book_of_record_data data-access layer at an as-of
# and shapes a typed result. Exposes the two books to BE reconciled; it does not reconcile
# them and writes nothing. Same execute_so / list_capabilities envelope as bd09. Not an agent.
# bd12Recon — the SD-12.10 RECONCILIATION service, bound beside bd12. A model-free SERVICE
# hosting the four reconcile tools (position · cash · transaction-matching · IBOR/ABOR): each
# execute_so reads the internal dual book (via book_of_record_data) AND the external comparator feed
# (via comparator_feed_data) at an as-of, runs the DUAL-INDEPENDENT-PIPELINE reconcile, classifies
# breaks DETERMINISTICALLY (no LLM), and persists E-24 break findings APPEND-ONLY to an
# engine-owned break store. It emits findings only — no correcting entry, no status transition, no
# gate (those live behind the breach gate). Same execute_so / list_capabilities envelope. Not an
# agent.
# entityResolution — the SD-13.2 ENTITY-RESOLUTION service, bound beside bd12Recon. A
# model-free SERVICE hosting the three resolution tools (resolve_batch · get_golden_record ·
# list_review_queue): resolve_batch reads the E-01 masters + the inbound entity feed (via
# entity_resolution_data), runs the DETERMINISTIC three-tier cascade (exact external-id ->
# name/alias
# key -> steward review queue — NO LLM), and persists golden records + quarantined records
# APPEND-ONLY
# to two engine-owned stores. The genuinely-ambiguous are quarantined, never force-merged (zero
# mis-merges is the cardinal floor). Same execute_so / list_capabilities envelope. Not an agent.
app = restate.app(
    services=[
        py_tools,
        bd09,
        agentinvestPlanner,
        navData,
        argResolver,
        canonicalData,
        bd12,
        bd12Recon,
        entityResolution,
    ]
)


def register_deployment(uri: str) -> str:
    """Register the Python endpoint with the shared Restate admin API."""
    body = f'{{"uri": "{uri}", "force": true}}'.encode()
    req = urllib.request.Request(  # noqa: S310 - loopback admin API, dev only
        f"{ADMIN_URL}/deployments",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        import json

        parsed = json.loads(resp.read().decode())
    deployment_id = parsed.get("id")
    if not deployment_id:
        raise RuntimeError(f"deployment register: response missing 'id': {parsed}")
    return str(deployment_id)


async def serve(register: bool = True) -> None:
    """Serve the Python endpoint; optionally register it, then hold open."""
    config = hypercorn.config.Config()
    config.bind = [f"0.0.0.0:{PY_ENDPOINT_PORT}"]

    shutdown = asyncio.Event()
    server_task = asyncio.create_task(
        hypercorn.asyncio.serve(app, config, shutdown_trigger=shutdown.wait)
    )
    # Let the listener bind before registering.
    await asyncio.sleep(0.5)
    sys.stderr.write(f"[agentinvest-py-endpoint] listening on 0.0.0.0:{PY_ENDPOINT_PORT}\n")

    if register:
        # Register in a thread executor: the admin's registration call discovers
        # the endpoint by calling BACK into it, so the serve loop MUST stay
        # responsive while we register. A synchronous register on this loop would
        # deadlock (loop blocked on the POST → discovery callback never served).
        loop = asyncio.get_running_loop()
        deployment_id = await loop.run_in_executor(None, register_deployment, DEPLOY_URL)
        sys.stderr.write(
            f"[agentinvest-py-endpoint] registered deployment {deployment_id} at {DEPLOY_URL}\n"
        )

    await server_task


def main() -> None:
    register = "--no-register" not in sys.argv
    try:
        asyncio.run(serve(register=register))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
