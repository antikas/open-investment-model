"""Parser error type — raised on any unhandled markdown structure."""
from __future__ import annotations
from pathlib import Path


class ParseError(ValueError):
    """A strict-parser failure.

    Carries the offending file path, the 1-indexed line number, and a
    one-clause reason. The generator surfaces these to stderr and exits
    non-zero per criterion (c) in the OIM-54 cycle goal.
    """

    def __init__(self, path: Path | str, line: int | None, reason: str) -> None:
        self.path = Path(path)
        self.line = line
        self.reason = reason
        loc = f"{self.path}:{line}" if line else str(self.path)
        super().__init__(f"{loc} — {reason}")
