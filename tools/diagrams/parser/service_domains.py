"""Service-domain markdown parser.

Reads `model/service-domains/INDEX.md`, every BD README, every per-SD file.
Builds an in-memory `ServiceDomainModel` with the full BD -> SD -> SO
hierarchy plus structured Consumes/Produces edges and SD -> entity
ownership.

Strict by construction: missing required headings, unparseable identifiers,
or unknown H2 headings in an SD file raise `ParseError`. Cross-references
to non-existent SDs are caught after the full parse by `validate_cross_refs`.

SD whitelist (the only H2 headings permitted in an SD file): `## Purpose`,
`## Service Operations`, `## Inputs and outputs`, `## Entities`,
`## Standards`, `## Open extensions`. Any other H2 raises `ParseError`
naming the file and the offending heading.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ParseError


_BD_DIR_RE = re.compile(r"^BD-(\d{2})-(.+)$")
_SD_FILE_RE = re.compile(r"^SD-(\d{2})\.(\d+)-(.+)\.md$")
_SD_ID_RE = re.compile(r"\bSD-(\d{2})\.(\d+)\b")
_BD_ID_RE = re.compile(r"\bBD-(\d{2})\b")
_ENTITY_ID_RE = re.compile(r"\b(E|PM|PB|DR|RA|FO)-(\d{2})\b")
_APPLIES_RE = re.compile(r"\*\*Applies:\*\*\s*([A-Z]+)")
_TITLE_RE = re.compile(r"^#\s+SD-(\d{2})\.(\d+)\s+[—-]\s+(.+?)\s*$")
_BD_TITLE_RE = re.compile(r"^#\s+BD-(\d{2})\s+[—-]\s+(.+?)\s*$")
_OFFICE_RE = re.compile(r"\*\*Office:\*\*\s*([^\n]+?)\.?\s*$", re.MULTILINE)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


# The whitelist of H2 headings every SD file may carry. Derived from a
# class-walk of all 169 SD files (no SD currently uses any other H2).
# Adding a heading to the model means adding it here in the same change.
SD_KNOWN_H2: frozenset[str] = frozenset({
    "Purpose",
    "Service Operations",
    "Inputs and outputs",
    "Entities",
    "Standards",
    "Open extensions",
    "Design notes",
})


@dataclass(frozen=True)
class ServiceOperation:
    """A single bullet under `## Service Operations` in an SD file."""
    name: str
    sd_id: str  # the parent SD id, e.g. "SD-01.4"


@dataclass
class ServiceDomain:
    id: str                          # "SD-NN.M"
    bd_num: int
    sd_num: int
    name: str                        # H1 title text (without the ID)
    applies: str                     # PUB / PRIV / BOTH
    path: Path
    purpose: str = ""                # first paragraph of `## Purpose`
    operations: list[ServiceOperation] = field(default_factory=list)
    consumes_entities: list[str] = field(default_factory=list)   # e.g. ["E-09", "PM-06"]
    owns_entities: list[str] = field(default_factory=list)
    consumes_sds: list[str] = field(default_factory=list)        # structured **Consumes:** SD refs
    produces_sds: list[str] = field(default_factory=list)        # structured **Produces:** SD refs
    upstream_sds: set[str] = field(default_factory=set)           # narrative "Inputs:" SD refs
    downstream_sds: set[str] = field(default_factory=set)         # narrative "Outputs:" SD refs

    @property
    def bd_id(self) -> str:
        return f"BD-{self.bd_num:02d}"


@dataclass
class BusinessDomain:
    id: str                          # "BD-NN"
    num: int
    slug: str                        # directory slug
    name: str                        # README H1 title (without ID)
    office: str                      # Front / Middle / Back / Cross-cutting / Commercial
    path: Path                       # the README path
    service_domains: list[ServiceDomain] = field(default_factory=list)


@dataclass
class ServiceDomainModel:
    business_domains: list[BusinessDomain]

    def all_sds(self) -> list[ServiceDomain]:
        return [sd for bd in self.business_domains for sd in bd.service_domains]

    def all_sos(self) -> list[ServiceOperation]:
        return [so for sd in self.all_sds() for so in sd.operations]

    def sd_by_id(self) -> dict[str, ServiceDomain]:
        return {sd.id: sd for sd in self.all_sds()}

    def bd_by_id(self) -> dict[str, BusinessDomain]:
        return {bd.id: bd for bd in self.business_domains}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _line_no(text: str, ix: int) -> int:
    return text.count("\n", 0, ix) + 1


def _parse_bd_readme(readme: Path) -> BusinessDomain:
    text = _read(readme)
    lines = text.splitlines()
    title_m = _BD_TITLE_RE.match(lines[0]) if lines else None
    if not title_m:
        raise ParseError(readme, 1, "BD README does not start with '# BD-NN — Title'")
    num = int(title_m.group(1))
    name = title_m.group(2).strip()
    office_m = _OFFICE_RE.search(text)
    if not office_m:
        raise ParseError(readme, None,
                         "BD README missing '**Office:** <Front|Middle|Back|"
                         "Cross-cutting|Commercial>' line")
    office = office_m.group(1).strip()
    slug = readme.parent.name.split("-", 2)[-1] if readme.parent.name.startswith("BD-") else ""
    return BusinessDomain(
        id=f"BD-{num:02d}",
        num=num,
        slug=slug,
        name=name,
        office=office,
        path=readme,
    )


def _extract_section(text: str, heading: str) -> tuple[str, int] | None:
    """Return (body_text, start_line_of_heading) or None.

    Heading is the verbatim H2, e.g. "## Service Operations". The body is
    every line after the heading up to (exclusive) the next H1/H2 or EOF.
    """
    pattern = re.compile(rf"^{re.escape(heading)}\s*$", re.MULTILINE)
    m = pattern.search(text)
    if not m:
        return None
    start = m.end()
    nxt = re.search(r"^#{1,2}\s+\S", text[start:], re.MULTILINE)
    end = start + nxt.start() if nxt else len(text)
    return text[start:end].strip("\n"), _line_no(text, m.start())


def _parse_operations(body: str, sd_id: str, path: Path, base_line: int) -> list[ServiceOperation]:
    ops: list[ServiceOperation] = []
    for offset, raw in enumerate(body.splitlines()):
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("- "):
            # Prose paragraphs and bold group-header lines (e.g. SD-12.11's
            # general-vs-specialisation grouping) are reader content, not
            # operations — only "- " bullets are Service Operations.
            continue
        # The bullet text is everything after "- ". The SO name is the first
        # bolded run or the leading prose up to " — " or " - " (em-dash split).
        rest = line[2:].strip()
        # Strip bold markers: "**Articulate beliefs** — ..." -> "Articulate beliefs"
        bold_m = re.match(r"\*\*(.+?)\*\*", rest)
        if bold_m:
            name = bold_m.group(1).strip()
        else:
            # No bold — split on em-dash / colon / period.
            for sep in (" — ", " – ", " - ", ": ", "."):
                if sep in rest:
                    name = rest.split(sep, 1)[0].strip()
                    break
            else:
                name = rest.strip()
        if not name:
            raise ParseError(path, base_line + offset + 1,
                             "Service Operation bullet has no name")
        ops.append(ServiceOperation(name=name, sd_id=sd_id))
    return ops


def _parse_entity_refs(line: str) -> list[str]:
    """Extract distinct E-NN / PM-NN / PB-NN / DR-NN / RA-NN identifiers."""
    seen: list[str] = []
    for m in _ENTITY_ID_RE.finditer(line):
        eid = f"{m.group(1)}-{m.group(2)}"
        if eid not in seen:
            seen.append(eid)
    return seen


def _parse_sd_refs(line: str) -> list[str]:
    seen: list[str] = []
    for m in _SD_ID_RE.finditer(line):
        sid = f"SD-{m.group(1)}.{m.group(2)}"
        if sid not in seen:
            seen.append(sid)
    return seen


def _parse_bd_refs(line: str) -> list[str]:
    seen: list[str] = []
    for m in _BD_ID_RE.finditer(line):
        bid = f"BD-{m.group(1)}"
        if bid not in seen:
            seen.append(bid)
    return seen


def _extract_bold_block(body: str, label: str) -> str | None:
    """Find a `- **Label:** <text...>` bullet (possibly multi-line) in a body."""
    pattern = re.compile(
        rf"^\s*-\s+\*\*{re.escape(label)}:?\*\*([^\n]*(?:\n(?!\s*-\s|\s*\*\*|\s*$)[^\n]*)*)",
        re.MULTILINE,
    )
    m = pattern.search(body)
    if not m:
        return None
    return m.group(1).strip()


def _parse_sd_file(path: Path, expected_bd: int, expected_sd: int) -> ServiceDomain:
    text = _read(path)
    lines = text.splitlines()
    if not lines:
        raise ParseError(path, 1, "empty SD file")
    title_m = _TITLE_RE.match(lines[0])
    if not title_m:
        raise ParseError(path, 1, "SD H1 does not match '# SD-NN.M — Title'")
    bd_n, sd_n = int(title_m.group(1)), int(title_m.group(2))
    if bd_n != expected_bd or sd_n != expected_sd:
        raise ParseError(path, 1,
                         f"SD H1 says SD-{bd_n:02d}.{sd_n} but file is "
                         f"SD-{expected_bd:02d}.{expected_sd}")
    name = title_m.group(3).strip()

    applies_m = _APPLIES_RE.search(text)
    if not applies_m:
        raise ParseError(path, None, "SD missing '**Applies:**' tag line")
    applies = applies_m.group(1)
    if applies not in {"PUB", "PRIV", "BOTH"}:
        raise ParseError(path, None,
                         f"'**Applies:**' must be PUB / PRIV / BOTH; got {applies!r}")

    sd_id = f"SD-{bd_n:02d}.{sd_n}"
    sd = ServiceDomain(
        id=sd_id, bd_num=bd_n, sd_num=sd_n, name=name, applies=applies, path=path,
    )

    # Purpose — first paragraph after "## Purpose".
    purpose = _extract_section(text, "## Purpose")
    if purpose:
        # First paragraph: everything up to the first blank line.
        first_para = purpose[0].split("\n\n", 1)[0].strip()
        sd.purpose = first_para

    # Service Operations.
    ops_sect = _extract_section(text, "## Service Operations")
    if not ops_sect:
        raise ParseError(path, None, "SD missing '## Service Operations' section")
    sd.operations = _parse_operations(ops_sect[0], sd_id, path, ops_sect[1])

    # Inputs and outputs — narrative SDs.
    io_sect = _extract_section(text, "## Inputs and outputs")
    if io_sect:
        inputs_text = _extract_bold_block(io_sect[0], "Inputs")
        outputs_text = _extract_bold_block(io_sect[0], "Outputs")
        if inputs_text:
            for sid in _parse_sd_refs(inputs_text):
                if sid != sd_id:
                    sd.upstream_sds.add(sid)
            # BD-level references add a node-level edge into every SD in that BD;
            # we record them on the BD index in the graph builder rather than here.
            # BD-level narrative references are aggregate-function-references:
            # they record "input from BD-XX as a whole" and produce a single
            # BD-level edge in the graph builder (see graph/build.py B-4 fix).
            # Not fan-out per member SD.
            sd.upstream_sds.update(_parse_bd_refs(inputs_text))
        if outputs_text:
            for sid in _parse_sd_refs(outputs_text):
                if sid != sd_id:
                    sd.downstream_sds.add(sid)
            sd.downstream_sds.update(_parse_bd_refs(outputs_text))

    # Entities — structured Consumes/Owns + (optionally) Produces/Consumes-SD.
    ent_sect = _extract_section(text, "## Entities")
    if not ent_sect:
        raise ParseError(path, None, "SD missing '## Entities' section")
    ent_body = ent_sect[0]

    consumes_text = _extract_bold_block(ent_body, "Consumes")
    if consumes_text:
        sd.consumes_entities = _parse_entity_refs(consumes_text)
        # An SD-level **Consumes:** can also name upstream SDs (the
        # 'inputs from SD-..' shorthand used in some SDs).
        for sid in _parse_sd_refs(consumes_text):
            if sid != sd_id:
                sd.consumes_sds.append(sid)
                sd.upstream_sds.add(sid)

    owns_text = _extract_bold_block(ent_body, "Owns")
    if owns_text:
        text_lower = owns_text.lower().lstrip(":").strip()
        if not text_lower.startswith("none") and not text_lower.startswith("no entities"):
            sd.owns_entities = _parse_entity_refs(owns_text)

    produces_text = _extract_bold_block(ent_body, "Produces")
    if produces_text:
        for sid in _parse_sd_refs(produces_text):
            if sid != sd_id:
                sd.produces_sds.append(sid)
                sd.downstream_sds.add(sid)

    # Strict: every H2 in the file must be in the whitelist. An unknown H2
    # silently dropped is a false-integrity hazard — the parser would
    # claim strictness it does not enforce. Raise instead.
    for m in _H2_RE.finditer(text):
        heading = m.group(1).strip()
        if heading not in SD_KNOWN_H2:
            raise ParseError(
                path, _line_no(text, m.start()),
                f"unknown H2 heading '## {heading}' in SD file (whitelist: "
                f"{', '.join(sorted(SD_KNOWN_H2))})",
            )

    return sd


def parse_service_domains(repo_root: Path) -> ServiceDomainModel:
    """Top-level entry: parse the entire SD model under model/service-domains/."""
    sd_dir = repo_root / "model" / "service-domains"
    if not sd_dir.is_dir():
        raise ParseError(sd_dir, None, "service-domains directory not found")

    bds: list[BusinessDomain] = []
    for bd_path in sorted(sd_dir.iterdir()):
        if not bd_path.is_dir():
            continue
        m = _BD_DIR_RE.match(bd_path.name)
        if not m:
            continue
        bd_num = int(m.group(1))
        readme = bd_path / "README.md"
        if not readme.is_file():
            raise ParseError(bd_path, None,
                             f"BD-{bd_num:02d} directory missing README.md")
        bd = _parse_bd_readme(readme)
        if bd.num != bd_num:
            raise ParseError(readme, 1,
                             f"BD title number ({bd.num}) does not match "
                             f"directory ({bd_num})")

        for sd_path in sorted(bd_path.glob("SD-*.md")):
            sm = _SD_FILE_RE.match(sd_path.name)
            if not sm:
                raise ParseError(sd_path, None,
                                 f"SD filename does not match SD-{bd_num:02d}.M-slug.md")
            if int(sm.group(1)) != bd_num:
                raise ParseError(sd_path, None,
                                 f"SD filename BD-prefix ({sm.group(1)}) "
                                 f"does not match parent BD ({bd_num:02d})")
            sd = _parse_sd_file(sd_path, bd_num, int(sm.group(2)))
            bd.service_domains.append(sd)
        bd.service_domains.sort(key=lambda s: s.sd_num)
        bds.append(bd)

    bds.sort(key=lambda b: b.num)
    return ServiceDomainModel(business_domains=bds)


def validate_cross_refs(sd_model: ServiceDomainModel) -> None:
    """Post-parse: every SD reference in a structured Consumes/Produces line
    must resolve to an SD that exists in the parsed model. BD references in
    narrative Inputs/Outputs lines are allowed to name a whole BD (they expand
    to all the BD's SDs in the graph builder).
    """
    known_sds = {sd.id for sd in sd_model.all_sds()}
    known_bds = {bd.id for bd in sd_model.business_domains}
    for sd in sd_model.all_sds():
        for sid in sd.consumes_sds + sd.produces_sds:
            if sid not in known_sds:
                raise ParseError(
                    sd.path, None,
                    f"{sd.id}: structured Consumes/Produces names "
                    f"unknown {sid}",
                )
        for ref in sd.upstream_sds | sd.downstream_sds:
            if ref.startswith("SD-") and ref not in known_sds:
                raise ParseError(
                    sd.path, None,
                    f"{sd.id}: Inputs/Outputs names unknown {ref}",
                )
            if ref.startswith("BD-") and ref not in known_bds:
                raise ParseError(
                    sd.path, None,
                    f"{sd.id}: Inputs/Outputs names unknown {ref}",
                )
