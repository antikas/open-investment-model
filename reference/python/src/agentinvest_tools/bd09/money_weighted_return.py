"""SO-09-03 — compute_money_weighted_return (IRR / MWR).

Money-weighted return: the internal rate of return on the dated cash-flow series — the single
rate ``r`` that discounts every dated flow to a net present value of zero. Unlike TWR, MWR
*does* reflect the timing and size of external flows, so it is the investor's actually-experienced
return and the standard performance basis in private markets (where the GP controls deployment
and exit timing). This realises the SD-09.1 "calculate money-weighted return" Service Operation;
the dated cash-flow series is E-06 Cash Flow Event (the IRR input series) plus, in private
markets, the PM-07 / PM-08 call and distribution legs.

Method (the published IRR / NPV-root formula):

    sum_k  CF_k / (1 + r) ** t_k  =  0

where ``CF_k`` is the signed flow (contribution / capital call < 0 from the investor's view,
distribution > 0, and the terminal NAV a positive flow at the end), and ``t_k`` is the flow's
time in periods (years, for an annualised IRR). The root is found by a **deterministic
bracketed bisection** on a sign-change interval — deterministic and replay-stable (no RNG, no
seed, no Newton starting-point sensitivity).

External oracle (build-gate §A2): matched in the test suite to the published worked example in
the AnalystPrep CFA Level I "Money-Weighted and Time-Weighted Rates of Return" notes (flows
−10,000 at t=0, −5,000 at t=1, +25,000 at t=2 → IRR ≈ 35.08%) to <= 1 bp absolute. The
published figure is the proof.

Conventional series only — the solver fails loud on non-conventional input. A *conventional*
cash-flow series has exactly **one** sign change in time order (an outflow block followed by an
inflow block, or the inverted lending case): by Descartes' rule of signs it has a unique
positive IRR, which the bracketed bisection finds. A *non-conventional* series — more than one
sign change in time order — may have multiple real IRRs or none in range, and a single-root
solver would return one arbitrary root with no signal that others are equally valid. Such series
are common for private-markets J-curve flows (capital calls and distributions interleave). To
avoid a silently-wrong IRR on valid input (a fiduciary landmine), the solver counts sign changes
up front and **raises** :class:`NonConventionalCashFlowError` when there is more than one — it
fails loud rather than returning a number a caller cannot trust.

Deferred (a carry-forward, not built here): the *resolution* of a non-conventional series — the
economically-meaningful root, an interior multi-root enumeration, or a modified IRR (MIRR) with
an explicit reinvestment assumption — is a future hardening item (the dispatch-service and
planning-loop path). This tool is made *safe* (fail-loud) on non-conventional input, not
*complete* on it. A caller needing a figure for an interleaved-flow series uses MWR-with-an-
explicit-reinvestment-rate or supplies an explicit bracket, which this layer does not yet offer.

Honest boundary: a correct IRR over synthetic flows is a correct *computation*, not a
GIPS-verified production return. The cash-flow series (E-06 Cash Flow Event) is not present in
the synthetic seed, so the synthetic-integration path for this tool is limited to oracle /
typed-input testing; the flows are taken as typed inputs rather than fabricated.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Bracket and convergence for the deterministic bisection. The bracket spans economically
# meaningful annual rates (a near-total loss up to a 100x gain); a series whose root lies
# outside it raises rather than returning a mis-bracketed number. The tolerance is far tighter
# than the §A2 1 bp gate so solver convergence is never the limiting error.
_RATE_LOWER = -0.999999
_RATE_UPPER = 100.0
_NPV_TOLERANCE = 1e-12
_MAX_ITERATIONS = 200


class NonConventionalCashFlowError(ValueError):
    """Raised when the cash-flow series is non-conventional (more than one sign change).

    A non-conventional series may have multiple real IRRs or none in range, so a single-root
    bracketed bisection cannot return *the* IRR — it would return one arbitrary root with no
    signal that others are equally valid. The solver raises this rather than returning a number
    a caller cannot trust. Subclasses :class:`ValueError` so existing error handling that catches
    ``ValueError`` still works; the dedicated type lets a caller distinguish "non-conventional
    series — needs MIRR or an explicit bracket" from the other input-validation failures.
    """


class DatedCashFlow(BaseModel):
    """One dated cash flow in the series.

    ``time`` is the flow's time in periods from the start (e.g. years, for an annualised IRR).
    ``amount`` is signed from the investor's perspective: a contribution / capital call is
    negative, a distribution is positive, and the terminal portfolio value is a positive flow at
    the final time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    time: Decimal = Field(
        ge=0, description="Time of the flow in periods from the start (e.g. years)."
    )
    amount: Decimal = Field(
        description="Signed flow — contribution/call < 0, distribution/NAV > 0."
    )


