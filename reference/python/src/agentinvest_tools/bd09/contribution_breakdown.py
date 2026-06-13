"""SO-09-05 — compute_contribution_breakdown (segment contribution to total return).

Decomposes a portfolio's total return into the contributions of its segments — each segment
(a sector, an asset class, a sleeve, a holding) contributes ``weight x segment_return`` to the
total, and the contributions **sum to the total return**. This is the contribution side of
SD-09.1's outputs (the input to SD-09.2 attribution) and the simplest, exact attribution
identity:

    r_total = sum_i ( w_i * r_i )      with   sum_i w_i = 1

The **segmentation axis is caller-supplied** (sector / asset-class / sleeve / holding) — the tool
is axis-agnostic: it takes labelled (weight, return) segments and computes the contribution per
segment and the total. The contribution-sums-to-total invariant is the same on any axis, so the
tool does not privilege one (the caller chooses sector or asset-class for the BD-09 use; the
common BD-09 axis is asset-class, matching E-09, with sector available for an equity sleeve).

External oracle (hand-verifiable): the contribution identity is exact —
``sum_i w_i * r_i`` equals the supplied/derived total to <= 1 bp absolute, verified in the test
suite against a hand-derived breakdown (no published toy oracle is invented; the summing
identity is the oracle, and a deliberately weight-unbalanced input is rejected).

Honest boundary: a tying breakdown over synthetic weights and returns is a correct *computation*,
not a GIPS-verified production attribution.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Segment weights must sum to ~1. The tolerance absorbs only legitimate rounding in supplied
# weights; a genuinely unbalanced set (weights that do not partition the portfolio) is rejected
# rather than silently producing a contribution total that is not the portfolio's return.
_WEIGHT_SUM_TOLERANCE = Decimal("0.0001")


class SegmentInput(BaseModel):
    """One segment of the portfolio on the caller's chosen segmentation axis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment: str = Field(description="The segment label (sector / asset-class / sleeve / holding).")
    weight: Decimal = Field(
        description="The segment's weight in the portfolio over the period (the weights sum to 1)."
    )
    segment_return: Decimal = Field(
        description="The segment's own return over the period (a rate)."
    )


class SegmentContribution(BaseModel):
    """One segment's contribution to the total return."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment: str = Field(description="The segment label.")
    weight: Decimal = Field(description="The segment's weight.")
    segment_return: Decimal = Field(description="The segment's return.")
    contribution: Decimal = Field(
        description="weight x segment_return — the contribution to total."
    )


class ContributionBreakdownInput(BaseModel):
    """Inputs to the contribution breakdown for one portfolio over one window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    segments: tuple[SegmentInput, ...] = Field(
        description="The labelled segments; weights sum to 1 (within rounding tolerance).",
    )

    @model_validator(mode="after")
    def _segments_present_and_balanced(self) -> ContributionBreakdownInput:
        if not self.segments:
            raise ValueError("contribution breakdown needs at least one segment")
        weight_sum = sum((s.weight for s in self.segments), Decimal(0))
        if abs(weight_sum - Decimal(1)) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError(
                f"segment weights sum to {weight_sum}, not 1 — they must partition the portfolio"
            )
        return self


class ContributionBreakdownOutput(BaseModel):
    """The per-segment contributions plus the total they sum to."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contributions: tuple[SegmentContribution, ...] = Field(
        description="Per-segment contribution (weight x return), in input order."
    )
    total_return: Decimal = Field(
        description="Sum of the contributions — the portfolio total return."
    )
    methodology: str = Field(
        description="The method label — 'contribution-weight-times-return'."
    )


def so_09_05_compute_contribution_breakdown(
    inp: ContributionBreakdownInput,
) -> ContributionBreakdownOutput:
    """Compute the segment contribution breakdown for a portfolio. SO-09-05.

    Pure and deterministic: per-segment ``weight x segment_return`` summed in input order (no
    I/O, clock, RNG or dict-order dependence — segments are an ordered tuple). The contributions
    sum, by construction, to the total return.
    """
    contributions = tuple(
        SegmentContribution(
            segment=s.segment,
            weight=s.weight,
            segment_return=s.segment_return,
            contribution=s.weight * s.segment_return,
        )
        for s in inp.segments
    )
    total = sum((c.contribution for c in contributions), Decimal(0))
    return ContributionBreakdownOutput(
        contributions=contributions,
        total_return=total,
        methodology="contribution-weight-times-return",
    )
