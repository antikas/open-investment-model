"""The pluggable `Selector` interface + this cycle's deterministic baseline.

The harness measures *a* selector through one stable contract:

    Selector.select(query, tools) -> selected_tool_id

`query` is the analyst request; `tools` is the candidate catalogue (the eval
set's `ToolSpec`s); the return is the single `tool_id` the selector picks. That
is the whole contract — deliberately the minimum that BOTH a lexical baseline AND
OIM-130's LLM `.plan()` tool-RAG selector can satisfy:

- the **baseline** (this cycle) ranks by lexical token overlap between the query
  and each tool's text and returns the top tool — no network, no API key, no
  randomness;
- the **production selector** (OIM-130) will embed/RAG the query against the tool
  catalogue inside the `.plan()` loop and return the chosen `tool_id` — the same
  signature, a different mechanism. The interface is intentionally NOT coupled to
  the baseline's lexical mechanism: it takes the catalogue, not a precomputed
  index; it returns an id, not a score vector; it has no `.fit()` / no shared
  state. An LLM selector implements `select` by calling a model; nothing in the
  contract leaks the baseline's internals. (Clause-5 interface walk.)

This cycle's baseline is **token-overlap (Jaccard) with a deterministic
tie-break**, chosen as the cheapest mechanism meeting deterministic + offline +
replay-stable. Comparison is done with **integer cross-multiplication** of the
overlap/union counts (never floating-point division), so the ranking is exact and
byte-identical across runs and platforms; ties break on the lexicographically
smallest `tool_id`. TF-IDF / local-embedding baselines were considered and
rejected for this cycle: they introduce float accumulation whose summation order
can vary, weakening the byte-identical replay property the harness must prove,
for no gain on a 4-tool intra-domain set.

**Tie-break = deterministic but ARBITRARY (latent number-fragility, P-MINOR-2).**
When two tools tie on exact Jaccard, the lexicographically smallest `tool_id`
wins. This is deterministic (so replay is stable) but it carries *no signal* —
the winner is decided by id naming, not by the query. The explicit "X not Y" pair
(C13 `twr-vs-mwr` / C14 `mwr-vs-twr`) sits at this resolution floor: both
candidates tie at Jaccard 0.125, so C14 passes only because `mwr` < `twr`
alphabetically and C13 misses for the mirror reason. **Renaming the tool ids
(e.g. `SO-09-01-time-weighted` / `-money-weighted`) would silently swap the
C13/C14 outcomes and shift the recorded headline number.** The tie-break logic is
intentionally NOT changed here (changing it would move the number); this comment
makes the dependence visible so a future id rename is not a silent surprise.

The baseline is a *harness-validation* selector. Its accuracy calibrates the
instrument; it is NOT agentINVEST's tool-selection accuracy. See the module
docstring in `__init__.py` and `reference/evals/README.md`.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from agentinvest_evals.schema import ToolSpec

# A stable, declared stop list. Held in the selector (not derived per-run) so the
# baseline is fully reproducible and the audit can see exactly what is dropped.
# Deliberately small and generic — NOT tuned to make the BD-09 set pass (tuning
# the stop list to the set would be gaming the baseline; the point is an honest
# weak baseline, not a green number).
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
        "i", "in", "is", "it", "its", "me", "my", "of", "on", "or", "our",
        "show", "that", "the", "their", "this", "to", "want", "was", "we",
        "what", "when", "where", "which", "with", "you", "your",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> frozenset[str]:
    """Lower-case, split on non-alphanumerics, drop stop words. Deterministic."""
    return frozenset(t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP_WORDS)


@runtime_checkable
class Selector(Protocol):
    """The contract every selector implements — baseline and production alike."""

    name: str

    def select(self, query: str, tools: tuple[ToolSpec, ...]) -> str:
        """Return the `tool_id` this selector picks for `query` from `tools`."""
        ...


class TokenOverlapBaselineSelector:
    """Deterministic, offline, replay-stable lexical baseline.

    Picks the tool whose text shares the highest Jaccard token overlap with the
    query. Exact integer comparison; tie-break on smallest `tool_id`. No network,
    no API key, no randomness, no float arithmetic in the ranking.
    """

    name = "token-overlap-baseline"

    def select(self, query: str, tools: tuple[ToolSpec, ...]) -> str:
        if not tools:
            raise ValueError("cannot select from an empty tool catalogue")
        q = tokenize(query)
        best_id: str | None = None
        # Jaccard = |intersection| / |union|. Compare a/b vs c/d without division
        # via a*d vs c*b (all non-negative integers) so the ranking is exact and
        # platform-independent.
        best_num = 0  # |intersection| of the current best
        best_den = 1  # |union| of the current best (>=1; empty-union scores 0)
        for tool in sorted(tools, key=lambda t: t.tool_id):
            tok = tokenize(tool.search_text())
            inter = len(q & tok)
            union = len(q | tok)
            num, den = (inter, union) if union else (0, 1)
            # Strictly greater (num/den > best_num/best_den) => new best. Equality
            # does NOT displace, so the first (lexicographically smallest tool_id)
            # wins ties — a deterministic-but-ARBITRARY tie-break (carries no query
            # signal; a tool_id rename can swap a tied pair's outcome, e.g. C13/C14
            # at Jaccard 0.125 — see the module docstring, P-MINOR-2).
            if best_id is None or num * best_den > best_num * den:
                best_id, best_num, best_den = tool.tool_id, num, den
        assert best_id is not None  # tools is non-empty
        return best_id
