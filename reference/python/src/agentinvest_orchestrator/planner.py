"""The planner — one real Anthropic Sonnet 4.6 structured-output call.

``plan_task(task, catalogue, guardrails)`` is the pure core of the ``.plan()``
loop: it builds a prompt from the task + the candidate **tool catalogue** +
guardrails, makes ONE Anthropic call constrained to emit a ``PlanSchema``-shaped
object (via the Anthropic **tool-use** mechanism — a single forced ``emit_plan``
tool whose ``input_schema`` is ``PlanSchema``'s JSON schema), and validates the
response against ``PlanSchema``. A malformed / unparseable response is a clear
**typed error** (``PlannerDeterministicError``), never a silent bad plan; a
transient API fault (429/529/timeout/connection) is a ``PlannerTransientError``.
The Restate handler (``service.py``) maps the first to a ``TerminalError`` (no
retry storm) and lets the second be retried — the deterministic-error-is-terminal
discipline.

Key loading. ``ANTHROPIC_API_KEY`` loads from ``reference/.env`` via
``python-dotenv``. The key is **never hard-coded, logged, printed, or committed**:
it is read from the environment, and a missing key fails with a clear "set
ANTHROPIC_API_KEY in reference/.env" message — no key value is ever embedded or
emitted anywhere (not in a log line, an exception message, or the LLM-call-count
side-effect log).

A ``max_tokens`` cap keeps each plan small (a few hundred tokens is plenty) so a
runaway response cannot run up cost — hygiene, not a load-bearing limit.

The LLM-call-count side-effect log (the journaled-exactly-once proof instrument).
Every real model call appends one line to a side-effect log file (path from
``AGENTINVEST_LLM_CALL_LOG``, when set). The crash-replay proof asserts this log
holds exactly ONE line across a crash+restart of the production VO: replay reads
the journaled plan back, so the model is called once, not twice. The log carries
NO key and NO plan content — only a monotonic counter + the task label.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentinvest_orchestrator.plan_schema import PlanSchema

# The model id — Anthropic Sonnet 4.6, the frontier model driving the one loop
# (frontier-only). Overridable via env for a future model bump, but the default is
# the ratified model.
PLANNER_MODEL = os.environ.get("AGENTINVEST_PLANNER_MODEL", "claude-sonnet-4-6")

# The max_tokens cap — small plans only; hygiene against a runaway response.
PLANNER_MAX_TOKENS = int(os.environ.get("AGENTINVEST_PLANNER_MAX_TOKENS", "1024"))

# The forced structured-output tool name. The call forces this single tool so the
# model MUST return a PlanSchema-shaped object (no free-form prose plan to parse).
_EMIT_PLAN_TOOL = "emit_plan"


class PlannerError(RuntimeError):
    """Base class for planner failures."""


class PlannerDeterministicError(PlannerError):
    """A deterministic failure re-running cannot fix — terminal (no retry).

    A malformed / unparseable / schema-invalid model response, a missing API key,
    or a 4xx bad-request. The handler maps this to a Restate ``TerminalError`` so
    Restate does NOT retry a failure that re-sending the same request reproduces.
    """


class PlannerTransientError(PlannerError):
    """A transient API fault that a retry may clear — retryable (bounded).

    A 429 rate-limit, a 529 overloaded, a network timeout, a connection error. The
    handler lets Restate retry this (bounded), since a recoverable blip must not be
    made permanent.
    """


@dataclass(frozen=True)
class ToolDescriptor:
    """One candidate tool the planner may select — the catalogue entry shape.

    ``so_id`` is the identifier a plan step references; ``name`` + ``summary`` are
    the natural-language surface the planner reads to choose. ``input_schema`` is
    the tool's JSON input schema (when available) so the planner can fill ``args``
    plausibly. The catalogue is built by ``load_tool_catalogue`` (the tool-RAG
    seam) — from ``bd09.list_capabilities`` for the orchestrator path, or from the
    eval set's candidate descriptors for the eval path.
    """

    so_id: str
    name: str
    summary: str
    input_schema: dict[str, Any] | None = None


def _emit_plan_tool_def() -> dict[str, Any]:
    """The Anthropic tool definition that forces a ``PlanSchema``-shaped response.

    The tool's ``input_schema`` is ``PlanSchema``'s JSON schema, so the model's
    tool-use input IS the plan. Forcing this single tool (``tool_choice`` below)
    means the model cannot answer with free-form prose — it must emit the plan.
    """
    return {
        "name": _EMIT_PLAN_TOOL,
        "description": (
            "Emit the plan for the analyst task as a structured object: an ordered "
            "list of steps (each naming the soId of a tool from the provided catalogue "
            "and its args), plus a riskScore in [0,1] and a one-line summary. Choose "
            "tool soIds ONLY from the provided catalogue."
        ),
        "input_schema": PlanSchema.model_json_schema(),
    }


def _build_prompt(task: str, catalogue: tuple[ToolDescriptor, ...], guardrails: str) -> str:
    """Render the user prompt: the task, the candidate catalogue, the guardrails.

    Deterministic given its inputs (the catalogue is rendered in the order given).
    Carries NO key, NO secret — only the task text and the public tool descriptors.
    """
    tool_lines = []
    for t in catalogue:
        line = f"- soId={t.so_id} | {t.name}: {t.summary}"
        tool_lines.append(line)
    catalogue_block = "\n".join(tool_lines) if tool_lines else "(empty catalogue)"
    return (
        "You are the planning step of an investment-operations orchestrator. Decompose "
        "the analyst task below into a plan: an ordered list of tool-call steps, each "
        "selecting ONE tool from the candidate catalogue by its soId and supplying its "
        "args. Select the single most appropriate tool for the task as the FIRST step; "
        "add further steps only if the task genuinely needs them.\n\n"
        f"GUARDRAILS:\n{guardrails}\n\n"
        f"CANDIDATE TOOL CATALOGUE (choose soIds ONLY from this list):\n{catalogue_block}\n\n"
        f"ANALYST TASK:\n{task}\n\n"
        "Emit the plan via the emit_plan tool. Set riskScore to your honest estimate of "
        "how high-stakes the operation is (0 = read-only analytics, 1 = irreversible "
        "fiduciary action)."
    )


_DEFAULT_GUARDRAILS = (
    "Select tools only from the provided catalogue (never invent a soId). Prefer the "
    "single most specific tool for the task. This plan is GENERATED, not executed — it "
    "is a tool-selection proposal, not an action taken."
)


def load_api_key() -> str:
    """Load ``ANTHROPIC_API_KEY`` from ``reference/.env`` (python-dotenv) or the env.

    NEVER returns or logs the key value anywhere except handing it to the SDK
    client. Loads ``reference/.env`` if present (does not override an already-set
    env var). Raises ``PlannerDeterministicError`` with a clear, key-free message
    if the key is absent — terminal, since a missing key is not fixed by retrying.
    """
    from dotenv import load_dotenv

    # reference/.env lives two parents up from this file's package:
    #   .../reference/python/src/agentinvest_orchestrator/planner.py
    #   -> .../reference/.env
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise PlannerDeterministicError(
            "ANTHROPIC_API_KEY is not set. Set it in reference/.env "
            "(ANTHROPIC_API_KEY=sk-ant-...); it is loaded via python-dotenv and never committed."
        )
    return key


def _record_llm_call(task: str) -> None:
    """Append ONE line to the LLM-call-count side-effect log (proof instrument).

    Used by the journaled-exactly-once crash-replay proof: the log must hold
    exactly one line across a crash+restart, proving replay does NOT re-invoke the
    model. Carries NO key and NO plan content — only a counter and the task label.
    A no-op when ``AGENTINVEST_LLM_CALL_LOG`` is unset (production runs unset).
    """
    log_path = os.environ.get("AGENTINVEST_LLM_CALL_LOG")
    if not log_path:
        return
    # Count existing lines so the appended line carries a monotonic call number.
    p = Path(log_path)
    n = len(p.read_text(encoding="utf-8").splitlines()) if p.exists() else 0
    with p.open("a", encoding="utf-8") as fh:
        # A short, key-free witness line. The task is truncated; no plan content.
        fh.write(f"llm-call {n + 1} task={task[:60]!r}\n")


def _parse_tool_use_plan(response: Any) -> PlanSchema:
    """Extract the ``emit_plan`` tool-use input from the response, validate it.

    A response that is not a single ``emit_plan`` tool-use with a ``PlanSchema``
    -valid input is a deterministic failure (the structured-output constraint did
    not produce a usable plan) — raised as ``PlannerDeterministicError``.
    """
    tool_inputs = [
        block.input
        for block in response.content
        if getattr(block, "type", None) == "tool_use"
        and getattr(block, "name", None) == _EMIT_PLAN_TOOL
    ]
    if not tool_inputs:
        raise PlannerDeterministicError(
            f"model did not emit the {_EMIT_PLAN_TOOL} tool "
            f"(stop_reason={getattr(response, 'stop_reason', '?')}); no plan to parse."
        )
    raw = tool_inputs[0]
    try:
        return PlanSchema.model_validate(raw)
    except ValidationError as exc:
        # The structured-output constraint produced an object that is not a valid
        # PlanSchema — deterministic (re-sending reproduces it), so terminal.
        raise PlannerDeterministicError(
            f"model emit_plan input failed PlanSchema validation: "
            f"{exc.error_count()} error(s): {exc}"
        ) from exc


def plan_task(
    task: str,
    catalogue: tuple[ToolDescriptor, ...],
    guardrails: str = _DEFAULT_GUARDRAILS,
    *,
    client: Any | None = None,
) -> PlanSchema:
    """Make one real Anthropic Sonnet 4.6 structured-output call → a validated plan.

    The pure planner core (no Restate context): build the prompt, force the
    ``emit_plan`` tool, validate the response. ``client`` is injectable for tests
    (a fake Anthropic client) — when ``None`` a real ``anthropic.Anthropic`` client
    is constructed from the env-loaded key.

    Error classification (surfaced as typed errors the handler maps):
      - a missing key / a malformed-unparseable / schema-invalid response / a 4xx
        bad-request -> ``PlannerDeterministicError`` (terminal, no retry storm);
      - a 429 / 529 / timeout / connection error -> ``PlannerTransientError``
        (retryable, bounded).
    """
    if not task or not task.strip():
        raise PlannerDeterministicError("planner: task is empty (a deterministic input error).")
    if not catalogue:
        raise PlannerDeterministicError(
            "planner: candidate tool catalogue is empty (nothing to select from)."
        )

    if client is None:
        import anthropic

        client = anthropic.Anthropic(api_key=load_api_key())

    prompt = _build_prompt(task, catalogue, guardrails)

    # The proof instrument: record the (about-to-happen) real model call. This runs
    # INSIDE the journaled step on the orchestrator path, so a replay (which reads
    # the journaled plan back instead of re-running the step) does NOT reach here —
    # the log stays at one line across a crash. A no-op when the env is unset.
    _record_llm_call(task)

    # The client is provider-agnostic at this seam (a real anthropic.Anthropic, or a
    # fake injected in tests), so the create() call is made through an Any-typed
    # handle: the planner depends on the response SHAPE (a list of content blocks),
    # not on the SDK's strict create() overload.
    messages_api: Any = client.messages
    try:
        response = messages_api.create(
            model=PLANNER_MODEL,
            max_tokens=PLANNER_MAX_TOKENS,
            tools=[_emit_plan_tool_def()],
            tool_choice={"type": "tool", "name": _EMIT_PLAN_TOOL},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 - we re-classify into the typed error pair
        _raise_classified(exc)

    return _parse_tool_use_plan(response)


def _raise_classified(exc: Exception) -> Any:
    """Map an Anthropic SDK exception onto the deterministic/transient typed pair.

    Transient (retryable): rate-limit (429), overloaded (529), API connection /
    timeout errors. Deterministic (terminal): authentication (401), permission
    (403), bad-request (400), not-found (404) — and any unrecognised error is
    treated deterministic (terminal) by default, the safe classification for a
    fiduciary substrate (never retry-storm an unknown). The message carries NO key.
    """
    # Import lazily so the module imports without the SDK present (tests inject a
    # client and never reach here; the error types are matched by name+attr).
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
        raise PlannerTransientError(
            f"transient Anthropic API fault ({name}, status={status})"
        ) from exc

    # Everything else — auth, permission, bad-request, not-found, and any
    # unrecognised error — is deterministic/terminal (no retry storm).
    raise PlannerDeterministicError(
        f"deterministic Anthropic API failure ({name}, status={status})"
    ) from exc


def _safe_json_dumps(obj: Any) -> str:
    """Compact, deterministic JSON (sorted keys) — used by the eval transcript."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
