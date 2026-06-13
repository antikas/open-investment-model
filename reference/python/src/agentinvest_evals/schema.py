"""The eval-set + eval-card format — the reused SSOT.

Two declared shapes, designed to extend:

- An **eval set** is a catalogue of `ToolSpec`s plus a list of `EvalCase`s. Each
  case is a realistic query, the `expected_tool_id` (the correct tool), and the
  near-duplicate `confusers` (the tools genuinely confusable with the correct one
  per the source SD spec). The set's tool catalogue is what a `Selector` ranks
  over; the cases are the golden labels.

- An **eval card** declares, in machine-checkable terms, what the eval measures:
  the `measures` statement, the `bar` (the write-time pass threshold), the
  `oracle` (where the correct labels come from — the BD-09 SD-09.1 Service
  Operation spec for the intra-domain set), the `author` and the `blesser`
  (distinct roles; the blesser certifies the set is genuinely adversarial and
  correctly labelled — a single-actor author-and-bless is visible because the two
  fields are equal).

The set is authored as JSON (data, diff-friendly, language-neutral so the TS side
can read it too); the card is authored as Markdown front-matter + prose so it is a
readable artefact AND machine-parseable. Both live under
`reference/evals/sets/`. This module is pure (no I/O beyond parsing a `dict` /
string) so the runner can be tested deterministically.

What extends additively here is the **data format**: the same
`EvalSet`/`EvalCard` shape is reused for a cross-office set (more confuser ids;
another set file; one additive `office_arm` tag on each case — see `EvalCase`),
and the production selector consumes exactly this `EvalSet` shape (its selections
scored via a record-then-score adapter — see `runner.py`). Adding the `office_arm`
field is additive — it defaults to `within-office`, so an untagged intra-domain
set parses unchanged, and existing fields stay stable.

**The gap metric itself was NOT additive — it is net-new runner/verdict work**:
two sub-population accuracies (within-office and cross-office), their difference
(the gap), and a two-part trigger (gap `> 5pp` primary OR cross-office `< 90%`
backstop). That is NOT expressible through the single-`bar` / single-`accuracy`
shapes here, so it lives in `runner.py` (`gap_metric`, `GapResult`) and a `--gap`
CLI path — not in this data format. The data format is reused additively; the
gap-metric verdict is structural runner work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# The two office arms a case can declare. The gap metric partitions cases on
# these. `within-office` is the control arm (near-duplicate confusers inside one
# office); `cross-office` is the torture arm (confusers straddling the
# front-office ↔ middle-office boundary). The default is within-office so an
# untagged intra-domain set parses unchanged.
WITHIN_OFFICE = "within-office"
CROSS_OFFICE = "cross-office"
_OFFICE_ARMS = frozenset({WITHIN_OFFICE, CROSS_OFFICE})


@dataclass(frozen=True)
class ToolSpec:
    """One tool in the catalogue a `Selector` ranks over.

    `tool_id` is the stable identifier the case labels reference. `name` and
    `description` are the natural-language surface a selector matches a query
    against — for the intra-domain set these are authored faithfully from the
    SD-09.1 Service Operation descriptions (the oracle), so the confusable
    vocabulary the SD spec itself carries (every return tool talks about "return",
    "period", "fees") is what makes the set genuinely adversarial.
    """

    tool_id: str
    name: str
    description: str

    def search_text(self) -> str:
        """The text a lexical selector matches against (name + description)."""
        return f"{self.name} {self.description}"


@dataclass(frozen=True)
class EvalCase:
    """One golden-labelled selection case.

    `query` is a realistic analyst request. `expected_tool_id` is the single
    correct tool. `confusers` are the near-duplicate tools that a weak selector
    is most likely to mis-pick — they must be genuinely confusable per the source
    spec (a green on non-confusable confusers is the "100%-pass is suspect" toy
    failure). `rationale` records WHY this is the right tool and why the confusers
    are tempting — a reviewer reads it to judge adversariality.

    `office_arm` (additive) tags which sub-population the case belongs to for the
    gap metric: `"within-office"` when the near-duplicate confusers sit inside one
    office (the control arm — e.g. all middle-office return tools, or all
    middle-office BD-08 valuation tools), `"cross-office"` when the confusers
    straddle the front-office ↔ middle-office boundary (the torture arm — e.g. a
    front-office desk mark vs a middle-office independent mark / IPV). It defaults
    to `"within-office"` so an intra-domain set (which has no tag in its JSON)
    parses unchanged and scores as one within-office population — the addition is
    strictly additive (the data format extends additively). The runner partitions
    on this tag to compute the two sub-population accuracies, the gap, and the
    two-part trigger; the tag carries NO scoring weight of its own (a case is
    correct iff the selected tool equals the label, identically in both arms) — it
    only declares which population the case counts toward, so the within/cross
    split is apples-to-apples (one selector, one catalogue, the only difference
    being where the near-duplicate sits relative to the office boundary).
    """

    case_id: str
    query: str
    expected_tool_id: str
    confusers: tuple[str, ...]
    rationale: str
    office_arm: str = WITHIN_OFFICE


@dataclass(frozen=True)
class EvalSet:
    """A tool catalogue + the golden cases over it."""

    set_id: str
    description: str
    tools: tuple[ToolSpec, ...]
    cases: tuple[EvalCase, ...]

    def tool_ids(self) -> tuple[str, ...]:
        return tuple(t.tool_id for t in self.tools)

    def validate(self) -> list[str]:
        """Structural self-check — returns a list of problems (empty == ok).

        This is NOT the accuracy eval; it is the set's well-formedness gate, run
        before scoring so a malformed set fails loudly rather than silently
        scoring wrong. It enforces the "not a toy set" properties:

        - every `expected_tool_id` and every confuser id exists in the catalogue;
        - a case never lists its own expected tool as a confuser;
        - case ids are unique;
        - (the two-sidedness check that the *intra-domain* set is not one-sided is
          asserted in the runner over the declared `focus_tool_ids`, since it is a
          property of a tool family within the set, not of the set shape alone).
        """
        problems: list[str] = []
        ids = set(self.tool_ids())
        seen_cases: set[str] = set()
        for c in self.cases:
            if c.case_id in seen_cases:
                problems.append(f"duplicate case_id: {c.case_id}")
            seen_cases.add(c.case_id)
            if c.expected_tool_id not in ids:
                problems.append(
                    f"{c.case_id}: expected_tool_id '{c.expected_tool_id}' not in catalogue"
                )
            for cf in c.confusers:
                if cf not in ids:
                    problems.append(f"{c.case_id}: confuser '{cf}' not in catalogue")
                if cf == c.expected_tool_id:
                    problems.append(f"{c.case_id}: expected_tool_id listed as its own confuser")
            if c.office_arm not in _OFFICE_ARMS:
                problems.append(
                    f"{c.case_id}: office_arm '{c.office_arm}' is not one of "
                    f"{sorted(_OFFICE_ARMS)}"
                )
        return problems

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> EvalSet:
        """Parse an eval set from its JSON `dict`. Deterministic; no I/O."""
        tools = tuple(
            ToolSpec(tool_id=t["tool_id"], name=t["name"], description=t["description"])
            for t in raw["tools"]
        )
        cases = tuple(
            EvalCase(
                case_id=c["case_id"],
                query=c["query"],
                expected_tool_id=c["expected_tool_id"],
                confusers=tuple(c["confusers"]),
                rationale=c["rationale"],
                # Additive: defaults to within-office when the case omits the tag
                # (so an untagged intra-domain set still parses).
                office_arm=c.get("office_arm", WITHIN_OFFICE),
            )
            for c in raw["cases"]
        )
        return EvalSet(
            set_id=raw["set_id"],
            description=raw["description"],
            tools=tools,
            cases=cases,
        )


@dataclass(frozen=True)
class EvalCard:
    """What an eval measures, its bar, its oracle, and its author≠blesser roles.

    `bar` is the pass threshold as a fraction in [0, 1] (within-office is
    0.95). `metric` names the reported quantity. `oracle` records where the
    correct labels come from (the ground-truth source). `author` and `blesser`
    are distinct strings; `single_actor_authored_and_blessed()` is True when they
    are equal — the structure makes that visible rather than hiding it.
    `focus_tool_ids` names the tool family the set is built to stress (the 4 BD-09
    return tools for the intra-domain set), so the runner can assert two-sidedness
    over it.
    """

    eval_id: str
    measures: str
    metric: str
    bar: float
    oracle: str
    author: str
    blesser: str
    set_ref: str
    focus_tool_ids: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    def single_actor_authored_and_blessed(self) -> bool:
        """True iff author == blesser — the governance smell the bless rule guards."""
        return self.author.strip() == self.blesser.strip()

    @staticmethod
    def from_markdown(text: str) -> EvalCard:
        """Parse an eval card from its `--- key: value ---` YAML-ish front-matter.

        A deliberately tiny, dependency-free front-matter reader (no PyYAML in the
        eval runtime): keys are `key: value`; list-valued keys use a bracketed
        comma list `[a, b, c]`; everything after the closing `---` is prose and
        ignored by the parser (it is the human-readable card body). Kept minimal
        so the card stays a readable Markdown artefact.
        """
        m = re.match(r"\s*---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
        if not m:
            raise ValueError("eval card has no '--- ... ---' front-matter block")
        fields: dict[str, Any] = {}
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise ValueError(f"malformed card front-matter line: {line!r}")
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                fields[key] = tuple(p.strip() for p in inner.split(",") if p.strip())
            else:
                fields[key] = value
        return EvalCard(
            eval_id=str(fields["eval_id"]),
            measures=str(fields["measures"]),
            metric=str(fields["metric"]),
            bar=float(fields["bar"]),
            oracle=str(fields["oracle"]),
            author=str(fields["author"]),
            blesser=str(fields["blesser"]),
            set_ref=str(fields["set_ref"]),
            focus_tool_ids=tuple(fields.get("focus_tool_ids", ())),
            notes=str(fields.get("notes", "")),
        )
