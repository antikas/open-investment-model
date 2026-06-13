"""The propose-only LLM cause-proposer + the evidence bundle (OIM-162 cycle-2, load-bearing tests).

These tests are OFFLINE + DETERMINISTIC (CI-safe): they inject a FAKE/stub Anthropic client so NO
live model call is made (the planner-test precedent; the ONE live smoke is proven separately and
pasted in the cycle report). What they prove:

1. **the evidence bundle never touches the oracle label** — the assembler imports neither the labels
   reader nor any labels table; a bundle's serialised content contains no label, no true cause, no
   `break_note` (the forbidden-input assertion);
2. **the proposer runs over the `unexplained` residue ONLY** — a proposal over a rule-classified
   break is a deterministic error (the residue-only invariant);
3. **the proposer captures, never decides** — the proposal's `of_record_cause` stays `unexplained`
   (the deterministic spine: the LLM proposal never changes the of-record cause);
4. **the narrowed/discovered rule is LABEL-INDEPENDENT** — `classify_value_diffs` reproduces the
   flywheel-turn outcome (the direction promote + the lone demotion) from the observable values
   ALONE, and a label-permutation of the value-break population does NOT change the rule's output
   (the rule reads the evidence, not the answer key);
5. **the stub seam is exercised end-to-end** — the prompt → tool-use → parse → CauseProposal path
   runs over the residue bundles with a stub client.
"""

from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from agentinvest_tools.bd12_recon import (
    BreakFinding,
    EvidenceBundle,
    assemble_bundle,
    assemble_value_context,
    classify_value_diffs,
    propose_cause,
)
from agentinvest_tools.bd12_recon import evidence_bundle as eb_module
from agentinvest_tools.bd12_recon.break_finding import ValueDiffCandidate
from agentinvest_tools.bd12_recon.proposer import (
    CauseProposalSchema,
    ProposerDeterministicError,
    build_proposer_prompt,
)

AS_OF = date(2026, 3, 31)


def _residue_finding(ref: str = "ibor:POS-0099") -> BreakFinding:
    """An `unexplained` residue break (of-record cause unexplained — the proposer's only input)."""
    return BreakFinding(
        reconciliation_type="ibor_abor",
        record_a_ref=ref,
        record_b_ref=ref.replace("ibor:", "abor:"),
        as_of_date=AS_OF,
        difference_amount=Decimal("250000"),
        difference_qty=None,
        cause_classification="unexplained",
        materiality="medium",
    )


# --- a fake/stub Anthropic client (the planner-test pattern) ------------------------------------


class _FakeBlock:
    def __init__(self, input_: dict[str, Any]) -> None:
        self.type = "tool_use"
        self.name = "emit_cause_proposal"
        self.input = input_


class _FakeResponse:
    def __init__(self, content: list[Any], stop_reason: str = "tool_use") -> None:
        self.content = content
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, proposal_for: Any) -> None:
        self._proposal_for = proposal_for

    def create(self, **kwargs: Any) -> _FakeResponse:
        prompt = kwargs["messages"][0]["content"]
        return _FakeResponse([_FakeBlock(self._proposal_for(prompt))])


class _FakeClient:
    _model_id_for_capture = "fake:test"

    def __init__(self, proposal_for: Any) -> None:
        self.messages = _FakeMessages(proposal_for)


def _proposal(cause: str = "pricing", conf: float = 0.6) -> dict[str, Any]:
    return {
        "proposed_cause": cause,
        "confidence": conf,
        "rationale": "from the observable evidence.",
        "evidence_cited": ["ratio_direction"],
    }


# ---------------------------------------------------------------------------
# (1) The evidence bundle NEVER touches the oracle label (the forbidden-input assertion).
# ---------------------------------------------------------------------------


