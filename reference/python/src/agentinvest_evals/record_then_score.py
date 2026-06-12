"""Record-then-score — integrate the REAL ``.plan()`` selector into the harness.

This is the OIM-105 P-MAJOR-1 carry-forward made real: OIM-130's planner is
async / durable / non-deterministic (it makes a real Sonnet 4.6 call), so it
CANNOT be a synchronous ``Selector`` scored live in the runner loop (that would
either measure a sync stand-in, or async-ify the deterministic interface and break
the harness's replay-stability). Instead:

1. **Record.** Run the real planner ONCE over every case in an eval set, taking
   the plan's PRIMARY tool selection (``plan.selected_so_ids()[0]``) as that case's
   recorded selection. Write the selections to a **fixed transcript file** (JSON).
   This is the one non-deterministic step — it happens once, off-line, and is
   pinned to disk.

2. **Score.** A ``TranscriptSelector`` implements the existing ``Selector``
   contract by LOOKING UP each query's recorded selection from the transcript — a
   pure, deterministic, replay-stable read. It is scored through the EXISTING
   ``run_eval`` / ``gap_metric`` runner + ``--gap`` gap metric, byte-for-byte the
   same scoring code the baseline runs through. The score of a fixed transcript is
   deterministic and re-runnable without a live model call.

So the planner's selections ARE measured (record), and the scoring stays
deterministic + replay-stable (score) — NOT a sync proxy, NOT an async-ified
interface. The transcript is keyed by ``case_id`` so a re-score reads exactly the
selections the planner made.

The gate-E number is whatever the planner actually scores — reported HONESTLY by
the runner. A miss is a real architectural signal (see the runner's honest
boundary), never something to fudge.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agentinvest_evals.schema import EvalSet, ToolSpec
from agentinvest_orchestrator.planner import ToolDescriptor, plan_task

# The transcript home (a builder artefact — the recorded planner selections).
_TRANSCRIPTS_DIR = Path(__file__).resolve().parents[3] / "evals" / "transcripts"


@dataclass(frozen=True)
class PlanTranscript:
    """A recorded run of the real planner over an eval set.

    ``selector_label`` names the recorded selector (e.g. the model id). ``set_id``
    pins which set this transcript scores against (a mismatch is a loud error, not
    a silent wrong score). ``selections`` maps ``case_id -> selected_tool_id`` (the
    plan's primary tool selection). ``model`` records the model that produced it.
    """

    selector_label: str
    set_id: str
    model: str
    selections: dict[str, str]

    def to_json(self) -> str:
        return json.dumps(
            {
                "selector_label": self.selector_label,
                "set_id": self.set_id,
                "model": self.model,
                "selections": self.selections,
            },
            sort_keys=True,
            ensure_ascii=True,
            indent=2,
        )

    @staticmethod
    def from_json(text: str) -> PlanTranscript:
        raw = json.loads(text)
        return PlanTranscript(
            selector_label=raw["selector_label"],
            set_id=raw["set_id"],
            model=raw["model"],
            selections=dict(raw["selections"]),
        )


def _descriptors_for(tools: tuple[ToolSpec, ...]) -> tuple[ToolDescriptor, ...]:
    """The candidate catalogue for the eval path — the whole set, load-all (the seam).

    Apples-to-apples with the baseline, which also ranks over the whole set's
    catalogue per case. (The tool-RAG seam is load-all at this scale — see
    ``tool_catalogue``.)
    """
    return tuple(
        ToolDescriptor(so_id=t.tool_id, name=t.name, summary=t.description, input_schema=None)
        for t in tools
    )


def record_transcript(eval_set: EvalSet, *, model_label: str) -> PlanTranscript:
    """Run the REAL planner over every case in ``eval_set``; record its selections.

    The one non-deterministic step. For each case, the planner is given the whole
    set's catalogue (load-all seam) and the case query; the plan's PRIMARY tool
    selection is recorded. The candidate set is identical to the baseline's, so the
    comparison is apples-to-apples. Makes one real Sonnet call per case — keep the
    set small (the OIM-105/106 sets are 16 + 28 cases).
    """
    catalogue = _descriptors_for(eval_set.tools)
    valid_ids = {t.tool_id for t in eval_set.tools}
    selections: dict[str, str] = {}
    for case in eval_set.cases:
        plan = plan_task(case.query, catalogue)
        chosen = plan.selected_so_ids()[0]
        # The planner is instructed to choose only catalogue ids; if it returns one
        # outside the catalogue, record it verbatim (it will score as a MISS — an
        # honest record of what the planner did, never silently remapped).
        if chosen not in valid_ids:
            chosen = f"__off-catalogue__:{chosen}"
        selections[case.case_id] = chosen
    return PlanTranscript(
        selector_label=model_label,
        set_id=eval_set.set_id,
        model=model_label,
        selections=selections,
    )


class TranscriptSelector:
    """A deterministic ``Selector`` reading a recorded transcript (the score side).

    Implements the existing ``Selector`` contract (``name`` + ``select(query,
    tools) -> tool_id``) by looking up the recorded selection for the query's case.
    Because the harness scores by passing each case's query, the selector resolves
    the query back to a ``case_id`` via a query->case_id index built from the set,
    then returns the recorded selection. A pure, deterministic, replay-stable read —
    no model call, no network, no randomness. This is what makes record-then-score
    replay-stable: the live run is recorded ONCE; scoring the transcript is byte-
    stable and re-runnable.
    """

    def __init__(self, transcript: PlanTranscript, eval_set: EvalSet) -> None:
        if transcript.set_id != eval_set.set_id:
            raise ValueError(
                f"transcript set_id '{transcript.set_id}' != eval set '{eval_set.set_id}' "
                "— refusing to score a transcript against the wrong set."
            )
        self.name = transcript.selector_label
        self._transcript = transcript
        # Index query -> case_id (queries are unique within a set; the runner scores
        # by query, so we resolve query back to the recorded case selection).
        self._query_to_case: dict[str, str] = {c.query: c.case_id for c in eval_set.cases}
        # Every case must have a recorded selection (a partial transcript is a loud
        # error, not a silent default).
        missing = [c.case_id for c in eval_set.cases if c.case_id not in transcript.selections]
        if missing:
            raise ValueError(
                f"transcript is missing selections for {len(missing)} case(s): {missing}"
            )

    def select(self, query: str, tools: tuple[ToolSpec, ...]) -> str:  # noqa: ARG002 - contract sig
        case_id = self._query_to_case.get(query)
        if case_id is None:
            raise ValueError(f"no recorded case for query: {query!r}")
        return self._transcript.selections[case_id]


def transcript_path(set_id: str, model_label: str) -> Path:
    """The on-disk path for a recorded transcript (a builder artefact)."""
    safe = model_label.replace("/", "-")
    return _TRANSCRIPTS_DIR / f"{set_id}.{safe}.transcript.json"


def save_transcript(transcript: PlanTranscript) -> Path:
    """Write a transcript to its builder-artefact path; return the path."""
    path = transcript_path(transcript.set_id, transcript.model)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(transcript.to_json() + "\n", encoding="utf-8")
    return path


def load_transcript(set_id: str, model_label: str) -> PlanTranscript:
    """Load a previously-recorded transcript from its builder-artefact path."""
    path = transcript_path(set_id, model_label)
    return PlanTranscript.from_json(path.read_text(encoding="utf-8"))
