"""Ownership-map parser.

Reads `model/ownership-map.md` — the SSOT for entity-to-SD ownership
patterns (single owner / key-partitioned / faceted / co-owned). Used by
the generator to render the ownership table on each entity page and to
cross-check entity / SD declarations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ParseError


_ROW_RE = re.compile(r"^\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")
_ENTITY_ID_RE = re.compile(r"\b(E|PM|PB|DR|RA|FO)-(\d{2})\b")
_SD_ID_RE = re.compile(r"\bSD-(\d{2})\.(\d+)\b")


@dataclass
class OwnershipRecord:
    entity_id: str
    owners: list[str]            # one or more SD ids
    pattern: str                 # "Single owner" / "Key-partitioned ..." / "Faceted" / "Co-owned"
    raw_owner_text: str


@dataclass
class OwnershipMap:
    records: dict[str, OwnershipRecord] = field(default_factory=dict)

    def get(self, entity_id: str) -> OwnershipRecord | None:
        return self.records.get(entity_id)


def parse_ownership_map(repo_root: Path) -> OwnershipMap:
    path = repo_root / "model" / "ownership-map.md"
    if not path.is_file():
        raise ParseError(path, None, "ownership-map.md not found")
    text = path.read_text(encoding="utf-8")

    om = OwnershipMap()
    # Find every table row that begins with an entity id and skip header/separator lines.
    for i, raw in enumerate(text.splitlines(), start=1):
        m = _ROW_RE.match(raw)
        if not m:
            continue
        cell1, cell2, cell3 = m.group(1), m.group(2), m.group(3)
        ent_m = _ENTITY_ID_RE.search(cell1)
        if not ent_m:
            continue
        # Skip header (e.g. "Entity") and separator (e.g. "---") rows already
        # filtered: the regex demands "X-NN" in the entity cell.
        ent_id = f"{ent_m.group(1)}-{ent_m.group(2)}"
        if ent_id in om.records:
            raise ParseError(path, i,
                             f"ownership-map duplicate row for {ent_id}")
        # Extract owning SD ids from cell2.
        owners: list[str] = []
        for sm in _SD_ID_RE.finditer(cell2):
            sid = f"SD-{sm.group(1)}.{sm.group(2)}"
            if sid not in owners:
                owners.append(sid)
        if not owners:
            raise ParseError(path, i,
                             f"ownership-map row for {ent_id} names no Service Domain")
        # Pattern cell — strip bold and trailing markdown.
        pattern = re.sub(r"\*+", "", cell3).strip()
        om.records[ent_id] = OwnershipRecord(
            entity_id=ent_id,
            owners=owners,
            pattern=pattern,
            raw_owner_text=cell2,
        )
    if not om.records:
        raise ParseError(path, None, "ownership-map parsed zero rows")
    return om
