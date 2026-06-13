"""The ``entityResolution`` model-free Restate dispatch service — the SD-13.2 resolution boundary.

The SD-13.2 (Entity & Counterparty Master) entity-resolution Service Operation, made an invocable
service: a model-free Restate service hosting the three resolution tools (resolve-batch ·
get-golden-record · list-review-queue) and dispatching a *named* Service Operation to its tool as a
journaled durable step. It is the ``bd12_recon_service.py`` analogue — same ``execute_so`` /
``list_capabilities`` envelope shape — so the MCP/OpenAPI ingress and the orchestrator reach it
identically.

Service, not agent (the load-bearing topology point — ADR-0054). The per-SD layer is a **model-free
dispatch / tool-hosting boundary** that carries **no reasoning loop**. It routes a *named* SO to its
resolution tool; it does **not** decide which SO to call (that is the orchestrating ``.plan()``
loop). And it adds **NO LLM** — the resolution decision is the deterministic three-tier cascade
(``entity_resolution.cascade``); the probabilistic / LLM-proposer tier is a deliberately-deferred
later cycle. The of-record resolve path imports no model (the module-graph spine assertion proves
the import closure is model-free).

THE THREE SOs:

- ``SO-13.2-01`` ``resolve_batch`` — read the E-01 masters + the inbound feed, run the deterministic
  cascade, persist the resolved clusters' golden records append-only + the quarantined records to
  the review queue append-only, and return the per-record decisions + counts.
- ``SO-13.2-02`` ``get_golden_record`` — read a golden record back from the engine-owned store by
  internal ``entity_id`` (READ-ONLY).
- ``SO-13.2-03`` ``list_review_queue`` — read the quarantined records back from the engine-owned
  review-queue store (READ-ONLY).

THE WRITES ARE APPEND-ONLY, NOT STATE-MUTATIONS. ``resolve_batch`` writes NEW ``status = resolved``
golden-record events + NEW ``status = in_review`` queue events; it never updates a record, never
transitions a status, never force-merges an ambiguous record. The steward confirmation / alias
write-back is a later, human-gated cycle. The read + cascade + APPEND is wrapped in ``ctx.run`` so
it
is a journaled durable step; the deterministic run-scoped ids + insert-only ``on conflict do
nothing`` keep a replay/re-run idempotent.

Error classification (the ``bd12Recon`` precedent): a Pydantic ``ValidationError`` on the request
args is a terminal 400; a ``MartsUnavailableError`` / store-unavailable (a deterministic data
condition) is a terminal 422; any other deterministic compute failure is a terminal 422.

Honest boundary: this wires the *synthetic* SD-13.2 resolution surface over the durable substrate. A
green dispatch proves typed-dispatch + the masters/feed read + the deterministic cascade + the
append-only golden/review persistence; it is **not** a production resolution against a live
master-data platform, and the probabilistic/LLM-proposer tier is deferred.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict

import restate
import restate.serde
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from restate.exceptions import TerminalError

from agentinvest_demo.entity_resolution_data import (
    MartsUnavailableError,
    read_master_entities,
    read_resolution_feed,
)
from agentinvest_tools.entity_resolution import (
    FeedRecord,
    GoldenRecordRow,
    GoldenRecordStoreUnavailableError,
    MasterEntity,
    ResolutionResult,
    ResolutionReviewStoreUnavailableError,
    ReviewItem,
    append_golden_records,
    append_review_items,
    build_golden_record,
    count_golden_records,
    count_review_items,
    provenance_to_json,
    read_golden_records,
    read_review_items,
    resolve_batch,
)

ENTITY_RESOLUTION_SERVICE_NAME = "entityResolution"

RESOLVE_SO_ID = "SO-13.2-01"
GOLDEN_SO_ID = "SO-13.2-02"
REVIEW_SO_ID = "SO-13.2-03"


# --- the request / output models ------------------------------------------------------------------


class ResolveBatchRequest(BaseModel):
    """The resolve-batch request — a run as-of label (+ optional persist toggle).

    The cascade resolves the whole inbound feed against the whole master set (a firm-wide resolution
    run), so the request carries only an as-of label + ``persist``. ``persist`` controls whether the
    run appends the golden records + review-queue items (default true). ``extra="forbid"`` — an
    unrecognised arg is a deterministic 400.
    """

    model_config = ConfigDict(extra="forbid")

    as_of_date: str = Field(
        default="2026-01-31", description="The resolution-run as-of label."
    )
    persist: bool = Field(
        default=True,
        description="Append the golden records + review-queue items (append-only).",
    )


class ResolveRecordResult(BaseModel):
    """One per-record cascade decision in the resolve-batch output (the explainable trace)."""

    model_config = ConfigDict(extra="forbid")

    source_record_id: str
    decision: str
    tier: str
    matched_entity_id: str | None
    score: str
    signal: str


class ResolveBatchOutput(BaseModel):
    """The resolve-batch result — the per-record decisions + the before/after counts."""

    model_config = ConfigDict(extra="forbid")

    as_of_date: str
    n_records: int
    n_resolved: int
    n_new: int
    n_review: int
    n_golden_records: int = Field(description="The distinct golden records the run produced.")
    results: tuple[ResolveRecordResult, ...]


class GetGoldenRecordRequest(BaseModel):
    """The get-golden-record request — the internal entity_id (never an external id)."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(description="The internal golden key (E-01 entity_id).")


