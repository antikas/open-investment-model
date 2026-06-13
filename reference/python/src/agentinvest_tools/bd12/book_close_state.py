"""SO-12.2-04 — read the ABOR book-close state (period-lock status, as-of).

SD-12.2 ABOR's *book close* Service Operation: the periodic close cuts off activity, completes
accruals, validates and **locks** the accounting book for the period. Downstream consumers
(NAV, reporting, audit) need to know whether the book they are reading is locked (closed) for a
period or still open. This tool reports the period-lock status of the ABOR book at an as-of date.

Honest derivation — no fabricated lock state. The canonical layer carries a single struck
ABOR book at one ``as_of_date`` (2026-03-31) and **no explicit period-lock column** (a book-close
state machine is a later structure, not seeded here). So this tool derives the status
honestly from what the layer carries: the ABOR book is treated as **closed/locked** for any period
whose end date is on or before the latest struck book date the data-access layer reports, and
**open** for any later period. It never invents a lock flag; it reports the derivation and the
struck book date it is based on, with the explicit note that the period-lock is derived, not a
seeded state-machine flag.

Pure and deterministic: the latest struck book date is read by the data-access layer and passed in;
this tool compares it to the requested as-of. No I/O, no clock, no RNG.

Honest boundary: a correct *derived* read over a **synthetic** book — there is no seeded
book-close state machine; the lock status is derived from the struck-book date, not read from a
period-lock ledger.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CloseStatus = Literal["closed", "open"]


class ReadBookCloseStateInput(BaseModel):
    """Inputs to the ABOR book-close-state read — the as-of and the latest struck book date."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of_date: date = Field(description="The period end date whose close status to report.")
    latest_struck_book_date: date = Field(
        description="The latest ABOR book date the canonical layer carries (from the data layer)."
    )


class ReadBookCloseStateOutput(BaseModel):
    """The derived ABOR book-close state — the status, the struck-book date, the derivation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of_date: date = Field(description="The period end date the status is for.")
    latest_struck_book_date: date = Field(description="The latest struck ABOR book date held.")
    status: CloseStatus = Field(
        description="'closed' (locked — the book is struck for this period) or 'open'."
    )
    is_locked: bool = Field(description="True iff the ABOR book is closed/locked for the period.")
    derivation: str = Field(
        description="The honest note: the lock is DERIVED from the struck-book date, not a flag."
    )


_DERIVATION_NOTE = (
    "period-lock DERIVED from the latest struck ABOR book date (closed iff as_of <= struck date); "
    "the canonical layer carries no seeded book-close state machine — a correct derived read, "
    "not a read of a period-lock ledger"
)


def read_abor_book_close_state(inp: ReadBookCloseStateInput) -> ReadBookCloseStateOutput:
    """Report the ABOR book-close (period-lock) state at the as-of date. SO-12.2-04.

    Pure and deterministic: the book is 'closed' (locked) for the as-of period iff the requested
    as-of date is on or before the latest struck ABOR book date the data-access layer reports, else
    'open'. The derivation is reported explicitly — there is no seeded book-close state machine, so
    the status is honestly derived from the struck-book date, never a fabricated lock flag.
    """
    is_locked = inp.as_of_date <= inp.latest_struck_book_date
    return ReadBookCloseStateOutput(
        as_of_date=inp.as_of_date,
        latest_struck_book_date=inp.latest_struck_book_date,
        status="closed" if is_locked else "open",
        is_locked=is_locked,
        derivation=_DERIVATION_NOTE,
    )
