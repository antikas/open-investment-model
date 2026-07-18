"""Entity-file parser.

Reads `model/entities/INDEX.md` plus every entity file under
`core/` and `specialisations/<pack>/`. The output `EntityModel` carries
the entity records, the FK declarations, the owning + consuming SDs (as
declared on the entity file's `## Owned and consumed by` section), and
the specialisation parent for pack entities.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ParseError

import pack_registry

# Entity-id prefix alternations are single-sourced from the pack registry so a
# new pack is one edit there, not another regex to remember here (OIM-211).
_PFX = pack_registry.PREFIX_ALT

_ENTITY_FILE_RE = re.compile(r"^(" + _PFX + r")-(\d{2})-(.+)\.md$")
_ENTITY_ID_RE = re.compile(r"\b(" + _PFX + r")-(\d{2})\b")
_SD_ID_RE = re.compile(r"\bSD-(\d{2})\.(\d+)\b")
# The FK target expression after `FK -> ` — extended additively (OIM-idf2 2a)
# to also match a brace-set union `{A, B}` (polymorphic FK) and the literal
# `self` (self-FK); the plain single-id branch also covers the id-notation
# self-FK (`FK -> <own-entity-id>`, e.g. `FK -> FO-07, self-ref` or the bare
# `FK -> FO-01` on FO-01 itself) — resolved against `ent_id` below. Mirrors
# the exports parser's `_FK_ENTITY_RE` (`tools/exports/model_parse.py`).
_FK_RE = re.compile(
    r"FK\s*[\->→]+\s*"
    r"(\{[^}]*\}|self\b|(?:" + _PFX + r")[_-]?\d{2,3})",
    re.IGNORECASE)
# One brace-set member, validated after the outer brace-set is captured.
_FK_ID_TOKEN_RE = re.compile(r"^(?:" + _PFX + r")[_-]?\d{2,3}$", re.IGNORECASE)
_TITLE_RE = re.compile(r"^#\s+(" + _PFX + r")-(\d{2})\s+[—-]\s+(.+?)\s*$")
_SPECIALISES_RE = re.compile(r"\*\*Specialises:\*\*\s*((?:" + _PFX + r")-\d{2})")


@dataclass
class Entity:
    id: str                              # "E-NN" / "PM-NN" / "PB-NN" / "DR-NN" / "RA-NN"
    prefix: str                          # "E" / "PM" / "PB" / "DR" / "RA"
    num: int
    name: str                            # title text
    path: Path
    summary: str = ""                    # first paragraph after H1
    specialises: str | None = None       # parent entity id (specialisation packs only)
    owned_by: list[str] = field(default_factory=list)        # SD ids (one or several)
    consumed_by: list[str] = field(default_factory=list)     # SD ids
    fk_targets: list[str] = field(default_factory=list)       # entity ids referenced as FKs
    # deduped cross-entity FK targets only — unchanged semantics: a brace-set
    # union now contributes every non-self member here (additive, OIM-idf2
    # 2a); a self-FK (either notation) never appears in this list, same as
    # before — see `self_fk` below, which makes the self-edge first-class
    # instead of silently dropping it.
    self_fk: bool = False
    # True when the entity carries at least one self-referential FK column,
    # in either notation: the literal `FK -> self`, or the id-notation
    # `FK -> <own-entity-id>` (e.g. `FK -> FO-07, self-ref` / bare `FK -> FO-01`
    # on FO-01 itself).

    @property
    def pack(self) -> str:
        """`core` for E-NN, the pack-slug ("private-markets" etc.) for others."""
        return pack_registry.PREFIX_TO_SLUG[self.prefix]


@dataclass
class EntityModel:
    entities: list[Entity]

    def by_id(self) -> dict[str, Entity]:
        return {e.id: e for e in self.entities}

    def by_pack(self) -> dict[str, list[Entity]]:
        out: dict[str, list[Entity]] = {}
        for e in self.entities:
            out.setdefault(e.pack, []).append(e)
        return out


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _line_no(text: str, ix: int) -> int:
    return text.count("\n", 0, ix) + 1


def _extract_section(text: str, heading: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(heading)}\s*$", re.MULTILINE)
    m = pattern.search(text)
    if not m:
        return None
    start = m.end()
    nxt = re.search(r"^#{1,2}\s+\S", text[start:], re.MULTILINE)
    end = start + nxt.start() if nxt else len(text)
    return text[start:end].strip("\n")


def _extract_bold_block(body: str, label: str) -> str | None:
    pattern = re.compile(
        rf"^\s*-\s+\*\*{re.escape(label)}:?\*\*([^\n]*(?:\n(?!\s*-\s|\s*\*\*|\s*$)[^\n]*)*)",
        re.MULTILINE,
    )
    m = pattern.search(body)
    if not m:
        return None
    return m.group(1).strip()


def _normalise_entity_id(raw: str) -> str:
    """Map FK match like 'E_09' or 'E-09' or 'E09' to canonical 'E-09'."""
    raw = raw.replace("_", "-")
    if "-" not in raw:
        # 'E09' -> 'E-09'
        for prefix in pack_registry.SPEC_PREFIXES:
            if raw.upper().startswith(prefix):
                return f"{prefix}-{raw[len(prefix):].zfill(2)}"
        return f"{raw[0].upper()}-{raw[1:].zfill(2)}"
    a, b = raw.split("-", 1)
    return f"{a.upper()}-{b.zfill(2)}"


def _parse_entity_file(path: Path, expected_prefix: str, expected_num: int) -> Entity:
    text = _read(path)
    lines = text.splitlines()
    if not lines:
        raise ParseError(path, 1, "empty entity file")
    m = _TITLE_RE.match(lines[0])
    if not m:
        raise ParseError(path, 1,
                         "entity H1 does not match '# X-NN — Title' (X in E/PM/PB/DR/RA)")
    pfx, num = m.group(1), int(m.group(2))
    if pfx != expected_prefix or num != expected_num:
        raise ParseError(path, 1,
                         f"entity H1 says {pfx}-{num:02d} but file is "
                         f"{expected_prefix}-{expected_num:02d}")
    name = m.group(3).strip()
    ent_id = f"{pfx}-{num:02d}"

    # First paragraph after the H1.
    summary = ""
    para_lines: list[str] = []
    for raw in lines[1:]:
        if raw.strip() == "" and not para_lines:
            continue
        if raw.startswith("#") or raw.startswith("**"):
            if para_lines:
                break
            else:
                continue
        if raw.strip() == "" and para_lines:
            break
        para_lines.append(raw.strip())
    if para_lines:
        summary = " ".join(para_lines).strip()

    ent = Entity(id=ent_id, prefix=pfx, num=num, name=name, path=path, summary=summary)

    sp = _SPECIALISES_RE.search(text)
    if sp:
        ent.specialises = sp.group(1)

    # FK declarations — anywhere in the file (attribute schema tables).
    fk_targets: list[str] = []
    self_fk = False
    for fk_m in _FK_RE.finditer(text):
        expr = fk_m.group(1)
        if expr.lower() == "self":
            self_fk = True
            continue
        if expr.startswith("{"):
            inner = expr[1:-1]
            raw_tokens = [t.strip() for t in inner.split(",")]
            if not inner.strip() or any(not t for t in raw_tokens):
                raise ParseError(
                    path, None,
                    f"{ent_id} has a malformed FK brace-set '{expr}' — "
                    f"empty or has an empty member")
            for tok in raw_tokens:
                if not _FK_ID_TOKEN_RE.match(tok):
                    raise ParseError(
                        path, None,
                        f"{ent_id} has a malformed FK brace-set member "
                        f"'{tok}' (from '{expr}') — not a recognised "
                        f"entity id")
                target = _normalise_entity_id(tok)
                if target == ent_id:
                    self_fk = True
                elif target not in fk_targets:
                    fk_targets.append(target)
            continue
        target = _normalise_entity_id(expr)
        if target == ent_id:
            self_fk = True
        elif target not in fk_targets:
            fk_targets.append(target)
    ent.fk_targets = fk_targets
    ent.self_fk = self_fk

    # Ownership / consumption.
    own_sect = _extract_section(text, "## Owned and consumed by")
    if not own_sect:
        raise ParseError(path, None,
                         "entity file missing '## Owned and consumed by' section")
    owned_by_text = _extract_bold_block(own_sect, "Owned by")
    consumed_by_text = _extract_bold_block(own_sect, "Consumed by")
    if not owned_by_text:
        raise ParseError(path, None,
                         "entity '## Owned and consumed by' missing '**Owned by:**' line")
    if not consumed_by_text:
        raise ParseError(path, None,
                         "entity '## Owned and consumed by' missing '**Consumed by:**' line")

    seen: list[str] = []
    for sm in _SD_ID_RE.finditer(owned_by_text):
        sid = f"SD-{sm.group(1)}.{sm.group(2)}"
        if sid not in seen:
            seen.append(sid)
    ent.owned_by = seen

    # Extract SD ids from the *structured consumer list* only — not from any
    # trailing prose clarification sentence.
    #
    # Entity files occasionally carry a clarifying sentence after the structured
    # semicolon-separated consumer list, e.g.:
    #   "…SD-16.1 Corporate & Fund Governance (…). The E-01 party records
    #    referenced … are mastered by SD-13.2 … not a consumer …"
    #
    # The structured list ends at the last `);` or `).` that closes the final
    # consumer entry; any prose that follows (a new sentence starting after a
    # period) is excluded.  The split pattern `). ` followed by a capital
    # letter (or `\n`) detects the boundary.
    m_prose = re.search(r'\)\.\s+[A-Z\n]', consumed_by_text)
    structured_consumer_text = (
        consumed_by_text[: m_prose.start() + 2]  # include the closing ').'
        if m_prose else consumed_by_text
    )
    seen = []
    for sm in _SD_ID_RE.finditer(structured_consumer_text):
        sid = f"SD-{sm.group(1)}.{sm.group(2)}"
        if sid not in seen:
            seen.append(sid)
    ent.consumed_by = seen

    if not ent.owned_by:
        raise ParseError(path, None,
                         "entity '**Owned by:**' line names no Service Domain")
    return ent


def parse_entities(repo_root: Path) -> EntityModel:
    ent_dir = repo_root / "model" / "entities"
    if not ent_dir.is_dir():
        raise ParseError(ent_dir, None, "entities directory not found")

    entities: list[Entity] = []

    # Core.
    core_dir = ent_dir / "core"
    if not core_dir.is_dir():
        raise ParseError(core_dir, None, "entities/core directory not found")
    for p in sorted(core_dir.glob("*.md")):
        if p.name.upper().startswith("README"):
            continue
        m = _ENTITY_FILE_RE.match(p.name)
        if not m:
            raise ParseError(p, None,
                             f"core entity filename does not match X-NN-slug.md "
                             f"(got {p.name})")
        if m.group(1) != "E":
            raise ParseError(p, None,
                             f"core entity has non-E prefix ({m.group(1)})")
        entities.append(_parse_entity_file(p, "E", int(m.group(2))))

    # Specialisation packs.
    spec_dir = ent_dir / "specialisations"
    if spec_dir.is_dir():
        for pack_dir in sorted(spec_dir.iterdir()):
            if not pack_dir.is_dir():
                continue
            if pack_dir.name not in pack_registry.SLUG_TO_PREFIX:
                raise ParseError(pack_dir, None,
                                 f"unknown specialisation pack {pack_dir.name!r}")
            expected_pfx = pack_registry.SLUG_TO_PREFIX[pack_dir.name]
            for p in sorted(pack_dir.glob("*.md")):
                if p.name.upper().startswith("README"):
                    continue
                m = _ENTITY_FILE_RE.match(p.name)
                if not m:
                    raise ParseError(p, None,
                                     f"pack entity filename does not match X-NN-slug.md")
                if m.group(1) != expected_pfx:
                    raise ParseError(p, None,
                                     f"pack entity has prefix {m.group(1)}, "
                                     f"expected {expected_pfx}")
                entities.append(_parse_entity_file(p, expected_pfx, int(m.group(2))))

    return EntityModel(entities=entities)


def validate_entity_references(em: EntityModel) -> None:
    """Every FK target and Specialises target must resolve to a known entity."""
    known = {e.id for e in em.entities}
    for e in em.entities:
        if e.specialises and e.specialises not in known:
            raise ParseError(e.path, None,
                             f"{e.id} **Specialises:** unknown {e.specialises}")
        for fk in e.fk_targets:
            if fk not in known:
                # FKs to abstract types (e.g. "Fund Family") slip through the
                # regex when prefixed with a known pack letter; ignore those
                # whose number doesn't exist rather than failing.
                # Conservative: just record a defect once the entity list is
                # complete.
                raise ParseError(e.path, None,
                                 f"{e.id} FK -> unknown entity {fk}")


def validate_entity_sd_references(em: EntityModel, sd_ids: set[str]) -> None:
    """Every SD named on an entity's Owned by / Consumed by line must exist."""
    for e in em.entities:
        for sid in e.owned_by + e.consumed_by:
            if sid not in sd_ids:
                raise ParseError(e.path, None,
                                 f"{e.id} references unknown {sid}")