class GoldenRecordOut(BaseModel):
    """A golden record read back from the store."""

    model_config = ConfigDict(extra="forbid")

    golden_id: str
    entity_id: str
    entity_name: str | None
    lei: str | None
    domicile: str | None
    source_record_ids: tuple[str, ...]
    provenance_json: str
    status: str


class GetGoldenRecordOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    found: bool
    records: tuple[GoldenRecordOut, ...]


class ListReviewQueueRequest(BaseModel):
    """The list-review-queue request — an optional cap on the returned queue depth.

    The queue read is effectively arity-0 (it reads the steward review queue), but it carries an
    optional ``limit`` so the typed tool surface exposes a named property (the descriptor invariant
    the other tools meet) and a caller can cap a large queue. ``limit <= 0`` or unset returns all.
    """

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(
        default=0,
        description="Max review-queue items to return (<= 0 returns all).",
    )


class ReviewItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_id: str
    source_record_id: str
    source_system: str
    raw_name: str
    raw_domicile: str | None
    tier: str
    signal: str
    status: str


class ListReviewQueueOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n_items: int
    items: tuple[ReviewItemOut, ...]


@dataclass(frozen=True)
class ToolSpec:
    """One registry entry — a named Service Operation bound to its handler closure + I/O model."""

    so_id: str
    name: str
    summary: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]


_REGISTRY: dict[str, ToolSpec] = {
    RESOLVE_SO_ID: ToolSpec(
        so_id=RESOLVE_SO_ID,
        name="resolve_batch",
        summary=(
            "Resolve the inbound entity feed through the deterministic three-tier cascade — "
            "golden records for the resolved, the genuinely-ambiguous quarantined to review "
            "(never force-merged). NO LLM (the deterministic spine)."
        ),
        input_model=ResolveBatchRequest,
        output_model=ResolveBatchOutput,
    ),
    GOLDEN_SO_ID: ToolSpec(
        so_id=GOLDEN_SO_ID,
        name="get_golden_record",
        summary="Read a golden record by internal entity_id from the append-only store (readonly).",
        input_model=GetGoldenRecordRequest,
        output_model=GetGoldenRecordOutput,
    ),
    REVIEW_SO_ID: ToolSpec(
        so_id=REVIEW_SO_ID,
        name="list_review_queue",
        summary="List the steward review queue — the quarantined records (read-only).",
        input_model=ListReviewQueueRequest,
        output_model=ListReviewQueueOutput,
    ),
}


# --- the resolution-run core (pure; reused by the service AND the eval) ---------------------------