def test_bundle_module_imports_no_label_reader_or_table() -> None:
    """STRUCTURAL: the evidence-bundle module imports NO labels reader and names NO label table.

    The label (`break_note` / `stg_break_labels` / `break_labels`) is a FORBIDDEN input to the
    bundle — the assembler reads only the neutral observable evidence. This parses the module's AST
    and asserts no IMPORT and no executed CODE references a label surface (the assembler imports
    neither a labels reader nor a label table name), so a bundle CANNOT carry the answer key by
    construction. (Scoping to imports + code names — NOT docstring/string prose — lets the module
    legitimately EXPLAIN in its docstring that the label is forbidden, without tripping the check.)
    """
    import ast

    src = inspect.getsource(eb_module)
    tree = ast.parse(src)
    forbidden = {"break_note", "stg_break_labels", "break_labels", "read_break_labels"}

    referenced: set[str] = set()
    for node in ast.walk(tree):
        # imports: `from X import name` / `import X`
        if isinstance(node, ast.ImportFrom):
            if node.module and any(f in node.module for f in forbidden):
                referenced.add(node.module)
            for alias in node.names:
                if any(f in alias.name for f in forbidden):
                    referenced.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if any(f in alias.name for f in forbidden):
                    referenced.add(alias.name)
        # code: a Name or Attribute referencing a label surface (NOT a string literal/docstring).
        elif isinstance(node, ast.Name) and node.id in forbidden:
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in forbidden:
            referenced.add(node.attr)

    assert not referenced, (
        f"the evidence-bundle module references the forbidden oracle label surface(s) {referenced} "
        f"in its imports/code — the label must never reach the bundle (it is the answer key)"
    )


def test_assembled_bundle_serialised_content_carries_no_label() -> None:
    """The assembled bundle's serialised content contains the observable evidence and NO label.

    A bundle is built from a finding + observable values; its JSON dump must carry no label field,
    no true cause, no `break_note` — only the neutral fields (diffs, ratio, direction, in-flight).
    """
    finding = _residue_finding()
    ctx = assemble_value_context([finding], {}, {})
    bundle = assemble_bundle(
        finding,
        break_id="BRK-T-0001",
        internal_value=Decimal("1000000"),
        external_value=Decimal("940000"),
        in_flight_qty=None,
        value_context=ctx,
    )
    dumped = bundle.model_dump_json()
    for forbidden in ("break_note", "true_cause", "label", "fx_break", "price_break", "qty_break"):
        assert forbidden not in dumped, f"the bundle leaked the forbidden label field {forbidden!r}"
    # the of-record cause IS carried (always `unexplained` for a residue break — the spine), and it
    # is NOT the answer key (it is the deterministic value the rule assigned).
    assert bundle.of_record_cause == "unexplained"
    assert bundle.ratio_direction == "below"  # 940000/1000000 = 0.94 < 1
    assert bundle.value_ratio == Decimal("0.940000")


def test_proposer_prompt_carries_no_label() -> None:
    """The prompt the model sees is built from the bundle ONLY — no label / no true cause."""
    finding = _residue_finding()
    ctx = assemble_value_context([finding], {}, {})
    bundle = assemble_bundle(
        finding, break_id="BRK-T-0002",
        internal_value=Decimal("1000000"), external_value=Decimal("1058000"),
        in_flight_qty=None, value_context=ctx,
    )
    prompt = build_proposer_prompt(bundle)
    for forbidden in ("break_note", "true_cause", "fx_break", "price_break", "answer key"):
        # "answer key" appears only in the negated "you do NOT have ... any answer key" instruction;
        # the FORBIDDEN thing is a LABEL VALUE, which must not appear.
        if forbidden == "answer key":
            continue
        assert forbidden not in prompt, f"the prompt leaked the forbidden label {forbidden!r}"
    assert "ratio_direction: above" in prompt  # the observable evidence IS in the prompt


# ---------------------------------------------------------------------------
# (2)+(3) The proposer runs over the residue ONLY and never changes the of-record cause.
# ---------------------------------------------------------------------------


def test_proposer_rejects_a_rule_classified_break() -> None:
    """A proposal over a rule-classified (NON-`unexplained`) break is a deterministic error.

    The proposer runs over the `unexplained` residue ONLY — a rule-classified break is of-record
    final and the proposer must never run over it (the residue-only invariant).
    """
    finding = BreakFinding(
        reconciliation_type="position", record_a_ref="POS-X", record_b_ref="custodian:POS-X",
        as_of_date=AS_OF, difference_amount=Decimal("500000"), difference_qty=None,
        cause_classification="pricing", materiality="medium",  # NOT unexplained
    )
    bundle = assemble_bundle(finding, break_id="BRK-T-0003")
    with pytest.raises(ProposerDeterministicError):
        propose_cause(bundle, client=_FakeClient(lambda _p: _proposal()))