class MoneyWeightedReturnInput(BaseModel):
    """Inputs to the money-weighted return (IRR) over a dated cash-flow series."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cash_flows: tuple[DatedCashFlow, ...] = Field(
        description="The dated, signed cash-flow series; must contain a sign change for a root.",
    )

    @model_validator(mode="after")
    def _has_sign_change(self) -> MoneyWeightedReturnInput:
        if len(self.cash_flows) < 2:
            raise ValueError("money-weighted return needs at least two cash flows")
        signs = {1 if cf.amount > 0 else -1 if cf.amount < 0 else 0 for cf in self.cash_flows}
        if 1 not in signs or -1 not in signs:
            raise ValueError(
                "money-weighted return is undefined without both an inflow and an outflow"
            )
        return self


class MoneyWeightedReturnOutput(BaseModel):
    """The money-weighted return (IRR) plus provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    money_weighted_return: Decimal = Field(
        description="The IRR of the dated cash-flow series (a per-period rate)."
    )
    iterations: int = Field(
        description="Bisection iterations to convergence (a determinism witness)."
    )
    methodology: str = Field(description="The method label — 'money-weighted-irr'.")


def _npv(rate: float, flows: tuple[tuple[float, float], ...]) -> float:
    """Net present value of the (time, amount) flows at ``rate``."""
    return float(sum(amount / (1.0 + rate) ** t for t, amount in flows))


def _count_sign_changes(flows: tuple[tuple[float, float], ...]) -> int:
    """Count sign changes in the time-ordered amount sequence (Descartes' rule of signs).

    Flows are ordered by time, zero amounts are ignored, and the number of transitions between a
    positive and a negative amount is counted. Exactly one sign change is a *conventional* series
    (a unique positive IRR); more than one is *non-conventional* (possibly multiple IRRs or none).
    """
    ordered = sorted(flows, key=lambda f: f[0])
    signs = [1 if amount > 0 else -1 for _, amount in ordered if amount != 0.0]
    return sum(1 for a, b in zip(signs, signs[1:], strict=False) if a != b)


def so_09_03_compute_money_weighted_return(
    inp: MoneyWeightedReturnInput,
) -> MoneyWeightedReturnOutput:
    """Compute the money-weighted return (IRR) for a dated cash-flow series. SO-09-03.

    Deterministic: a bracketed bisection on a fixed ``[_RATE_LOWER, _RATE_UPPER]`` interval —
    the same series always yields the same root in the same number of iterations (no RNG, no
    starting-point sensitivity).

    Conventional series only — fails loud otherwise. Raises
    :class:`NonConventionalCashFlowError` when the series has more than one sign change in time
    order (non-conventional → the IRR may be non-unique or absent; a single-root solver cannot
    return *the* IRR — see the module docstring for the deferred resolution path). Raises a plain
    ``ValueError`` if a conventional root is not bracketed by the interval (the IRR lies outside
    the economically-meaningful range, or the series is otherwise degenerate).
    """
    flows = tuple((float(cf.time), float(cf.amount)) for cf in inp.cash_flows)

    sign_changes = _count_sign_changes(flows)
    if sign_changes > 1:
        raise NonConventionalCashFlowError(
            "money-weighted return is not guaranteed unique or present for a non-conventional "
            f"cash-flow series ({sign_changes} sign changes in time order; a conventional series "
            "has exactly one). The IRR may be multiple-valued or absent — use a modified IRR "
            "(MIRR) with an explicit reinvestment rate, or supply an explicit bracket."
        )

    low, high = _RATE_LOWER, _RATE_UPPER
    npv_low, npv_high = _npv(low, flows), _npv(high, flows)
    if npv_low == 0.0:
        return MoneyWeightedReturnOutput(
            money_weighted_return=Decimal(repr(low)),
            iterations=0,
            methodology="money-weighted-irr",
        )
    if npv_low * npv_high > 0:
        raise ValueError(
            "money-weighted return is not bracketed in the supported rate range "
            f"[{_RATE_LOWER}, {_RATE_UPPER}] — the IRR is outside it or the series degenerate"
        )

    mid = (low + high) / 2.0
    iterations = 0
    for step in range(1, _MAX_ITERATIONS + 1):
        iterations = step
        mid = (low + high) / 2.0
        npv_mid = _npv(mid, flows)
        if abs(npv_mid) < _NPV_TOLERANCE or (high - low) / 2.0 < _NPV_TOLERANCE:
            break
        if (npv_mid > 0) == (npv_low > 0):
            low, npv_low = mid, npv_mid
        else:
            high = mid

    return MoneyWeightedReturnOutput(
        money_weighted_return=Decimal(repr(mid)),
        iterations=iterations,
        methodology="money-weighted-irr",
    )