@dataclass(frozen=True)
class ResolutionRun:
    """The pure result of a resolution run — decisions + the derived golden records + review items.

    Pure (no persistence) so the eval scores it directly and the service persists it. Built by
    ``run_resolution`` from the masters + feed.
    """

    results: tuple[ResolutionResult, ...]
    golden_rows: tuple[GoldenRecordRow, ...]
    review_items: tuple[ReviewItem, ...]


def run_resolution(
    masters: tuple[MasterEntity, ...],
    feed: tuple[FeedRecord, ...],
    as_of_date: str,
) -> ResolutionRun:
    """Run the deterministic cascade over the feed + masters and derive the golden + review outputs.

    Pure + deterministic — no persistence, no label. Resolves the batch, builds one golden record
    per
    distinct resolved entity_id (clustering the resolved records by their matched master), and
    routes
    every ``review`` decision to the review-queue items. A ``new`` decision is NOT written to the
    golden store in cycle-1 (a net-new golden key is a curated steward decision); it is surfaced in
    the per-record results and counted, but neither golden-written nor (unless ambiguous) queued.
    """
    by_id = {m.entity_id: m for m in masters}
    feed_by_src = {r.source_record_id: r for r in feed}
    results = resolve_batch(tuple(feed), masters)

    # Cluster the RESOLVED records by their matched entity_id -> one golden record per cluster.
    resolved_clusters: dict[str, list[Any]] = {}
    review_items: list[ReviewItem] = []
    for res in results:
        rec = feed_by_src[res.source_record_id]
        if res.decision == "resolved" and res.matched_entity_id is not None:
            resolved_clusters.setdefault(res.matched_entity_id, []).append(rec)
        elif res.decision == "review":
            review_items.append(
                ReviewItem(
                    source_record_id=rec.source_record_id,
                    source_system=rec.source_system,
                    raw_name=rec.raw_name,
                    raw_domicile=rec.raw_domicile,
                    tier=res.tier,
                    signal=res.signal,
                    as_of_date=as_of_date,
                )
            )
        # decision == "new": surfaced in results + counted; not golden-written (curated key) and not
        # queued unless the batch guard demoted it to review (handled above).

    golden_rows: list[GoldenRecordRow] = []
    for entity_id in sorted(resolved_clusters):
        cluster = tuple(resolved_clusters[entity_id])
        gr = build_golden_record(entity_id, cluster, by_id.get(entity_id))
        golden_rows.append(
            GoldenRecordRow(
                entity_id=gr.entity_id,
                entity_name=gr.entity_name,
                lei=gr.lei,
                domicile=gr.domicile,
                source_record_ids=gr.source_record_ids,
                provenance_json=provenance_to_json(gr.provenance),
            )
        )

    return ResolutionRun(
        results=tuple(results),
        golden_rows=tuple(golden_rows),
        review_items=tuple(review_items),
    )


# --- the per-SO dispatch closures -----------------------------------------------------------------


