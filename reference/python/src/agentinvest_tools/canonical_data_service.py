"""The ``canonicalData`` Python Restate service — the Operator UI inspector's read seam.

The Operator UI's **Canonical-data inspector** (a read-only view of the dbt-built canonical
layer) cannot reach the WSL2-ext4 duckdb file directly from the Windows-host Next.js, so it reads
through this thin cross-language seam: the UI calls ``canonicalData/listTables`` and
``canonicalData/sampleTable`` over the Restate ingress, and these handlers read the canonical
store via the duckdb read utilities (``agentinvest_demo.canonical_inspect``).

Topology: ``canonicalData`` is a model-free Restate *service* — a namespace + dispatch
boundary in the Python tool+data layer — NOT an "agent". It carries no reasoning loop (the single
orchestrating loop is the planner's ``.plan()``). It is a pure read tool, the sibling of
``navData`` (the NAV-strike marts read).

READ-ONLY + NO INJECTION SURFACE (the load-bearing property, mirrored from the read util):
- ``listTables`` takes NO table input — it lists the marts + realised staging entities the store
  actually carries (derived from ``information_schema``), each with its row count.
- ``sampleTable`` takes a table name that is validated against the store-DERIVED allowlist before
  any sample SQL runs; an unknown / crafted / injection name is a clean ``TerminalError`` (404),
  never interpolated into SQL. The sample is a parameterised ``select * … limit <capped-int>`` —
  no free-form SQL from the client, ever. The cap is clamped to ``[1, 25]``.
- The store is opened ``read_only=True``; the handler never writes.

The reads are wrapped in ``ctx.run`` so each is a journaled durable step (replay reads the result
back, the store is not re-queried). The request types are Pydantic models with ``extra="forbid"``,
validated in the HANDLER body (the ``navData`` precedent), so an off-contract key is a clean 400 —
the same reject-unknown-keys hardening. SYNTHETIC data: the canonical layer is the
synthetic seed, not production data.
"""

from __future__ import annotations

from typing import Any, TypedDict

import restate
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from restate.exceptions import TerminalError

from agentinvest_demo.canonical_inspect import (
    SAMPLE_LIMIT_DEFAULT,
    UnknownTableError,
    list_canonical_tables,
    sample_canonical_table,
)
from agentinvest_demo.marts import MartsUnavailableError
from agentinvest_tools.request_serde import PassThroughJsonSerde

CANONICAL_DATA_SERVICE_NAME = "canonicalData"


class ListTablesRequest(BaseModel):
    """Wire shape of the list-tables request — it takes NO arguments (no injection surface).

    A Pydantic model with ``extra="forbid"`` (the ``navData`` precedent): ANY request key is
    rejected as a clean ``TerminalError`` (400). There is nothing to pass — the inspector lists
    the store's own canonical tables — so the empty object ``{}`` is the only valid body.
    """

    model_config = ConfigDict(extra="forbid")


class CanonicalTableWire(TypedDict):
    """One inspectable canonical table on the wire — its fq name, layer, and row count."""

    name: str
    schema: str
    table: str
    layer: str
    rowCount: int


class ListTablesResult(TypedDict):
    """The inspectable canonical tables (marts + realised staging entities) with row counts."""

    tables: list[CanonicalTableWire]
    computedBy: str


class SampleTableRequest(BaseModel):
    """Wire shape of the sample request — the table name (allowlisted) + an optional capped limit.

    ``table`` is required and is validated against the store-DERIVED allowlist in the handler
    (an unknown / crafted name is a clean 404 — never interpolated into SQL). ``limit`` is optional
    and clamped to ``[1, 25]`` by the read util regardless of what is passed. ``extra="forbid"``
    rejects any off-contract key (400).
    """

    model_config = ConfigDict(extra="forbid")

    table: str = Field(description="The fully-qualified canonical table to sample (allowlisted).")
    limit: int = Field(
        default=SAMPLE_LIMIT_DEFAULT,
        description="Optional row cap for the sample; clamped to [1, 25].",
    )


