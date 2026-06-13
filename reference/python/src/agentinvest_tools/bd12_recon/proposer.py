"""The propose-only LLM cause classifier over the ``unexplained`` residue (OIM-162 cycle-2).

A typed tool that takes an ``unexplained`` E-24 break + its deterministically-assembled
observable-evidence bundle and returns a **PROPOSAL** — a ``proposed_cause`` (an E-24 vocabulary
value, or still-``unexplained``), a confidence, a rationale, and the evidence it cites. It runs ONLY
over breaks whose of-record classification is ``unexplained`` (the deterministic residue); it NEVER
runs over a rule-classified break (those are of-record final).

THE DETERMINISTIC SPINE (the load-bearing architecture invariant). The LLM PROPOSES; rules CLASSIFY.
This tool NEVER writes the of-record ``cause_classification`` — its output is a proposal captured
append-only in the proposal store (``proposal_store.py``), the LLM's ENTIRE writable universe. The
of-record cause stays the deterministic ``unexplained`` value; no LLM output enters the break store,
the canonical layer, or any state the system acts on. Describing this tool as "classifying breaks"
is WRONG — it proposes; the deterministic rules classify. (ADR-0054 + the deterministic-spine:
no LLM in the knowledge-claim path.)

THE LLM SEAM (the ``agentinvest_orchestrator/planner.py`` precedent — Anthropic). One structured-
output Anthropic call constrained to emit a ``CauseProposalSchema``-shaped object via the Anthropic
tool-use mechanism (a single forced ``emit_cause_proposal`` tool whose ``input_schema`` is the
schema's JSON schema). A malformed/unparseable response is a typed ``ProposerDeterministicError``
(terminal); a transient API fault is a ``ProposerTransientError`` (retryable). The
``ANTHROPIC_API_KEY``
loads from ``reference/.env`` via the planner's ``load_api_key`` (never hard-coded, logged, or
committed). ``client`` is INJECTABLE so CI runs against a deterministic stub/recorded fixture — NO
live model call in the gate; the one live smoke is proven separately (the cycle report).

THE LABEL NEVER REACHES THE MODEL. The prompt is built from the evidence bundle ONLY (the neutral
observable evidence — ``evidence_bundle.py`` forbids the label). The model never sees
``break_note``,
``stg_break_labels``, or the true cause — it proposes from the same observable evidence the
deterministic rule sees. So a rule DERIVED from a correct proposal's rationale is label-independent
by construction (proven by test).

THE HONEST BOUNDARY (this cycle). One flywheel turn over a SYNTHETIC corpus, with the human gate
exercised AS THIS CYCLE'S OWN review (this brief + its blind audit) — NOT a production review
workflow, NOT continuous learning, NOT model training. A proposal that is correct-against-label AND
yields a derivable label-independent rule is PROMOTED by this cycle's own audited code change (the
narrowed ``classify_value_diffs``); anything no honest rule reaches stays ``unexplained``.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# The model id — reuse the planner's ratified frontier model default (ADR-0054 v0.1 frontier-only).
# Overridable via env for a future model bump (the planner's PLANNER_MODEL convention).
from agentinvest_orchestrator.planner import PLANNER_MODEL as PROPOSER_MODEL
from agentinvest_tools.bd12_recon.evidence_bundle import EvidenceBundle

# The E-24 cause vocabulary the proposal may name (or still-``unexplained``).
ProposedCause = Literal[
    "timing", "pricing", "missing_transaction", "data_error", "fx", "fees", "unexplained"
]

# The max_tokens cap — small proposals only; hygiene against a runaway response (the planner cap).
PROPOSER_MAX_TOKENS = 512

# The forced structured-output tool name (the planner's _EMIT_PLAN_TOOL convention).
_EMIT_PROPOSAL_TOOL = "emit_cause_proposal"


class ProposerError(RuntimeError):
    """Base class for proposer failures (the planner's typed-error pair, mirrored)."""


class ProposerDeterministicError(ProposerError):
    """A deterministic failure re-running cannot fix — terminal (no retry).

    A malformed / unparseable / schema-invalid model response, a missing API key, a non-residue
    break, or a 4xx bad-request. The handler maps this to a Restate ``TerminalError`` so Restate
    does
    NOT retry a failure that re-sending the same request reproduces.
    """


class ProposerTransientError(ProposerError):
    """A transient API fault that a retry may clear — retryable (bounded)."""


class CauseProposalSchema(BaseModel):
    """The structured-output object the model is forced to emit — the proposal's content.

    The model fills this from the evidence bundle ONLY. ``proposed_cause`` is an E-24 vocabulary
    value or 'unexplained' (honest abstention); ``confidence`` is [0,1]; ``rationale`` cites the
    observable evidence; ``evidence_cited`` names the bundle fields the proposal leaned on (so a
    reviewer sees the grounding). ``extra='forbid'`` so a malformed object is a clean error.
    """

    model_config = ConfigDict(extra="forbid")

    proposed_cause: ProposedCause = Field(
        description="The proposed E-24 cause, or 'unexplained' if the evidence does not support" 
            "one."
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Honest confidence in [0,1].")
    rationale: str = Field(
        min_length=1, description="One-paragraph rationale grounded in the observable evidence."
    )
    evidence_cited: tuple[str, ...] = Field(
        default=(), description="The bundle fields the proposal cites (e.g. ratio_direction)."
    )


class CauseProposal(BaseModel):
    """One captured cause proposal — the proposer's full output, ready for the append-only store.

    Carries the proposal content PLUS the capture metadata the flywheel needs: the break it is over,
    the model id, the evidence-snapshot ref, the prompt hash, the of-record cause (always
    'unexplained' — the spine), and a timestamp. This is what ``proposal_store.append_proposals``
    persists at ``status = proposed``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    break_id: str = Field(description="The engine break id the proposal is over.")
    reconciliation_type: str = Field(description="position / cash / transaction / ibor_abor.")
    record_a_ref: str = Field(description="The break's internal-book record.")
    model_id: str = Field(description="The model that produced the proposal (or 'stub' in CI).")
    snapshot_ref: str = Field(
        description="The evidence-bundle content hash the proposal is grounded in."
    )
    prompt_hash: str = Field(description="A hash of the exact prompt the model saw (replay key).")
    proposed_cause: ProposedCause = Field(description="The proposed cause, or 'unexplained'.")
    confidence: Decimal | None = Field(default=None, description="Confidence in [0,1], 4dp.")
    rationale: str = Field(description="The observable-evidence rationale.")
    of_record_cause: str = Field(
        description="The DETERMINISTIC of-record cause — always 'unexplained' for a residue break "
        "(the proposal never changes it; the spine holds)."
    )
    created_at: str = Field(default="", description="ISO timestamp the proposal was captured.")


def _emit_proposal_tool_def() -> dict[str, Any]:
    """The Anthropic tool definition that forces a ``CauseProposalSchema``-shaped response."""
    return {
        "name": _EMIT_PROPOSAL_TOOL,
        "description": (
            "Emit a cause proposal for an UNEXPLAINED reconciliation break, as a structured" 
                "object: "
            "a proposed_cause (one of timing/pricing/missing_transaction/data_error/fx/fees, or "
            "'unexplained' if the observable evidence does not support a cause), a confidence in "
            "[0,1], a one-paragraph rationale grounded ONLY in the observable evidence provided," 
                "and "
            "the evidence fields you cited. You are PROPOSING, not deciding — the deterministic" 
                "rules "
            "remain the only of-record classification."
        ),
        "input_schema": CauseProposalSchema.model_json_schema(),
    }


def build_proposer_prompt(bundle: EvidenceBundle) -> str:
    """Render the prompt from the evidence bundle ONLY — the label is never in it.

    Deterministic given the bundle. Carries NO label, NO ``break_note``, NO true cause — only the
    neutral observable evidence (the diffs, the value ratio + direction + cluster size, the
    in-flight
    quantity). The model proposes from the same observable evidence the deterministic rule sees.
    """
    return (
        "You are a propose-only classification aid for an investment-operations RECONCILIATION "
        "engine. A break has been surfaced and the DETERMINISTIC of-record rules could not" 
            "classify "
        "its cause (it is 'unexplained'). Propose the most likely cause from the OBSERVABLE" 
            "EVIDENCE "
        "below ONLY — you do NOT have, and must not assume, any answer key. If the evidence does" 
            "not "
        "support a specific cause, propose 'unexplained' honestly.\n\n"
        "OBSERVABLE EVIDENCE (the only inputs — no label is provided):\n"
        f"- reconciliation_type: {bundle.reconciliation_type}\n"
        f"- internal record: {bundle.record_a_ref}\n"
        f"- counter-record: {bundle.record_b_ref}\n"
        f"- difference_amount (external - internal): {bundle.difference_amount}\n"
        f"- difference_qty (external - internal): {bundle.difference_qty}\n"
        f"- value_ratio (external/internal): {bundle.value_ratio}\n"
        f"- ratio_direction: {bundle.ratio_direction} "
        "(above = custodian marks higher; below = custodian translates lower)\n"
        f"- ratio_cluster_size: {bundle.ratio_cluster_size} "
        "(how many value breaks in this run share this exact ratio; >=2 suggests a systematic "
        "FX-translation factor, 1 suggests an idiosyncratic single-holding difference)\n"
        f"- in_flight_qty (a known TD/SD trade for this instrument): {bundle.in_flight_qty}\n\n"
        "CAUSE VOCABULARY: timing (a TD/SD in-flight trade explains a quantity lag), pricing (a "
        "single-holding mark difference, often the custodian marking above the book), fx (a "
        "systematic currency-translation difference shared across holdings, translating the value "
        "lower), missing_transaction, data_error (a quantity miscount with no value/trade signal), "
        "fees, or 'unexplained'.\n\n"
        "Emit your proposal via the emit_cause_proposal tool. You are PROPOSING for human review, "
        "not deciding — the deterministic rules remain the of-record classification."
    )


def _prompt_hash(prompt: str) -> str:
    return "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _parse_proposal(response: Any) -> CauseProposalSchema:
    """Extract the ``emit_cause_proposal`` tool-use input and validate it (the planner pattern)."""
    tool_inputs = [
        block.input
        for block in response.content
        if getattr(block, "type", None) == "tool_use"
        and getattr(block, "name", None) == _EMIT_PROPOSAL_TOOL
    ]
    if not tool_inputs:
        raise ProposerDeterministicError(
            f"model did not emit the {_EMIT_PROPOSAL_TOOL} tool "
            f"(stop_reason={getattr(response, 'stop_reason', '?')}); no proposal to parse."
        )
    try:
        return CauseProposalSchema.model_validate(tool_inputs[0])
    except ValidationError as exc:
        raise ProposerDeterministicError(
            f"model emit_cause_proposal input failed schema validation: "
            f"{exc.error_count()} error(s): {exc}"
        ) from exc


def propose_cause(
    bundle: EvidenceBundle,
    *,
    client: Any | None = None,
) -> CauseProposal:
    """Make one propose-only Anthropic call over an ``unexplained`` break bundle → a proposal.

    The pure proposer core (no Restate context): assert the break is a residue break (of-record
    cause is 'unexplained'), build the prompt from the bundle, force the ``emit_cause_proposal``
    tool, validate the response, and wrap it as a ``CauseProposal`` ready for the append-only store.

    PRECONDITION (the residue-only invariant): the bundle's ``of_record_cause`` MUST be
    'unexplained' — a proposal over a rule-classified break is a deterministic error (the proposer
    runs over the residue ONLY; rule-classified breaks are of-record final).

    ``client`` is injectable for CI (a fake/stub Anthropic client returning a recorded proposal) —
    when ``None`` a real ``anthropic.Anthropic`` client is constructed from the env-loaded key (the
    one live smoke). The model id is the ratified frontier model (the planner's).

    The proposal NEVER changes the of-record cause — it is captured at ``status = proposed`` in the
    proposal store; the deterministic spine holds (the of-record cause stays 'unexplained').
    """
    if bundle.of_record_cause != "unexplained":
        raise ProposerDeterministicError(
            f"propose_cause runs over the UNEXPLAINED residue only; break {bundle.break_id} has "
            f"of-record cause {bundle.of_record_cause!r} (a rule-classified break is of-record "
            f"final — the proposer must not run over it)."
        )

    prompt = build_proposer_prompt(bundle)
    model_id = PROPOSER_MODEL

    if client is None:
        import anthropic

        from agentinvest_orchestrator.planner import load_api_key

        client = anthropic.Anthropic(api_key=load_api_key())

    messages_api: Any = client.messages
    try:
        response = messages_api.create(
            model=PROPOSER_MODEL,
            max_tokens=PROPOSER_MAX_TOKENS,
            tools=[_emit_proposal_tool_def()],
            tool_choice={"type": "tool", "name": _EMIT_PROPOSAL_TOOL},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 - re-classified into the typed pair (the planner pattern)
        _raise_classified(exc)

    schema = _parse_proposal(response)
    model_id = getattr(client, "_model_id_for_capture", model_id)
    return CauseProposal(
        break_id=bundle.break_id,
        reconciliation_type=bundle.reconciliation_type,
        record_a_ref=bundle.record_a_ref,
        model_id=model_id,
        snapshot_ref=bundle.snapshot_ref,
        prompt_hash=_prompt_hash(prompt),
        proposed_cause=schema.proposed_cause,
        confidence=Decimal(str(round(schema.confidence, 4))),
        rationale=schema.rationale,
        of_record_cause=bundle.of_record_cause,
        created_at=datetime.now().isoformat(timespec="seconds"),
    )


def _raise_classified(exc: Exception) -> Any:
    """Map an Anthropic SDK exception onto the deterministic/transient typed pair (planner map)."""
    name = type(exc).__name__
    status = getattr(exc, "status_code", None)
    transient_names = {
        "RateLimitError",
        "InternalServerError",
        "APIConnectionError",
        "APITimeoutError",
        "APIConnectionTimeoutError",
    }
    transient_status = {408, 409, 429, 500, 502, 503, 504, 529}
    if name in transient_names or (isinstance(status, int) and status in transient_status):
        raise ProposerTransientError(
            f"transient Anthropic API fault ({name}, status={status})"
        ) from exc
    raise ProposerDeterministicError(
        f"deterministic Anthropic API failure ({name}, status={status})"
    ) from exc