def _dispatch_resolve(args: dict[str, Any], run_id: str) -> dict[str, Any]:
    try:
        request = ResolveBatchRequest.model_validate(args)
    except ValidationError as exc:
        raise TerminalError(
            f"{RESOLVE_SO_ID} (resolve_batch): invalid arguments — "
            f"{exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc

    try:
        masters = read_master_entities()
        feed = read_resolution_feed()
    except MartsUnavailableError as exc:
        raise TerminalError(f"{RESOLVE_SO_ID} (resolve_batch): {exc}", status_code=422) from exc

    run = run_resolution(masters, feed, request.as_of_date)

    if request.persist:
        try:
            if run.golden_rows:
                append_golden_records(list(run.golden_rows), run_id=run_id)
            if run.review_items:
                append_review_items(list(run.review_items), run_id=run_id)
        except (GoldenRecordStoreUnavailableError, ResolutionReviewStoreUnavailableError) as exc:
            raise TerminalError(f"{RESOLVE_SO_ID} (resolve_batch): {exc}", status_code=422) from exc

    n_resolved = sum(1 for r in run.results if r.decision == "resolved")
    n_new = sum(1 for r in run.results if r.decision == "new")
    n_review = sum(1 for r in run.results if r.decision == "review")
    output = ResolveBatchOutput(
        as_of_date=request.as_of_date,
        n_records=len(run.results),
        n_resolved=n_resolved,
        n_new=n_new,
        n_review=n_review,
        n_golden_records=len(run.golden_rows),
        results=tuple(
            ResolveRecordResult(
                source_record_id=r.source_record_id,
                decision=r.decision,
                tier=r.tier,
                matched_entity_id=r.matched_entity_id,
                score=str(r.score),
                signal=r.signal,
            )
            for r in run.results
        ),
    )
    return {
        "result": output.model_dump(mode="json"),
        "provenance": {
            "soId": RESOLVE_SO_ID,
            "tool": "resolve_batch",
            "runId": run_id,
            "persisted": bool(request.persist),
        },
        "computedBy": f"python:{ENTITY_RESOLUTION_SERVICE_NAME}",
    }


def _dispatch_get_golden(args: dict[str, Any], run_id: str) -> dict[str, Any]:
    try:
        request = GetGoldenRecordRequest.model_validate(args)
    except ValidationError as exc:
        raise TerminalError(
            f"{GOLDEN_SO_ID} (get_golden_record): invalid arguments — "
            f"{exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc
    try:
        if count_golden_records() == 0:
            records: list[Any] = []
        else:
            records = [g for g in read_golden_records() if g.entity_id == request.entity_id]
    except GoldenRecordStoreUnavailableError as exc:
        raise TerminalError(f"{GOLDEN_SO_ID} (get_golden_record): {exc}", status_code=422) from exc
    output = GetGoldenRecordOutput(
        entity_id=request.entity_id,
        found=bool(records),
        records=tuple(
            GoldenRecordOut(
                golden_id=g.golden_id,
                entity_id=g.entity_id,
                entity_name=g.entity_name,
                lei=g.lei,
                domicile=g.domicile,
                source_record_ids=g.source_record_ids,
                provenance_json=g.provenance_json,
                status=g.status,
            )
            for g in records
        ),
    )
    return {
        "result": output.model_dump(mode="json"),
        "provenance": {"soId": GOLDEN_SO_ID, "tool": "get_golden_record", "runId": run_id},
        "computedBy": f"python:{ENTITY_RESOLUTION_SERVICE_NAME}",
    }


def _dispatch_list_review(args: dict[str, Any], run_id: str) -> dict[str, Any]:
    try:
        request = ListReviewQueueRequest.model_validate(args)
    except ValidationError as exc:
        raise TerminalError(
            f"{REVIEW_SO_ID} (list_review_queue): invalid arguments — "
            f"{exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc
    try:
        items = [] if count_review_items() == 0 else read_review_items()
    except ResolutionReviewStoreUnavailableError as exc:
        raise TerminalError(f"{REVIEW_SO_ID} (list_review_queue): {exc}", status_code=422) from exc
    if request.limit > 0:
        items = items[: request.limit]
    output = ListReviewQueueOutput(
        n_items=len(items),
        items=tuple(
            ReviewItemOut(
                queue_id=it.queue_id,
                source_record_id=it.source_record_id,
                source_system=it.source_system,
                raw_name=it.raw_name,
                raw_domicile=it.raw_domicile,
                tier=it.tier,
                signal=it.signal,
                status=it.status,
            )
            for it in items
        ),
    )
    return {
        "result": output.model_dump(mode="json"),
        "provenance": {"soId": REVIEW_SO_ID, "tool": "list_review_queue", "runId": run_id},
        "computedBy": f"python:{ENTITY_RESOLUTION_SERVICE_NAME}",
    }


_DISPATCH: dict[str, Callable[[dict[str, Any], str], dict[str, Any]]] = {
    RESOLVE_SO_ID: _dispatch_resolve,
    GOLDEN_SO_ID: _dispatch_get_golden,
    REVIEW_SO_ID: _dispatch_list_review,
}


# --- the Restate envelope (the bd12Recon precedent) -----------------------------------------------


class ExecuteSoInput(BaseModel):
    """The ``execute_so`` request envelope — a named SO plus its args."""

    model_config = ConfigDict(extra="forbid")

    soId: str = Field(description="The Service-Operation identifier, e.g. SO-13.2-01")
    args: dict[str, Any] = Field(default_factory=dict, description="The SO args as a JSON object.")


class CapabilityDescriptor(TypedDict):
    soId: str
    name: str
    summary: str
    inputSchema: dict[str, Any]
    outputSchema: dict[str, Any]


class ListCapabilitiesOutput(TypedDict):
    service: str
    capabilities: list[CapabilityDescriptor]


entityResolution = restate.Service(ENTITY_RESOLUTION_SERVICE_NAME)


class ExecuteSoEnvelopeSerde(restate.serde.Serde[Any]):
    """A permissive pass-through JSON deserialiser so the handler guard owns the status
    (bd12Recon)."""

    def deserialize(self, buf: bytes) -> Any:
        if not buf:
            return {}
        try:
            return json.loads(buf)
        except Exception:
            return buf.decode("utf-8", errors="replace")

    def serialize(self, obj: Any) -> bytes:
        if obj is None:
            return b""
        return json.dumps(obj).encode("utf-8")


def _coerce_envelope(req: Any) -> dict[str, Any]:
    if isinstance(req, ExecuteSoInput):
        return req.model_dump()
    if not isinstance(req, dict):
        raise TerminalError(
            "execute_so: request body must be a JSON object with 'soId' and 'args' — "
            f"got {type(req).__name__}",
            status_code=400,
        )
    try:
        envelope = ExecuteSoInput.model_validate(req)
    except ValidationError as exc:
        raise TerminalError(
            f"execute_so: invalid request envelope — {exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc
    return envelope.model_dump()


@entityResolution.handler(name="execute_so", input_serde=ExecuteSoEnvelopeSerde())
async def execute_so(ctx: restate.Context, req: ExecuteSoInput) -> dict[str, Any]:
    """Dispatch a named SD-13.2 resolution Service Operation to its tool as a journaled step.

    Model-free dispatch — it routes the *named* ``soId`` to its registered resolution tool; it does
    not decide which SO to call (the orchestrator's ``.plan()`` loop does). The read + cascade +
    append-only persistence runs inside the journaled step (replay reads the result back; the
    deterministic run-scoped ids keep an actual re-run idempotent). The writes are append-only (new
    ``resolved`` / ``in_review`` events) — no update, no force-merge. NO LLM (the deterministic
    spine). An unknown ``soId`` is a terminal 404; a bad arg / data condition is terminal (400/422).
    """
    envelope = _coerce_envelope(req)
    so_id = envelope.get("soId")
    args = envelope.get("args", {})
    if not isinstance(args, dict):
        args = {}

    dispatch = _DISPATCH.get(so_id) if so_id is not None else None
    if dispatch is None:
        raise TerminalError(
            f"unknown Service Operation '{so_id}' — registered: {sorted(_DISPATCH)}",
            status_code=404,
        )

    as_of = args.get("as_of_date", "2026-01-31")
    run_id = f"{ctx.request().id}-{so_id}-{as_of}"
    return await ctx.run(f"so-{so_id}", lambda: dispatch(args, run_id))


@entityResolution.handler(name="list_capabilities")
async def list_capabilities(ctx: restate.Context) -> ListCapabilitiesOutput:
    """Return the registered SD-13.2 resolution tool catalogue — each so_id with its I/O schema.

    Read-only; no journaled step (it derives from the static registry). Arity-0 — called with an
    empty request body over the ingress.
    """
    capabilities: list[CapabilityDescriptor] = [
        {
            "soId": spec.so_id,
            "name": spec.name,
            "summary": spec.summary,
            "inputSchema": spec.input_model.model_json_schema(),
            "outputSchema": spec.output_model.model_json_schema(),
        }
        for spec in _REGISTRY.values()
    ]
    return {"service": ENTITY_RESOLUTION_SERVICE_NAME, "capabilities": capabilities}