class SampleTableResult(TypedDict):
    """A capped sample of one canonical table — headers + ≤25 stringified rows + the counts."""

    name: str
    columns: list[str]
    rows: list[list[str | None]]
    rowCount: int  # the table's TOTAL row count
    sampled: int  # rows in THIS sample (≤ the cap)
    limit: int  # the effective cap applied
    computedBy: str


canonicalData = restate.Service(CANONICAL_DATA_SERVICE_NAME)


def _coerce_request[ModelT: BaseModel](
    req: Any, model: type[ModelT], handler_name: str
) -> ModelT:
    """Validate the raw request body against ``model`` (``extra="forbid"``), or fail terminal 400.

    The ``navData`` precedent: a valid body is either an already-built ``model`` instance or a
    plain ``dict`` (validated through ``model.model_validate`` so an unknown key is a clean 400);
    a non-dict body is a clean 400. Run in the HANDLER body (not the serde — the SDK re-wraps a
    serde error as a status-less 500); the message is kept clean of build cruft.
    """
    if isinstance(req, model):
        return req
    if not isinstance(req, dict):
        raise TerminalError(
            f"{handler_name}: request body must be a JSON object — got {type(req).__name__}",
            status_code=400,
        )
    try:
        return model.model_validate(req)
    except ValidationError as exc:
        raise TerminalError(
            f"{handler_name}: invalid request — {exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc


@canonicalData.handler(name="listTables", input_serde=PassThroughJsonSerde())
async def list_tables(ctx: restate.Context, req: ListTablesRequest) -> ListTablesResult:
    """List the inspectable canonical tables (marts + realised staging entities) with row counts.

    Takes no table input (no injection surface). The set is derived from the store's own catalogue,
    so it is the real, current table set. An unprovisioned store is a clean ``TerminalError`` (422).
    An off-contract request key is a clean 400 before the read. Wrapped in ``ctx.run`` (journaled).
    """
    _coerce_request(req, ListTablesRequest, "listTables")

    def _read() -> ListTablesResult:
        try:
            tables = list_canonical_tables()
        except MartsUnavailableError as exc:
            # A deterministic data condition (no store / no duckdb) — terminal so Restate does not
            # retry it; the UI surfaces it as the inspector being unavailable.
            raise TerminalError(str(exc), status_code=422) from exc
        return {
            "tables": [
                {
                    "name": t.name,
                    "schema": t.schema,
                    "table": t.table,
                    "layer": t.layer,
                    "rowCount": t.row_count,
                }
                for t in tables
            ],
            "computedBy": "python:canonicalData",
        }

    return await ctx.run("list-canonical-tables", _read)


@canonicalData.handler(name="sampleTable", input_serde=PassThroughJsonSerde())
async def sample_table(ctx: restate.Context, req: SampleTableRequest) -> SampleTableResult:
    """Read a CAPPED sample of one ALLOWLISTED canonical table — headers + ≤25 rows.

    The table name is validated against the store-derived allowlist FIRST: an unknown / crafted /
    injection name is a clean ``TerminalError`` (404) before any sample SQL — never interpolated.
    The sample is ``select * from <allowlisted> limit <clamped-int>`` (no free-form SQL; the cap
    is clamped to [1, 25]). An unprovisioned store is a 422; an off-contract key is a 400. Wrapped
    in ``ctx.run`` (journaled).
    """
    request = _coerce_request(req, SampleTableRequest, "sampleTable")
    table = request.table
    limit = request.limit

    def _read() -> SampleTableResult:
        try:
            s = sample_canonical_table(table, limit=limit)
        except UnknownTableError as exc:
            # An unknown / crafted / injection table name — REFUSED (404). Never interpolated into
            # SQL. This is the load-bearing read-only / no-injection boundary.
            raise TerminalError(str(exc), status_code=404) from exc
        except MartsUnavailableError as exc:
            raise TerminalError(str(exc), status_code=422) from exc
        return {
            "name": s.name,
            "columns": list(s.columns),
            "rows": [list(r) for r in s.rows],
            "rowCount": s.row_count,
            "sampled": s.sampled,
            "limit": s.limit,
            "computedBy": "python:canonicalData",
        }

    return await ctx.run("sample-canonical-table", _read)