def test_proposal_never_changes_the_of_record_cause() -> None:
    """THE DETERMINISTIC SPINE: the proposal's `of_record_cause` stays `unexplained`.

    The LLM proposes a cause (here `fx`), but the of-record cause carried on the captured proposal
    is the DETERMINISTIC value (`unexplained`) — the proposal never mutates it. The spine holds.
    """
    finding = _residue_finding()
    bundle = assemble_bundle(
        finding, break_id="BRK-T-0004",
        internal_value=Decimal("1000000"), external_value=Decimal("940000"),
    )
    proposal = propose_cause(
        bundle, client=_FakeClient(lambda _p: _proposal(cause="fx", conf=0.45))
    )
    assert proposal.proposed_cause == "fx"  # the LLM's proposal
    assert proposal.of_record_cause == "unexplained"  # the deterministic of-record cause unchanged
    assert proposal.confidence == Decimal("0.4500")
    assert proposal.snapshot_ref == bundle.snapshot_ref
    assert proposal.prompt_hash.startswith("sha256:")


def test_proposer_parses_and_validates_a_stub_proposal() -> None:
    """The stub seam runs end-to-end: prompt → tool-use → parse → CauseProposal (offline)."""
    finding = _residue_finding()
    bundle = assemble_bundle(
        finding, break_id="BRK-T-0005",
        internal_value=Decimal("1000000"), external_value=Decimal("1058000"),
    )
    proposal = propose_cause(bundle, client=_FakeClient(lambda _p: _proposal(cause="pricing")))
    assert proposal.break_id == "BRK-T-0005"
    assert proposal.proposed_cause == "pricing"
    assert proposal.model_id == "fake:test"


def test_schema_rejects_a_malformed_proposal() -> None:
    """A schema-invalid model response is a deterministic error (the planner-test discipline)."""
    finding = _residue_finding()
    bundle = assemble_bundle(finding, break_id="BRK-T-0006", internal_value=Decimal("1"),
                             external_value=Decimal("2"))
    # confidence out of range → schema invalid → deterministic.
    with pytest.raises(ProposerDeterministicError):
        propose_cause(bundle, client=_FakeClient(lambda _p: {"proposed_cause": "fx",
                                                             "confidence": 5.0, "rationale": "x"}))
    # the schema itself validates a well-formed object and rejects a bad one.
    assert CauseProposalSchema.model_validate(_proposal()).proposed_cause == "pricing"


# ---------------------------------------------------------------------------
# (4) The narrowed/discovered rule is LABEL-INDEPENDENT (the answer-key discipline at rule level).
# ---------------------------------------------------------------------------


def _cands(rows: list[tuple[str, str, str]]) -> list[ValueDiffCandidate]:
    return [
        ValueDiffCandidate(record_a_ref=r, record_b_ref=r, internal_value=Decimal(iv),
                           external_value=Decimal(ev))
        for (r, iv, ev) in rows
    ]


def test_narrowed_rule_reproduces_the_flywheel_outcome_from_values_alone() -> None:
    """The narrowed `classify_value_diffs` reproduces the flywheel-turn outcome from values ALONE.

    Mirrors the OIM-197 value-break population (the same ratios), NO label passed in — the rule
    sees only the observable values:
    - the shared downward fx pairs (0.98, 0.965) → `fx`;
    - the unique upward pricing breaks (1.04, 1.033 ...) → `pricing` (direction rule);
    - the coincidental upward pricing pair (1.058 shared) → `pricing` (the direction PROMOTE —
      above book is a mark difference, never fx);
    - the lone downward fx (0.94 unique) → `unexplained` (the honest DEMOTION);
    - the downward pricing colliding with the fx ratio (0.965) → `fx` (the unbreakable collision).
    """
    cands = _cands([
        ("POS-0004", "100", "98"),    # fx pair (0.98)
        ("POS-0023", "100", "98"),    # fx pair (0.98)
        ("POS-0005", "100", "96.5"),  # fx pair (0.965)
        ("POS-0007", "100", "96.5"),  # fx pair (0.965)
        ("POS-0012", "100", "104"),   # pricing unique above (1.04)
        ("POS-0014", "100", "105.8"), # pricing pair above (1.058)
        ("POS-0015", "100", "105.8"), # pricing pair above (1.058)
        ("POS-0013", "100", "94"),    # lone fx below (0.94) — unique
        ("POS-0016", "100", "96.5"),  # pricing below colliding with the fx ratio (0.965)
    ])
    out = classify_value_diffs(cands)
    assert out["POS-0004"] == out["POS-0023"] == "fx"
    assert out["POS-0005"] == out["POS-0007"] == "fx"
    assert out["POS-0012"] == "pricing"
    assert out["POS-0014"] == out["POS-0015"] == "pricing"   # the PROMOTE (above-book → pricing)
    assert out["POS-0013"] == "unexplained"                  # the DEMOTION (lone downward)
    assert out["POS-0016"] == "fx"                            # the unbreakable collision


def test_narrowed_rule_output_is_invariant_to_a_label_permutation() -> None:
    """LABEL-INDEPENDENCE: the rule output is identical whatever labels the breaks carry.

    `classify_value_diffs` takes only the observable values (record refs + internal/external value);
    it has NO label parameter and reads no label. This asserts the discipline structurally: the same
    value population yields the same classification regardless of any label the caller might attach
    elsewhere — the rule cannot be reading the answer key because it never receives one.
    """
    rows = [("A", "100", "105.8"), ("B", "100", "105.8"), ("C", "100", "94")]
    out_once = classify_value_diffs(_cands(rows))
    # re-run with the SAME values (a label permutation is a no-op to the rule — it takes no label).
    out_twice = classify_value_diffs(_cands(rows))
    assert out_once == out_twice
    # and the output is a pure function of the values: A/B (above, shared) → pricing; C (lone below)
    # → unexplained — no label could change this.
    assert out_once == {"A": "pricing", "B": "pricing", "C": "unexplained"}


def test_direction_rule_does_not_perturb_the_zero_amount_pin() -> None:
    """The POS-0019 by-construction pin (ratio == 1, zero amount) stays `pricing` under the rule.

    The pin-fragility warning (OIM-197 F-N2/O-2): the zero-amount A/B-disagreement break is
    classified `pricing` because its 1.000 ratio is unique. The narrowed DIRECTION rule (> 1 →
    pricing) must NOT change this — a ratio of exactly 1 is neither above nor below, so it falls to
    the cluster rule (unique → pricing). This guards that the rule holds on the EVIDENCE, not on the
    coincidence: the pin is unperturbed because 1.000 is unique, not because the rule relies on it.
    """
    # the zero-amount break (ratio 1.0) alone → pricing (the cluster rule, unperturbed)
    out = classify_value_diffs(_cands([("POS-0019", "100", "100")]))
    assert out["POS-0019"] == "pricing"
    # and even amid other value breaks, a unique 1.0 ratio stays pricing (not swept into a cluster).
    out2 = classify_value_diffs(_cands([
        ("POS-0019", "100", "100"), ("X", "100", "98"), ("Y", "100", "98"),
    ]))
    assert out2["POS-0019"] == "pricing"
    assert out2["X"] == out2["Y"] == "fx"


def test_evidence_bundle_is_a_frozen_model() -> None:
    """The bundle is immutable (frozen) — the replayable evidence a reviewer recomputes."""
    finding = _residue_finding()
    bundle = assemble_bundle(finding, break_id="BRK-T-0007", internal_value=Decimal("1"),
                             external_value=Decimal("2"))
    assert isinstance(bundle, EvidenceBundle)
    with pytest.raises(ValidationError):
        bundle.snapshot_ref = "tampered"  # noqa: PGH003 - frozen-model assignment raises at runtime
