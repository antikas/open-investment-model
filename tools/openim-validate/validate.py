#!/usr/bin/env python3
"""OpenIM model structural-integrity validator.

Deterministic, mechanical checks over the OpenIM model. No judgement: counts,
identifiers, contiguity, link resolution, section presence, cross-file count
agreement. Fast, exact, re-runnable on every commit. Mechanical checks belong
in a script — an LLM is never asked to count files.

Usage:  python tools/openim-validate/validate.py
Exit:   0 if clean, 1 if any DEFECT is found. WARNINGs do not fail the run.

Distribution awareness: the private build trail (the docs/ directory —
decision records, backlog, build records — plus CLAUDE.md) is present in the
private tree but not in a public distribution of the model. When docs/ is
absent, the checks that read those files are skipped with a single
informational notice; every model-level check still runs.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SD_DIR = REPO / "model" / "service-domains"
ENTITY_DIR = REPO / "model" / "entities"
ADR_DIR = REPO / "docs" / "adr"
INDEX = SD_DIR / "INDEX.md"
OWNERSHIP_MAP = REPO / "model" / "ownership-map.md"

# Single presence flag for the private build trail. The checks that read
# docs/adr/**, docs/BACKLOG.md, docs/cycles/**, or CLAUDE.md consult it and
# are skipped (silently, with one informational line in main()) when the
# trail is not part of the tree.
BUILD_TRAIL_PRESENT = (REPO / "docs").is_dir()

# Files that must state the *current* model totals — never a historical count.
# ADRs and review reports are deliberately excluded: they record counts as-of a
# past decision and must keep them.
LIVE_COUNT_FILES = [
    "README.md",
    "model/README.md",
    "CLAUDE.md",
    "model/service-domains/INDEX.md",
    "model/entities/INDEX.md",
    "model/ownership-map.md",
]

# Files scanned for the BD/SD-pair phrasings only (a focused subset of the prose
# check). These files carry many historical waypoint counts in their narrative
# (e.g. "model total is now **129 Service Domains**") so the broader prose
# regex set would false-positive — but they also carry current-state pair
# phrasings like "current state: N BD / M SD" that must stay live.
#
# Consumed by `check_backlog_prose_counts`; a separate constant per `check_*`
# function keeps each scan's scope explicit.
LIVE_BD_SD_PAIR_FILES = [
    "docs/BACKLOG.md",
]

defects: list[str] = []
warnings: list[str] = []


def defect(msg: str) -> None:
    defects.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


# Required section headers in every Service Domain file.
SD_SECTIONS = ["## Purpose", "## Service Operations", "## Entities", "## Standards"]
# Headers expected but not fatal if a legacy file drifts.
SD_SECTIONS_SOFT = ["## Inputs and outputs", "## Open extensions"]


def bd_dirs() -> list[Path]:
    return sorted(p for p in SD_DIR.iterdir() if p.is_dir() and p.name.startswith("BD-"))


def check_business_domains() -> dict[int, int]:
    """Per-BD: README present, SD files contiguous, return {bd_num: sd_count}."""
    counts: dict[int, int] = {}
    for bd in bd_dirs():
        m = re.match(r"BD-(\d+)-", bd.name)
        if not m:
            defect(f"BD directory name does not match BD-NN-slug: {bd.name}")
            continue
        bd_num = int(m.group(1))
        if not (bd / "README.md").exists():
            defect(f"BD-{bd_num:02d}: missing README.md")
        sd_files = sorted(bd.glob("SD-*.md"))
        nums: list[int] = []
        for sd in sd_files:
            sm = re.match(rf"SD-{bd_num:02d}\.(\d+)-", sd.name)
            if not sm:
                defect(f"SD file name does not match SD-{bd_num:02d}.M-slug: {sd.name}")
                continue
            nums.append(int(sm.group(1)))
            check_sd_file(sd, bd_num, int(sm.group(1)))
        nums.sort()
        if nums:
            expected = list(range(1, len(nums) + 1))
            if nums != expected:
                defect(f"BD-{bd_num:02d}: SD numbering not contiguous 1..{len(nums)} "
                       f"— found {nums}")
        counts[bd_num] = len(nums)
    return counts


def check_sd_file(path: Path, bd_num: int, sd_num: int) -> None:
    text = path.read_text(encoding="utf-8")
    first = text.splitlines()[0] if text.splitlines() else ""
    if not first.startswith(f"# SD-{bd_num:02d}.{sd_num} "):
        defect(f"{path.name}: H1 title does not start '# SD-{bd_num:02d}.{sd_num} '")
    for sec in SD_SECTIONS:
        if sec not in text:
            defect(f"{path.name}: missing required section '{sec}'")
    for sec in SD_SECTIONS_SOFT:
        if sec not in text:
            warn(f"{path.name}: missing expected section '{sec}'")
    if "**Applies:**" not in text:
        defect(f"{path.name}: missing '**Applies:**' tag line")


def parse_index_summary() -> tuple[int, int, dict[int, int]]:
    """Return (declared_bd_count, declared_sd_count, {bd_num: declared_sd_count})."""
    text = INDEX.read_text(encoding="utf-8")
    declared_bd = declared_sd = -1
    m = re.search(r"\*\*(\d+) Business Domains, (\d+) Service Domains\.\*\*", text)
    if m:
        declared_bd, declared_sd = int(m.group(1)), int(m.group(2))
    else:
        defect("INDEX.md: no '**N Business Domains, M Service Domains.**' summary line")
    per_bd: dict[int, int] = {}
    for row in re.finditer(r"^\|\s*BD-(\d+)\s*\|[^|]+\|[^|]+\|\s*(\d+)\s*\|", text, re.M):
        per_bd[int(row.group(1))] = int(row.group(2))
    return declared_bd, declared_sd, per_bd


def check_index(counts: dict[int, int]) -> None:
    declared_bd, declared_sd, per_bd = parse_index_summary()
    actual_bd = len(counts)
    actual_sd = sum(counts.values())
    if declared_bd not in (-1, actual_bd):
        defect(f"INDEX.md summary says {declared_bd} Business Domains; "
               f"{actual_bd} BD directories exist")
    if declared_sd not in (-1, actual_sd):
        defect(f"INDEX.md summary says {declared_sd} Service Domains; "
               f"{actual_sd} SD files exist")
    for bd_num, actual in sorted(counts.items()):
        decl = per_bd.get(bd_num)
        if decl is None:
            defect(f"INDEX.md summary table has no row for BD-{bd_num:02d}")
        elif decl != actual:
            defect(f"INDEX.md summary table: BD-{bd_num:02d} says {decl} SDs; "
                   f"{actual} SD files exist")
    for bd_num in per_bd:
        if bd_num not in counts:
            defect(f"INDEX.md summary table lists BD-{bd_num:02d}; no directory exists")


def check_index_links() -> None:
    text = INDEX.read_text(encoding="utf-8")
    for link in re.finditer(r"\]\((BD-[^)]+\.md)\)", text):
        target = SD_DIR / link.group(1)
        if not target.exists():
            defect(f"INDEX.md: dead link to {link.group(1)}")
    # Every SD file should be linked from INDEX.
    linked = set(re.findall(r"\]\((BD-[^)]+/SD-[^)]+\.md)\)", text))
    for bd in bd_dirs():
        for sd in bd.glob("SD-*.md"):
            rel = f"{bd.name}/{sd.name}"
            if rel not in linked:
                defect(f"INDEX.md: SD file not linked — {rel}")


def check_adrs() -> None:
    if not ADR_DIR.exists():
        defect("docs/adr/ directory missing")
        return
    nums = sorted(int(m.group(1)) for p in ADR_DIR.glob("*.md")
                  if (m := re.match(r"(\d+)-", p.name)))
    if not nums:
        defect("docs/adr/: no ADR files found")
        return
    seen: set[int] = set()
    for n in nums:
        if n in seen:
            defect(f"docs/adr/: duplicate ADR number {n:04d}")
        seen.add(n)
    # A gap is reported as a WARNING — OpenIM has a known intentional gap (no 0003).
    full = set(range(min(nums), max(nums) + 1))
    for missing in sorted(full - set(nums)):
        warn(f"docs/adr/: no ADR-{missing:04d} (gap in the sequence — confirm intentional)")


def check_count_agreement(counts: dict[int, int]) -> None:
    """README.md, model/README.md (and CLAUDE.md, when the private build
    trail is present) must agree on the BD/SD count."""
    actual_bd, actual_sd = len(counts), sum(counts.values())
    files = ["README.md", "model/README.md"]
    if BUILD_TRAIL_PRESENT:
        files.append("CLAUDE.md")
    for rel in files:
        path = REPO / rel
        if not path.exists():
            warn(f"{rel}: not found — count agreement not checked")
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"(\d+) Business Domains?(?:\s+and|,)\s+(\d+) Service Domains?", text):
            bd, sd = int(m.group(1)), int(m.group(2))
            if (bd, sd) != (actual_bd, actual_sd):
                defect(f"{rel}: states '{bd} Business Domains, {sd} Service Domains'; "
                       f"model is {actual_bd} BD / {actual_sd} SD")


def count_entities() -> tuple[int, int]:
    """Return (core_entity_count, specialisation_entity_count) from the files."""
    core = ENTITY_DIR / "core"
    n_core = len(list(core.glob("E-*.md"))) if core.exists() else 0
    n_spec = 0
    spec = ENTITY_DIR / "specialisations"
    if spec.exists():
        for pack in spec.iterdir():
            if pack.is_dir():
                n_spec += len([p for p in pack.glob("*.md")
                               if re.match(r"(PM|PB|DR|RA|FO)-\d+-", p.name)])
    return n_core, n_spec


# BD/SD-pair phrasings — one regex per phrasing, each capturing both the BD
# and the SD count for a paired check. Declared once, shared by every
# consumer, so future drift in similar paired phrasings does not require
# another validator extension — add the new phrasing here and every consumer
# helper picks it up. Each pattern captures group(1)=BD, group(2)=SD.
BD_SD_PAIR_PATTERNS: list[tuple[str, str]] = [
    # Header-sentence form: "model total: 17 Business Domains, 166 Service Domains."
    (
        r"model total[^\d]{0,30}?(\d+)\s+Business\s+Domains?,?\s+(\d+)\s+Service\s+Domains?",
        "model-total header",
    ),
    # Reconciliation / status-snapshot / final-model form: "current 17 BD / 166 SD",
    # "current state: 17 BD / 166 SD", "Final model: 17 BD / 166 SD". All
    # three are "the current / final landscape state" assertions and must
    # reconcile against the model.
    (
        r"(?:current(?:\s+state)?[:\s]+|the current\s+|[Ff]inal model[:\s]+\**)(\d+)\s+BD\s*/\s*(\d+)\s+SD",
        "current/final N BD / M SD",
    ),
    # Directory-tree / inline form: "17 Business Domain / 166 Service Domain
    # decomposition" (note the singular forms in README.md's directory-tree
    # code block).
    (
        r"(\d+)\s+Business\s+Domains?\s*/\s*(\d+)\s+Service\s+Domains?\s+decomposition",
        "N Business Domain / M Service Domain decomposition",
    ),
    # "N Business Domains and M Service Domains" (the ownership-map's
    # landscape phrasing). Distinct from the "model total" header (which
    # carries the "model total" anchor) — this one is the bare-prose
    # landscape statement.
    (
        r"(\d+)\s+Business\s+Domains?\s+and\s+(\d+)\s+Service\s+Domains?",
        "N Business Domains and M Service Domains",
    ),
]


def scan_bd_sd_pairs(
    text: str,
    rel: str,
    actual_bd: int,
    actual_sd: int,
    *,
    skip_table_lines: bool = False,
) -> None:
    """Run the BD/SD-pair regex set against `text` and defect on mismatch.

    Shared helper used by `check_prose_counts`, `check_adr_index_prose_counts`,
    and `check_backlog_prose_counts`. Every consumer picks up the same regex
    set; adding a new paired phrasing means one entry in
    `BD_SD_PAIR_PATTERNS` rather than three.
    """
    if skip_table_lines:
        text = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("|")
        )
    for pattern, label in BD_SD_PAIR_PATTERNS:
        for m in re.finditer(pattern, text):
            found_bd, found_sd = int(m.group(1)), int(m.group(2))
            if (found_bd, found_sd) != (actual_bd, actual_sd):
                defect(f"{rel}: prose says {found_bd} BD / "
                       f"{found_sd} SD ({label}); current model value is "
                       f"{actual_bd} BD / {actual_sd} SD")


def check_prose_counts(counts: dict[int, int]) -> None:
    """Catch stale counts embedded in prose in the files that must stay current.

    The no-SSOT-reconciliation pattern: prose counts drift behind the model
    because nothing re-reads them after the model grows. This scans only
    LIVE_COUNT_FILES — decision records and reviews keep historical counts by
    design and are not scanned.
    """
    actual_bd, actual_sd = len(counts), sum(counts.values())
    n_core, n_spec = count_entities()
    n_total = n_core + n_spec
    # Single-value checks: each captures one number; the expected value is
    # the actual current count.
    checks = [
        (r"all (\d+) Business Domains", actual_bd, "all-N-Business-Domains"),
        (r"all (\d+) Service Domains", actual_sd, "all-N-Service-Domains"),
        (r"model total\D{0,30}?(\d+)", actual_sd, "model-total Service Domains"),
        (r"(\d+) specialisation entit", n_spec, "specialisation-entity count"),
        (r"(\d+) with the core", n_total, "entity-model total"),
        (r"entity model is \*\*(\d+) entities", n_total, "entity-model total"),
    ]
    for rel in LIVE_COUNT_FILES:
        path = REPO / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern, expected, label in checks:
            for m in re.finditer(pattern, text):
                found = int(m.group(1))
                if found != expected:
                    defect(f"{rel}: prose says {found} ({label}); "
                           f"current model value is {expected}")
        # Paired BD/SD phrasings — apply via the shared helper.
        scan_bd_sd_pairs(text, rel, actual_bd, actual_sd)


def check_adr_index_prose_counts(counts: dict[int, int]) -> None:
    """Scan the ADR INDEX for stale prose counts.

    `docs/adr/INDEX.md` is deliberately excluded from `LIVE_COUNT_FILES` because
    the per-row table's "Model after" column records historical counts (one per
    ADR, by design). But the file *also* carries current-model prose — a header
    sentence stating the current total, plus a reconciliation paragraph that
    walks the ADR chain and ends at the current total. Both must stay live;
    a header updated while the prose body two lines below is not walked is
    exactly the drift class this catches.

    Skips lines starting with `|` (the per-row table) and delegates the
    paired-phrasing scan to the shared `scan_bd_sd_pairs` helper (the
    BD/SD-pair regex set is declared once in `BD_SD_PAIR_PATTERNS`).
    """
    path = REPO / "docs" / "adr" / "INDEX.md"
    if not path.exists():
        return
    actual_bd, actual_sd = len(counts), sum(counts.values())
    text = path.read_text(encoding="utf-8")
    scan_bd_sd_pairs(
        text, "docs/adr/INDEX.md", actual_bd, actual_sd, skip_table_lines=True,
    )


def check_backlog_prose_counts(counts: dict[int, int]) -> None:
    """Scan `LIVE_BD_SD_PAIR_FILES` for stale BD/SD-pair counts.

    These files are deliberately *not* in `LIVE_COUNT_FILES` because their
    narrative carries dozens of historical waypoint counts ("model total is
    now **129 Service Domains**") that the standard prose-count regex set
    would false-positive on. But they *also* carry current-state pair
    phrasings — status-snapshot headers like "current state: 17 BD / N SD"
    and closing lines like "Final model: 17 BD / N SD" — that must stay
    live against the model.

    Scans every line of each file with the shared BD/SD-pair regex set
    (`BD_SD_PAIR_PATTERNS`) — no table-line skip needed (the BACKLOG has no
    per-row BD table). Historical waypoint phrasings ("129 Service Domains")
    use the bare-N forms not matched by the pair patterns, so they pass
    through.

    Adding a future paired-phrasing file means appending to
    `LIVE_BD_SD_PAIR_FILES`; the function picks it up automatically.
    """
    actual_bd, actual_sd = len(counts), sum(counts.values())
    for rel in LIVE_BD_SD_PAIR_FILES:
        path = REPO / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        scan_bd_sd_pairs(text, rel, actual_bd, actual_sd)


def check_per_bd_sd_annotations(counts: dict[int, int]) -> None:
    """Scan LIVE_COUNT_FILES for stale per-BD `(N SDs)` prose.

    `BD_SD_PAIR_PATTERNS` checks model *totals*, not per-BD counts; this
    check closes the per-BD gap — a prose annotation like "BD-17 (8 SDs)"
    written before a Business Domain grew would otherwise drift silently.

    The pattern `BD-NN <something> (N SDs)` appears in design-note prose
    summarising BD splits / archetype tables / per-BD breakdowns. The regex is
    bounded by `[^()\\n]{1,200}?` to anchor each match within a single sentence
    and avoid crossing parenthesis boundaries (the design-note prose often
    chains multiple per-BD annotations separated by `;`).

    Scans only LIVE_COUNT_FILES — historical waypoint annotations in
    `docs/BACKLOG.md` ("BD-NN ... (N SDs)" entries recording each BD at the
    time of its expansion) are by-design point-in-time records and would
    false-positive.
    """
    pattern = re.compile(r"BD-(\d+)[^()\n]{1,200}?\((\d+)\s+SDs?\b")
    for rel in LIVE_COUNT_FILES:
        path = REPO / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            bd_num = int(m.group(1))
            claimed = int(m.group(2))
            actual = counts.get(bd_num)
            if actual is None:
                defect(f"{rel}: prose annotation 'BD-{bd_num:02d} (... {claimed} SDs)' "
                       f"references a BD that has no directory")
            elif actual != claimed:
                defect(f"{rel}: prose annotation 'BD-{bd_num:02d} (... {claimed} SDs)'; "
                       f"BD-{bd_num:02d} has {actual} SD files")


def check_per_row_bd_tables(counts: dict[int, int]) -> None:
    """Validate any `| BD-NN | name | office | N |` table in the
    LIVE_COUNT_FILES has the right rows and the right per-row counts.

    A per-row table can fall out of step with the model — stale per-row
    counts, or a Business Domain missing a row — while sitting two lines
    below a (validator-checked) canonical sentence. The prose-count check
    catches the headline; this check catches the table.
    """
    for rel in LIVE_COUNT_FILES:
        path = REPO / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # Match rows of shape `| BD-NN | ... | ... | N |`. The third column
        # in INDEX.md is the office tag; in README.md it's also office; in
        # CLAUDE.md and the other files there is no such table — the regex
        # only matches where the table exists.
        seen_bd: dict[int, int] = {}
        for m in re.finditer(
            r"^\|\s*BD-(\d+)\s*\|[^|]+\|[^|]+\|\s*(\d+)\s*\|",
            text,
            re.M,
        ):
            bd_num = int(m.group(1))
            sd_count = int(m.group(2))
            seen_bd[bd_num] = sd_count
        if not seen_bd:
            continue  # No per-row BD table in this file.
        # Any BD listed must exist and carry the right count.
        for bd_num, listed_count in sorted(seen_bd.items()):
            actual = counts.get(bd_num)
            if actual is None:
                defect(f"{rel}: per-row table lists BD-{bd_num:02d}; "
                       f"no BD directory exists")
            elif actual != listed_count:
                defect(f"{rel}: per-row table says BD-{bd_num:02d} has "
                       f"{listed_count} Service Domains; {actual} SD files exist")
        # Any actual BD missing from the table is a defect — a table that
        # silently drops a Business Domain understates the model.
        for bd_num in sorted(counts):
            if bd_num not in seen_bd:
                defect(f"{rel}: per-row table missing row for BD-{bd_num:02d}")


def check_ownership_map() -> None:
    """Entity-side leg of the three-way ownership pattern.

    Every entity file declares an owner, and the ownership map exists. The map
    (`model/ownership-map.md`) is the SSOT for entity ownership. Each entity
    file's `Owned by:` line names the authoritative Service Domain (or, for
    the documented multi-owner patterns, names the pattern). The SD-side leg
    is `check_ownership_map_producing_side`; together the two checks enforce
    the map's ownership contract.
    """
    if not OWNERSHIP_MAP.exists():
        defect("model/ownership-map.md: missing (the SSOT for entity ownership)")
        return
    for d in (ENTITY_DIR / "core", *((ENTITY_DIR / "specialisations").iterdir() if (ENTITY_DIR / "specialisations").exists() else ())):
        if not d.is_dir():
            continue
        for p in d.glob("*.md"):
            if p.name in {"README.md", "INDEX.md"}:
                continue
            if not re.match(r"(E|PM|PB|DR|RA|FO)-\d+-", p.name):
                continue
            text = p.read_text(encoding="utf-8")
            if "**Owned by:**" not in text:
                defect(f"{p.relative_to(REPO)}: missing '**Owned by:**' declaration")


def parse_ownership_map() -> dict[str, list[tuple[str, str]]]:
    """Parse `model/ownership-map.md`'s entity tables into {entity_id: [(sd_id, annotation), ...]}.

    The map's tables carry one row per entity, with the owning Service Domain(s)
    in column 2. Each row matched is `| <entity_id> <name> | <owner-cell> | <pattern> |`.
    The owner-cell may carry one SD (single owner) or multiple SDs separated by
    `+` / `or` (key-partitioned or faceted), each with an optional annotation
    (the partition key value or facet name).
    """
    text = OWNERSHIP_MAP.read_text(encoding="utf-8")
    rows: dict[str, list[tuple[str, str]]] = {}
    # Match table rows of shape:
    #   | **E-NN** ... | <owner-cell> | <pattern> |
    #   | E-NN ...     | <owner-cell> | <pattern> |
    # The first column starts with the entity ID; the cell may be bolded.
    pattern_row = re.compile(
        r"^\|\s*\**((?:E|PM|PB|DR|RA|FO)-\d+)[^|]*\|([^|]+)\|([^|]+)\|",
        re.M,
    )
    for m in pattern_row.finditer(text):
        entity_id = m.group(1)
        owner_cell = m.group(2)
        # Find every SD-NN.M reference in the owner cell.
        sd_refs = re.findall(r"SD-(\d{2})\.(\d+)", owner_cell)
        owners: list[tuple[str, str]] = []
        for bd, sd in sd_refs:
            sd_id = f"SD-{bd}.{sd}"
            owners.append((sd_id, owner_cell.strip()))
        if owners:
            rows.setdefault(entity_id, []).extend(owners)
    return rows


def check_ownership_map_producing_side() -> None:
    """SD-side leg of the three-way ownership pattern.

    For each (entity, owner_sd) pair declared in `model/ownership-map.md`, the
    owning Service Domain file's `**Owns:**` line must name the entity (by its
    ID — e.g. 'E-19' or 'E-03'). A line that omits the entity ID, or that says
    'none' / 'none directly' while the map names the SD as owner, is a defect.

    An SD `**Owns:**` line stale against the map is exactly the drift class
    this check detects.
    """
    if not OWNERSHIP_MAP.exists():
        return  # `check_ownership_map` already defects on the missing map.
    rows = parse_ownership_map()
    if not rows:
        defect("model/ownership-map.md: no entity rows parsed — table format change?")
        return
    # Build a {sd_id: path} index for owner-SD files.
    sd_paths: dict[str, Path] = {}
    for bd in bd_dirs():
        for sd in bd.glob("SD-*.md"):
            m = re.match(r"(SD-\d{2}\.\d+)", sd.name)
            if m:
                sd_paths[m.group(1)] = sd
    for entity_id, owners in rows.items():
        for sd_id, _annotation in owners:
            path = sd_paths.get(sd_id)
            if path is None:
                defect(f"ownership-map: {entity_id} owner {sd_id} — no SD file found")
                continue
            text = path.read_text(encoding="utf-8")
            # Extract the **Owns:** block — it can run to the end of its line
            # and onto subsequent lines until a blank line or new bullet.
            m_owns = re.search(r"\*\*Owns:\*\*([^\n]*(?:\n(?!\s*-\s|\s*\*\*|\s*$)[^\n]*)*)", text)
            if not m_owns:
                defect(f"{path.relative_to(REPO)}: missing '**Owns:**' line "
                       f"(map names this SD as owner of {entity_id})")
                continue
            owns_block = m_owns.group(1)
            # The Owns line must name the entity ID. A negative declaration
            # ('none' / 'none directly') is a defect — the map says this SD
            # owns the entity (or its partition / facet).
            # A negative declaration ('none' / 'none directly') is a defect
            # regardless of whether the entity ID appears elsewhere in the
            # block — the map declares this SD an owner, so the line cannot
            # claim non-ownership. ("recorded as E-19" reads as "the data
            # ends up at E-19 but I don't own it" — exactly the drift
            # pattern this catches.)
            first_line = owns_block.split("\n", 1)[0].strip().lower()
            if first_line.startswith("none"):
                defect(f"{path.relative_to(REPO)}: '**Owns:**' starts 'none' but "
                       f"ownership-map names {sd_id} as owner of {entity_id}")
            elif entity_id not in owns_block:
                defect(f"{path.relative_to(REPO)}: '**Owns:**' line does not "
                       f"name {entity_id} (ownership-map declares {sd_id} an "
                       f"owner)")


# The seven key-partitioned entities declared in `model/ownership-map.md` —
# each one with its partition vocabulary. Producer-side `**Owns:**` lines name
# the specific partition (e.g. `book = ibor`, `risk_type = market`, "fund-side
# rows of E-13"); consumer-side `**Consumes:**` lines must do the same so the
# tool-surface SSOT (the `**Consumes:**` line) carries the partition contract
# the implementation depends on. The map's own rule is the source: "Consumers
# must declare which book."
PARTITIONED_ENTITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    # E-04 Holding / Position — partitioned by `book` (SD-12.1 IBOR vs SD-12.2 ABOR).
    "E-04": ("book", "ibor", "abor"),
    # E-07 Valuation — partitioned by `method`, using the attribute-schema enum
    # (observable_price / mark_to_model / manager_mark / appraisal / amortised_cost).
    "E-07": ("method", "observable_price", "mark_to_model", "manager_mark", "appraisal", "amortised_cost"),
    # E-13 Entity Alias — partitioned by master kind (instrument-side / entity-side / fund-side).
    "E-13": ("partition", "instrument-side", "entity-side", "fund-side"),
    # E-14 External Identifier — partitioned by master kind.
    "E-14": ("partition", "instrument-side", "entity-side", "fund-side"),
    # E-19 Risk Measurement — partitioned by `risk_type` (market / credit / counterparty / liquidity / concentration / scenario / stress / climate).
    "E-19": ("risk_type",),
    # E-25 Account — partitioned by `account_type` (SD-12.5 safekeeping / SD-11.7 cash / SD-15.4 register).
    "E-25": ("account_type", "safekeeping", "cash", "register"),
    # E-29 Allocation Plan — partitioned by `plan_type` (SD-01.4 strategic, SD-01.6 reference_portfolio, SD-01.10 commitment_pacing).
    "E-29": ("plan_type", "strategic", "reference_portfolio", "commitment_pacing"),
}


def check_consuming_side_partitions() -> None:
    """Consumer-side leg of the key-partitioned ownership pattern.

    For each `**Consumes:**` line in a Service Domain file (or in a Business
    Domain README) that names one of the seven key-partitioned entities (E-04,
    E-07, E-13, E-14, E-19, E-25, E-29), the line must declare which partition
    is consumed.
    The accepted forms — matching the producer-side vocabulary used in the
    corresponding `**Owns:**` lines — are:

      - The literal "any X" (e.g. "any `book`", "any `method`", "any partition",
        "any `risk_type`"), which is the all-partitions declaration.
      - A specific partition value (e.g. "`book = ibor`", "`method = quoted`",
        "`risk_type = market`", "instrument-side partition", "fund-side rows").

    Silence is the defect class — a `**Consumes:**` line that names a
    partitioned entity but says nothing about which partition leaves the
    partition contract undeclared. Per the ownership-map's own rule
    ("Consumers must declare which book"), the rule is mechanically
    verifiable here: the consumer line must carry one of the partition
    keywords inside a small window after the entity ID.
    """
    if not OWNERSHIP_MAP.exists():
        return  # `check_ownership_map` already defects on the missing map.

    # Build the file list — every SD file and every BD README.
    files: list[Path] = []
    for bd in bd_dirs():
        readme = bd / "README.md"
        if readme.exists():
            files.append(readme)
        files.extend(sorted(bd.glob("SD-*.md")))

    # Pattern for a `**Consumes:**` block — captures the line content up to a
    # blank line or the next bullet point.
    consumes_block_re = re.compile(
        r"\*\*Consumes:?\*\*([^\n]*(?:\n(?!\s*-\s|\s*\*\*|\s*$)[^\n]*)*)",
    )

    for path in files:
        text = path.read_text(encoding="utf-8")
        for m_block in consumes_block_re.finditer(text):
            block = m_block.group(1)
            # For each partitioned entity, check if it is named in the block.
            for entity_id, keywords in PARTITIONED_ENTITY_KEYWORDS.items():
                # Find every occurrence of the entity ID as a word.
                for m_id in re.finditer(rf"\b{re.escape(entity_id)}\b", block):
                    # Take a 240-character window after the entity ID — enough
                    # to cover the entity's qualifying clause without spilling
                    # into the next entity in a long list.
                    window = block[m_id.end():m_id.end() + 240]
                    # Stop the window at the next entity ID in the line, so a
                    # later E-NN's partition doesn't satisfy this E-NN's check.
                    next_entity = re.search(r"\b(E|PM|PB|DR|RA|FO)-\d+\b", window)
                    if next_entity:
                        window = window[:next_entity.start()]
                    if not any(kw in window for kw in keywords):
                        # Also accept "any partition" / "any book" / "any method"
                        # / "any risk_type" — these appear in the keyword tuple
                        # already (`book`, `method`, `partition`, `risk_type`),
                        # so silence is what we are catching here.
                        defect(
                            f"{path.relative_to(REPO)}: '**Consumes:**' line "
                            f"names {entity_id} without declaring a partition "
                            f"(key-partitioned ownership; consumer-side rule "
                            f"in model/ownership-map.md). Expected one "
                            f"of: {', '.join(keywords)} (or 'any …')."
                        )


def check_sd_name_resolution() -> None:
    """SD references must name the SD by its canonical H1.

    Walks every entity file (`model/entities/core/*.md` and
    `model/entities/specialisations/*/*.md`, excluding READMEs / INDEXes)
    and every Service Domain file (`model/service-domains/*/SD-*.md`).
    For each reference of the form `SD-NN.M <Name>` in the prose,
    parses out the cited name (the capitalised tokens that follow the SD
    ID, up to the next punctuation / link / lowercase clause / another SD
    ID), looks up the actual SD file at
    `model/service-domains/BD-NN-*/SD-NN.M-*.md`, reads its H1, and
    verifies the cited name is a substring (case-insensitive) of the H1.

    The defect class: prose citing an SD by an invented name (a name the
    writer expected, not the name the SD file carries) reads plausibly and
    survives review — this check catches it mechanically at commit time.
    """
    # Build the SD H1 index — one entry per SD file under model/service-domains/.
    sd_h1: dict[str, str] = {}
    for bd in bd_dirs():
        for sd in bd.glob("SD-*.md"):
            m = re.match(r"(SD-\d{2}\.\d+)", sd.name)
            if not m:
                continue
            text = sd.read_text(encoding="utf-8")
            first = text.splitlines()[0] if text.splitlines() else ""
            # H1 form: `# SD-NN.M — Name`. Strip the SD ID prefix and the
            # em-dash separator, keep just the Name portion.
            h1_match = re.match(r"^#\s*SD-\d{2}\.\d+\s*[—\-]\s*(.+?)\s*$", first)
            if h1_match:
                sd_h1[m.group(1)] = h1_match.group(1).strip()

    # Build the file list — every entity file (core + specialisations) plus
    # every SD file. READMEs and INDEX files are excluded; they carry
    # navigation prose, not the canonical references we want to check.
    files: list[Path] = []
    core = ENTITY_DIR / "core"
    if core.exists():
        files.extend(sorted(
            p for p in core.glob("*.md")
            if p.name not in {"README.md", "INDEX.md"}
            and re.match(r"E-\d+-", p.name)
        ))
    spec = ENTITY_DIR / "specialisations"
    if spec.exists():
        for pack in sorted(spec.iterdir()):
            if not pack.is_dir():
                continue
            files.extend(sorted(
                p for p in pack.glob("*.md")
                if p.name not in {"README.md", "INDEX.md"}
                and re.match(r"(PM|PB|DR|RA|FO)-\d+-", p.name)
            ))
    for bd in bd_dirs():
        files.extend(sorted(bd.glob("SD-*.md")))

    # SD-reference pattern: SD-NN.M, followed by whitespace, followed by a
    # multi-token capitalised name (the cited canonical name). The regex
    # is deliberately strict: a cited "name" must be at least **two**
    # capitalised tokens (or a capitalised token + `&` + capitalised
    # token). Single all-caps abbreviations following the SD ID
    # (e.g. `the SD-08.4 IPV policy`, `the SD-15.8 RFP function`,
    # `the SD-13.9 ESG data`) are prose using the SD as an adjective,
    # not citing the SD by name — and would false-positive against H1s
    # that are unrelated.
    #
    # The capture stops at punctuation that ends a name clause
    # (period, comma, semicolon, colon, paren, bracket, em-dash,
    # newline, pipe, asterisk, slash) or at the next SD/BD/E reference.
    # Connectives `&`, `of`, `the`, `and`, `for`, `in`, `on`, `to`, `at`
    # may sit inside a name (the H1 vocabulary uses `&`); the trailing
    # connective is trimmed off after capture.
    sd_ref_re = re.compile(
        # Negative lookbehind: skip SD IDs that are the trailing member of
        # a slash-separated list (`SD-07.1 / SD-07.2 / SD-07.3 / SD-07.4 Name`).
        # In that pattern the cited "Name" is a collective for the list,
        # typically the Business Domain name, not the trailing SD's own name.
        # Two-char lookbehind covers the `/ SD-NN.M` shape (slash + space).
        r"(?<!/ )(?<!/)"
        r"\bSD-(\d{2}\.\d+)\s+"
        # First name token: capital-led word with letters, digits,
        # apostrophes; hyphens are excluded so "GIPS-compliant" /
        # "LP-commitment" prose adjectives are not captured as names.
        # Negative lookahead `(?!SD-)` prevents the capture from
        # absorbing a following SD-NN.M reference.
        r"((?!SD-)[A-Z][A-Za-z0-9']*"
        # At least one continuation: either ` & Word`, ` of/and/the/... Word`,
        # or just ` Word`. The `&` form covers the common buy-side name
        # pattern (`X & Y`). Connectives are absorbed only when followed
        # by another capitalised token. The negative lookahead on each
        # continuation prevents pulling in `and SD-NN.M`-style tails.
        r"(?:\s+(?:&|of|the|and|for|in|on|to|at)\s+(?!SD-)[A-Z][A-Za-z0-9']*"
        r"|\s+(?!SD-)[A-Z][A-Za-z0-9']*)+)"
    )

    # The check runs on prose only — skip code fences. Tables (which we do
    # want to check) are kept.
    fence_re = re.compile(r"```.*?```", re.DOTALL)

    for path in files:
        text = path.read_text(encoding="utf-8")
        # Strip fenced code blocks before scanning.
        prose = fence_re.sub("", text)
        for m in sd_ref_re.finditer(prose):
            sd_id = f"SD-{m.group(1)}"
            cited = m.group(2).strip()
            # Trim trailing connective tokens that the greedy capture
            # would have pulled in (e.g. `the`, `and`, `of`) before any
            # following punctuation. These are not part of the canonical
            # SD name.
            cited = re.sub(r"\s+(?:of|the|and|for|in|on|to|at)$", "", cited).strip()
            # If the cited "name" is just a single short connective word
            # (e.g. captured at end of sentence), skip — no real name.
            if len(cited) < 3 or cited.lower() in {"the", "and", "for", "of"}:
                continue
            # The cited "name" can include trailing words that are part of
            # the sentence rather than the SD's actual name (the regex is
            # deliberately permissive). The substring check is one-way:
            # the cited name need only be a substring of the H1, not the
            # other way around. If the H1 is `Investment Analytics & Insight`
            # and the cited "name" is `Investment Analytics`, that is a
            # PASS — the cited portion is a faithful prefix.
            #
            # The defect case is the cited "name" containing words not in
            # the H1 at all (e.g. `ESG & Sustainability Compliance` against
            # H1 `Side-Letter & Fund-Term Compliance`).
            actual_h1 = sd_h1.get(sd_id)
            if actual_h1 is None:
                defect(f"{path.relative_to(REPO)}: reference to {sd_id} "
                       f"({cited!r}) — no SD file found at "
                       f"model/service-domains/BD-*/SD-{m.group(1)}-*.md")
                continue
            # Try progressively shorter prefixes of the cited name, from
            # the full capture down to the first two-or-more capitalised
            # words, looking for a substring match against the H1. This
            # tolerates the greedy capture pulling in trailing sentence
            # words (e.g. `SD-09.5 Investment Analytics & Insight feeds
            # …` — the capture is `Investment Analytics & Insight feeds`;
            # `Investment Analytics & Insight` is the prefix that matches).
            tokens = cited.split()
            matched = False
            for end in range(len(tokens), 1, -1):
                candidate = " ".join(tokens[:end])
                if candidate.lower() in actual_h1.lower():
                    matched = True
                    break
            if not matched:
                defect(f"{path.relative_to(REPO)}: reference to {sd_id} "
                       f"cites name {cited!r}; actual {sd_id} H1 is "
                       f"{actual_h1!r} (cited name is not a substring "
                       f"of the canonical H1)")


def check_adr_status_progression() -> None:
    """Two-layer status gate (ADR-0023 mechanical + ADR-0029 separation-of-duties).

    The ADR status vocabulary under ADR-0029:
      Proposed → Accepted → Accepted (audited)

    Legacy vocabulary `Accepted (remediated)` is preserved on historical ADRs
    (0018-0028) and continues to require a fully-ticked `## Remediation walk`
    section (ADR-0023's mechanical check).

    The new vocabulary `Accepted (audited)` is the close-gate under ADR-0029.
    Its check: the ADR must (a) carry a `## Remediation walk` section as the
    remediation agent's audit-input summary (informational, but required as
    documentation), and (b) carry an explicit audit-record reference — either
    a body sentence naming the synthesis Remediation log entry that
    records the audit-agent's clean return, or a dedicated `## Audit record`
    section. An ADR carrying `(audited)` without the audit reference is a
    DEFECT — the close-gate proof is the audit agent's clean return, and the
    ADR must point at it.

    Status `Accepted` (without either qualifier) does not trigger the check —
    the gate is the transition into a closure-state qualifier.
    """
    if not ADR_DIR.exists():
        return  # `check_adrs` already defects on a missing directory.
    for p in sorted(ADR_DIR.glob("*.md")):
        if p.name in {"INDEX.md", "TEMPLATE.md"}:
            continue
        if not re.match(r"\d{4}-", p.name):
            continue
        text = p.read_text(encoding="utf-8")
        m_status = re.search(r"\*\*Status:\*\*\s*([^\n]+)", text)
        if not m_status:
            warn(f"{p.relative_to(REPO)}: no '**Status:**' line")
            continue
        status = m_status.group(1).strip()

        # ADR-0023 legacy gate — `Accepted (remediated)` requires walked checklist.
        if "Accepted (remediated)" in status:
            if "## Remediation walk" not in text:
                defect(f"{p.relative_to(REPO)}: status '{status}' but no "
                       f"'## Remediation walk' section (ADR-0023 §5)")
                continue
            m_walk = re.search(
                r"## Remediation walk\s*\n(.*?)(?=\n##\s|\Z)",
                text,
                re.DOTALL,
            )
            if not m_walk:
                defect(f"{p.relative_to(REPO)}: '## Remediation walk' section parse failed")
                continue
            walk_block = m_walk.group(1)
            for cb_match in re.finditer(r"^\s*-\s*\[( |x|X)\]\s*(.*)$", walk_block, re.M):
                tick = cb_match.group(1)
                line_text = cb_match.group(2)
                if tick == " " and "not applicable" not in line_text.lower():
                    defect(f"{p.relative_to(REPO)}: unticked checkbox in "
                           f"'## Remediation walk' — '{line_text[:60]}…' "
                           f"(ADR-0023 §2: '(remediated)' gates on every line)")
            continue

        # ADR-0029 new gate — `Accepted (audited)` requires audit-record reference.
        if "Accepted (audited)" in status:
            # The remediation walk is still useful as the audit-input summary,
            # so check it is present (informational documentation under ADR-0029).
            if "## Remediation walk" not in text:
                defect(f"{p.relative_to(REPO)}: status '{status}' but no "
                       f"'## Remediation walk' section (ADR-0029: walk is "
                       f"the audit-input summary even when not the close gate)")
                continue
            # The close gate is the audit-agent's clean return. The ADR must
            # reference it. Accept either an `## Audit record` section, or a
            # body sentence naming the audit verdict / synthesis log entry.
            has_audit_section = "## Audit record" in text
            has_audit_reference = bool(
                re.search(r"audit\s+(agent|verdict|record|return)", text, re.I)
            )
            if not (has_audit_section or has_audit_reference):
                defect(f"{p.relative_to(REPO)}: status '{status}' but no audit "
                       f"record reference (ADR-0029 §4: the close gate is the "
                       f"audit-agent's clean return; the ADR must reference it)")
            continue

        # Status `Accepted` without a closure qualifier — no gate check.


def check_dispatch_scope_completeness() -> None:
    """ADR-0038 — Scope-declaration discipline.

    Any ADR that asserts class-uniform completeness over a model surface
    must carry a `**Scope of completeness claim:**` block. When present,
    the block must enumerate at least one surface, each line prefixed with
    one of three sweep statuses — `swept` / `re-checked` / `excepted` —
    and an `excepted` status must carry a reason.

    The mechanical check only enforces the format of the block when present;
    the judgement on whether the ADR *should* carry the block (because it
    makes a class-completeness claim) is the audit-agent's job under the
    ADR-0038 class-walk licence.
    """
    if not ADR_DIR.exists():
        return
    pattern = re.compile(
        r"(?:^|\n)(?:##\s+|\*\*)Scope of completeness claim(?:\*\*|\s*\n)(.*?)"
        r"(?=\n##\s|\n---|\Z)",
        re.DOTALL,
    )
    line_re = re.compile(r"^\s*[-*]\s*(?:\*\*)?(swept|re-checked|excepted)(?:\*\*)?\b(.*)$", re.I)
    for p in sorted(ADR_DIR.glob("*.md")):
        if p.name in {"INDEX.md", "TEMPLATE.md"}:
            continue
        if not re.match(r"\d{4}-", p.name):
            continue
        text = p.read_text(encoding="utf-8")
        m = pattern.search(text)
        if not m:
            continue  # no claim section — nothing to check mechanically
        block = m.group(1).strip()
        # An ADR that uses the section as a self-describing process note (not
        # a per-surface enumeration) is acceptable as long as it states so
        # explicitly. The check looks for at least one sweep-status line OR
        # an explicit "does not claim class-completeness" disclaimer.
        if "does not claim" in block.lower() or "not a model-surface" in block.lower():
            continue
        bullets = [ln for ln in block.splitlines() if re.match(r"^\s*[-*]\s+", ln)]
        if not bullets:
            defect(f"{p.relative_to(REPO)}: '**Scope of completeness claim:**' "
                   f"section has no enumerated surfaces (ADR-0038: every claim "
                   f"must list surfaces with sweep-status prefixes)")
            continue
        for bullet in bullets:
            lm = line_re.match(bullet)
            if not lm:
                defect(f"{p.relative_to(REPO)}: scope-of-completeness-claim "
                       f"bullet does not start with a sweep-status prefix "
                       f"(swept / re-checked / excepted) — '{bullet.strip()[:80]}…' "
                       f"(ADR-0038 §2)")
                continue
            status, rest = lm.group(1).lower(), lm.group(2)
            if status == "excepted" and not re.search(r"\b(reason|because|deferred|out[- ]of[- ]scope)\b", rest, re.I):
                defect(f"{p.relative_to(REPO)}: scope-of-completeness-claim "
                       f"'excepted' line carries no reason — '{bullet.strip()[:80]}…' "
                       f"(ADR-0038 §2: excepted requires a reason)")


def _adr_status_qualifier(text: str) -> str | None:
    """Return the `**Status:**` qualifier of an ADR body, lower-cased, or None.

    e.g. 'accepted (built)', 'accepted (audited)', 'accepted (remediated)',
    'accepted', 'proposed'. The qualifier is everything after `**Status:**`
    up to the first ` —` / `.` / newline so any trailing prose
    does not pollute the comparison.
    """
    m = re.search(r"\*\*Status:\*\*\s*([^\n]+)", text)
    if not m:
        return None
    raw = m.group(1).strip()
    # Cut at the first em-dash-with-space or full stop so a trailing clause
    # ("Accepted (built) — further notes.") reduces to the qualifier.
    raw = re.split(r"\s+—\s|(?<=\))\.", raw)[0].strip()
    return raw.lower()


def _referenced_adr_numbers(text: str) -> set[int]:
    """ADR numbers referenced in a body — `ADR-NNNN`, `(NNNN-….md)` links,
    and `adr/NNNN-` paths. Used to associate a close-out / BACKLOG closure
    claim with the specific ADRs it declares shipped."""
    nums: set[int] = set()
    for m in re.finditer(r"ADR-(\d{4})\b", text):
        nums.add(int(m.group(1)))
    for m in re.finditer(r"(?:adr/|\()(\d{4})-[a-z0-9][a-z0-9-]*\.md", text):
        nums.add(int(m.group(1)))
    return nums


def check_close_out_audited_consistency() -> None:
    """ADR-0052 — the unaudited-close-out gate.

    `check_adr_status_progression` gates the transition *into* a closure
    qualifier but is blind to an ADR *stranded below* its declared closure:
    `Accepted (built)` falls straight through. The failure mode: an ADR
    stranded at `Accepted (built)` while a referencing close-out / BACKLOG
    line declares it `Accepted (audited)` — the close-out commit that
    *announced* the flip touched no ADR file.

    This check closes the mechanical hole. It reconciles each ADR's status
    against the *declared-closure claim in the artefacts that reference it*:

      - a `docs/cycles/**/close-out.md` whose `**Final status:**` is
        `Accepted (audited)`;
      - a `docs/BACKLOG.md` per-`### OIM-NN` entry whose `**Status:**` is
        `Accepted (audited)`.

    For every ADR such an artefact names as shipped (an `ADR-NNNN` reference
    or a `NNNN-….md` link), if that ADR's own `**Status:**` is still
    `Accepted (built)` (not progressed to a closure qualifier), it is a
    DEFECT — the referencing artefact declares the ADR audited; the ADR
    file does not.

    CRITICAL — it reconciles against the *declared-closure claim*, not
    against `(built)` alone. A new ADR at `Accepted (built)` whose own
    backing work is still in flight (no close-out / BACKLOG line yet
    declares *it* audited) carries no audited claim to be inconsistent with,
    so it is NOT flagged.
    """
    if not ADR_DIR.exists():
        return

    # 1. ADRs stranded at `Accepted (built)` — the candidates that could be
    #    inconsistent with a referencing audited claim.
    stranded_built: set[int] = set()
    for p in sorted(ADR_DIR.glob("*.md")):
        if p.name in {"INDEX.md", "TEMPLATE.md"}:
            continue
        m_num = re.match(r"(\d{4})-", p.name)
        if not m_num:
            continue
        qual = _adr_status_qualifier(p.read_text(encoding="utf-8"))
        if qual == "accepted (built)":
            stranded_built.add(int(m_num.group(1)))

    if not stranded_built:
        return  # nothing can be inconsistent

    # 2. Gather the referencing artefacts that make an audited-closure claim,
    #    each with the ADR numbers it declares shipped.
    #    (source-label, declared-audited ADR numbers)
    claims: list[tuple[str, set[int]]] = []

    # 2a. Cycle close-outs.
    cycles_dir = REPO / "docs" / "cycles"
    if cycles_dir.exists():
        for co in sorted(cycles_dir.glob("**/close-out.md")):
            text = co.read_text(encoding="utf-8")
            m_final = re.search(r"\*\*Final status:\*\*\s*`?([^\n`]+)`?", text)
            if not m_final:
                continue
            if "accepted (audited)" in m_final.group(1).strip().lower():
                claims.append((str(co.relative_to(REPO)),
                               _referenced_adr_numbers(text)))

    # 2b. BACKLOG per-OIM-NN entries.
    backlog = REPO / "docs" / "BACKLOG.md"
    if backlog.exists():
        text = backlog.read_text(encoding="utf-8")
        # Split into `### ` sections; each section's first `**Status:**` line
        # is the entry status, and the section body is where it names ADRs.
        sections = re.split(r"(?m)^(?=###\s)", text)
        for sec in sections:
            head = sec.splitlines()[0] if sec.strip() else ""
            if not head.startswith("###"):
                continue
            m_status = re.search(r"\*\*Status:\*\*\s*\**\s*`?([^\n`]+)", sec)
            if not m_status:
                continue
            if "accepted (audited)" in m_status.group(1).strip().lower():
                claims.append((f"docs/BACKLOG.md ({head.lstrip('# ').strip()[:40]})",
                               _referenced_adr_numbers(sec)))

    # 3. Reconcile: any stranded-built ADR named by an audited claim is a defect.
    for source, declared in claims:
        for adr_num in sorted(declared & stranded_built):
            defect(f"docs/adr/{adr_num:04d}-*.md: status 'Accepted (built)' but "
                   f"{source} declares it 'Accepted (audited)' "
                   f"(ADR-0052: an ADR stranded below its declared closure — "
                   f"the close-out announced a flip the SSOT does not carry)")


# ---------------------------------------------------------------------------
# OIM-212 — Three new checks (ADR-0067):
#   1. check_count_surface_agreement — HARD defect: entity counts across
#      README.md, model/README.md, model/entities/INDEX.md (table + gloss +
#      Pack-sizes prose), model/ownership-map.md, docs/adr/INDEX.md, and
#      all model/diagrams/ .md + .d2 files.
#   2. check_two_sided_edges — WARNING (pending remediation of the pre-existing
#      latent set; hardens to DEFECT once OIM-213 remediation pass is complete):
#      entity **Consumed by** ↔ SD **Consumes** bidirectional consistency.
#   3. check_deferral_language — advisory WARNING: stale deferral phrasing in
#      reader-facing model prose.
#
# These three checks REUSE tools/diagrams/parser/ for entity/edge extraction
# (SSOT — no re-implementation of entity or SD parsing here).  The parser is
# imported lazily inside each check so the validator can still run if
# tools/diagrams/ is absent (e.g. in a stripped distribution).
# ---------------------------------------------------------------------------


def _load_parser_models() -> "tuple | None":
    """Attempt to import and parse the entity and service-domain models.

    Returns (EntityModel, ServiceDomainModel) on success, or None if the
    parser package is unavailable (distribution tree without tools/diagrams/).
    Errors during parsing are surfaced as WARNINGs — a parser failure must not
    silently suppress the checks.
    """
    try:
        import sys as _sys
        tools_path = str(REPO / "tools")
        if tools_path not in _sys.path:
            _sys.path.insert(0, tools_path)
        from diagrams.parser.entities import parse_entities
        from diagrams.parser.service_domains import parse_service_domains
        em = parse_entities(REPO)
        sdm = parse_service_domains(REPO)
        return em, sdm
    except ImportError:
        warn("check_count_surface_agreement / check_two_sided_edges: "
             "tools/diagrams/parser/ not importable — checks skipped")
        return None
    except Exception as exc:  # noqa: BLE001
        warn(f"check_count_surface_agreement / check_two_sided_edges: "
             f"parser raised {type(exc).__name__}: {exc} — checks skipped")
        return None


def _derive_entity_counts(em: "object") -> "dict":
    """Derive the canonical counts from the parsed EntityModel.

    Returns a dict with keys:
      core      — number of core entities (E-NN)
      per_pack  — {pack_name: count}
      total_spec — sum of specialisation counts
      total     — core + total_spec

    Pack names are the canonical lowercase slugs ('public-markets', etc.).
    """
    by_pack = em.by_pack()
    core_count = len(by_pack.get("core", []))
    pack_counts: dict[str, int] = {}
    total_spec = 0
    for pack_name, entities in by_pack.items():
        if pack_name == "core":
            continue
        pack_counts[pack_name] = len(entities)
        total_spec += len(entities)
    return {
        "core": core_count,
        "per_pack": pack_counts,
        "total_spec": total_spec,
        "total": core_count + total_spec,
    }


def _scan_entity_count_tokens(
    text: str,
    rel: str,
    counts: dict,
    *,
    skip_table_lines: bool = False,
) -> None:
    """Scan `text` for entity / pack count tokens and emit defects on mismatch.

    Targeted patterns only — each pattern must anchor to a specific phrasing
    that appears in reader-facing current-state prose, not in sub-counts or
    historical table rows. The full list of matched phrasings is:

    Total entity count (current-state assertions):
      - `**NN entities**:` (README.md canonical data model sentence)
      - `NN with the core` (README.md, model/README.md, entities/INDEX.md)
      - `**NN entities**` (entities/INDEX.md standalone bolded total)
      - `has NN entities —` (ownership-map.md "the canonical entity model has NN entities")
      - `NN entities —` in an OpenIM entity model label (diagrams)
      - `NN entities (NN core + N specialisation` (d2 layer-stack label)

    Core count:
      - `generalised core of NN` (README.md, ownership-map.md)
      - `core of NN entities` (README.md)
      - `NN core entities` (entities/INDEX.md)
      - `NN core + N specialisation` (d2 layer-stack label)

    Specialisation total:
      - `**NN specialisation entities**` (entities/INDEX.md)
      - `NN specialisation entities` (README.md inline)
      - `NN with the core` (multiple files — the "NN spec, NN with the core" form)

    Per-pack counts (Pack-sizes prose paragraph + table row in entities/INDEX.md):
      - `public-markets NN` / `fund-operations NN` / etc. (Pack-sizes prose)
      - The parenthesised gloss `(NN + NN + NN + NN + NN)` with PB/FO/PM/DR/RA order

    skip_table_lines: when True, lines beginning with `|` (markdown table rows)
    are excluded before scanning.  Used for docs/adr/INDEX.md where the
    per-ADR "Model after" column carries historical entity counts.

    Normalisation: D2 label strings store newlines as the literal two-character
    escape `\\n` (backslash + "n"), and HTML diagram labels use `<br/>`.
    Either sequence immediately before a digit prevents the `\\b` word-boundary
    pattern from firing (because "n" is a word character).  The scan_text is
    normalised — literal `\\n` and `<br/>` are replaced with a space — so that
    every count token in diagram surfaces is correctly detected regardless of
    the escape form used by the authoring tool.
    """
    total = counts["total"]
    core = counts["core"]
    spec = counts["total_spec"]
    per_pack = counts["per_pack"]

    scan_text = text
    if skip_table_lines:
        scan_text = "\n".join(
            line for line in text.splitlines()
            if not line.lstrip().startswith("|")
        )

    # Normalise D2/HTML escape sequences that suppress word-boundary matching.
    # Literal `\n` (backslash + n, as stored in .d2 label strings) and
    # `<br/>` / `<br />` (Mermaid/HTML label line-breaks) are replaced with a
    # single space so the `\b` boundary before a digit fires correctly.
    # This is scan_text-only; the original `text` is kept for line-number
    # lookups via `_line_of` below.
    scan_text = re.sub(r'\\n', ' ', scan_text)
    scan_text = re.sub(r'<br\s*/?>', ' ', scan_text, flags=re.IGNORECASE)

    def _line_of(m: re.Match) -> int:
        # Line number in the *original* text (not the filtered scan_text).
        # Re-search the original text for the matched string to get the
        # real line number, falling back to the scan_text offset.
        return text.count("\n", 0, text.find(m.group(0))) + 1 if m.group(0) in text else 1

    # ── 1. Total entity count ──────────────────────────────────────────────
    total_patterns: list[tuple[str, str]] = [
        # `**NN entities**:` — README.md "A canonical data model of **81 entities**:".
        # Only bold-total assertions; "**38 entities**" does not appear as a total.
        (r"\*\*(\d+)\s+entities\*\*\s*[:(—]", "bold-total **NN entities**:"),
        # `NN with the core` — "43 specialisation entities, 81 with the core".
        (r"\b(\d+)\s+with\s+the\s+core\b", "NN with the core"),
        # `has NN entities` — ownership-map.md "canonical entity model has 81 entities —".
        (r"\bhas\s+(\d+)\s+entities\b", "has NN entities"),
        # `NN entities —` or `NN entities (NN core` — diagram label forms in layer-stack.md
        # and d2/layer-stack.d2. Negative lookbehind on `(` prevents matching
        # per-pack parentheticals like "(11 entities)".
        (r"(?<!\()\b(\d+)\s+entities\s+[—(]", "NN entities — or ( (diagram label)"),
        # `OpenIM entity model is **NN entities**` — a specific phrasing.
        (r"entity model is \*\*(\d+)\s+entities", "entity model is **NN entities**"),
        # `NN entities\n` at end of a Mermaid label line, e.g.:
        # `M2["Canonical entity model<br/>81 entities — core + 5 specialisation packs...`
        # (already caught by the `NN entities —` pattern above)
    ]
    for pat, label in total_patterns:
        for m in re.finditer(pat, scan_text, re.IGNORECASE):
            found = int(m.group(1))
            if found != total:
                defect(f"{rel}:{_line_of(m)}: entity total says {found} ({label}); "
                       f"derived total is {total}")

    # ── 2. Core count ─────────────────────────────────────────────────────
    core_patterns: list[tuple[str, str]] = [
        # `generalised core of NN` — README.md, ownership-map.md.
        (r"\bgeneralised core of (\d+)\b", "generalised core of NN"),
        # `core of NN entities` — README.md inline.
        (r"\bcore of (\d+)\s+entit", "core of NN entities"),
        # `NN core entities` — entities/INDEX.md "with the 38 core entities".
        (r"\b(\d+)\s+core\s+entities\b", "NN core entities"),
        # `NN core + N specialisation` — d2 label form.
        (r"\b(\d+)\s+core\s*\+\s*\d+\s+specialisation", "NN core + N specialisation (d2)"),
    ]
    for pat, label in core_patterns:
        for m in re.finditer(pat, scan_text, re.IGNORECASE):
            found = int(m.group(1))
            if found != core:
                defect(f"{rel}:{_line_of(m)}: core entity count says {found} ({label}); "
                       f"derived core count is {core}")

    # ── 3. Specialisation total ───────────────────────────────────────────
    spec_patterns: list[tuple[str, str]] = [
        # `**NN specialisation entities**` — entities/INDEX.md bolded total.
        (r"\*\*(\d+)\s+specialisation\s+entit", "**NN specialisation entities**"),
        # `NN specialisation entities` — README.md inline.
        (r"\b(\d+)\s+specialisation\s+entities\b", "NN specialisation entities"),
    ]
    for pat, label in spec_patterns:
        for m in re.finditer(pat, scan_text, re.IGNORECASE):
            found = int(m.group(1))
            if found != spec:
                defect(f"{rel}:{_line_of(m)}: specialisation entity count says {found} ({label}); "
                       f"derived spec count is {spec}")

    # ── 4. Per-pack counts ────────────────────────────────────────────────
    # Pack-sizes prose paragraph: "public-markets NN, fund-operations NN, ..."
    # The pack name appears immediately before a space+number.
    pack_label_map = {
        "public-markets": "public-markets",
        "fund-operations": "fund-operations",
        "private-markets": "private-markets",
        "derivatives": "derivatives",
        "real-assets": "real-assets",
    }
    # OIM-212 MN-3 carry (OIM-210): tighten the per-pack count pattern so it
    # only fires when the number is followed by a comma, period, space-and-word,
    # or end-of-string — not when followed by a hyphen (e.g. "derivatives 5-year"
    # would be a latent false-positive with the bare \b pattern).
    for pack_slug, canonical in pack_label_map.items():
        pat = rf"\b{re.escape(pack_slug)}\s+(\d+)(?=[,.\s]|$)"
        for m in re.finditer(pat, scan_text, re.IGNORECASE):
            expected = per_pack.get(canonical)
            if expected is None:
                continue
            found = int(m.group(1))
            if found != expected:
                defect(f"{rel}:{_line_of(m)}: pack '{canonical}' count says {found}; "
                       f"derived count is {expected}")

    # Parenthesised gloss `(NN + NN + NN + NN + NN)` — the five-pack
    # addition form in entities/INDEX.md "All five specialisation packs are
    # built. **47 specialisation entities** across the five (11 + 12 + 14 + 5 + 5)".
    # Order is canonical PB→FO→PM→DR→RA per ADR-0063.
    gloss_pat = re.compile(
        r"\((\d+)\s*\+\s*(\d+)\s*\+\s*(\d+)\s*\+\s*(\d+)\s*\+\s*(\d+)\)"
    )
    for m in gloss_pat.finditer(scan_text):
        found_vals = [int(m.group(i)) for i in range(1, 6)]
        expected_vals = [
            per_pack.get("public-markets", 0),
            per_pack.get("fund-operations", 0),
            per_pack.get("private-markets", 0),
            per_pack.get("derivatives", 0),
            per_pack.get("real-assets", 0),
        ]
        if found_vals != expected_vals:
            defect(f"{rel}:{_line_of(m)}: parenthesised pack-size gloss says "
                   f"({' + '.join(str(v) for v in found_vals)}); "
                   f"derived pack sizes are "
                   f"({' + '.join(str(v) for v in expected_vals)}) "
                   f"(public-markets + fund-operations + private-markets + derivatives + real-assets)")


def _scan_entity_index_table(
    text: str,
    rel: str,
    per_pack: dict,
) -> None:
    """Check the | Pack | Entities | ... table in entities/INDEX.md.

    The table rows look like:
    | **[public-markets/](...) (`PB-NN`)** | 11 | What it covers |
    """
    pack_row_pat = re.compile(
        r"^\|\s*\*?\*?\[?(public-markets|fund-operations|private-markets|derivatives|real-assets)"
        r"[^\|]*\|\s*(\d+)\s*\|",
        re.M | re.IGNORECASE,
    )
    for m in pack_row_pat.finditer(text):
        pack_name = m.group(1).lower()
        found = int(m.group(2))
        expected = per_pack.get(pack_name)
        if expected is None:
            continue
        line_no = text.count("\n", 0, m.start()) + 1
        if found != expected:
            defect(f"{rel}:{line_no}: entity INDEX table row '{pack_name}' says {found}; "
                   f"derived count is {expected}")


def check_count_surface_agreement(em: "object") -> None:
    """HARD defect: every entity/pack count token across all reader-facing surfaces
    must agree with the filesystem-derived canonical counts.

    Surfaces scanned:
      - README.md
      - model/README.md
      - model/entities/INDEX.md  (table + gloss + Pack-sizes prose paragraph)
      - model/ownership-map.md
      - docs/adr/INDEX.md
      - model/diagrams/*.md  (all diagram .md files)
      - model/diagrams/d2/*.d2  (all D2 source files, incl. layer-stack.d2)

    Added: OIM-212 / ADR-0067.  Closes the OIM-204 d2-count blind spot, the
    OIM-206 d2-count blind spot, and the OIM-207 Pack-sizes prose blind spot.
    """
    counts = _derive_entity_counts(em)

    # Surfaces to scan for entity count tokens.
    surfaces: list[str] = [
        "README.md",
        "model/README.md",
        "model/entities/INDEX.md",
        "model/ownership-map.md",
    ]
    if BUILD_TRAIL_PRESENT:
        surfaces.append("docs/adr/INDEX.md")

    for rel in surfaces:
        path = REPO / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # docs/adr/INDEX.md has historical counts in per-row table cells;
        # skip table lines so only the current-state prose header is scanned.
        skip_table = rel == "docs/adr/INDEX.md"
        _scan_entity_count_tokens(text, rel, counts, skip_table_lines=skip_table)
        # Per-pack entity table check (only relevant for entities/INDEX.md).
        if rel == "model/entities/INDEX.md":
            _scan_entity_index_table(text, rel, counts["per_pack"])

    # Diagram surfaces — every .md and .d2 under model/diagrams/.
    diag_dir = REPO / "model" / "diagrams"
    if diag_dir.is_dir():
        for diag_file in sorted(diag_dir.rglob("*")):
            if diag_file.suffix not in {".md", ".d2"}:
                continue
            if not diag_file.is_file():
                continue
            rel = str(diag_file.relative_to(REPO)).replace("\\", "/")
            text = diag_file.read_text(encoding="utf-8")
            _scan_entity_count_tokens(text, rel, counts)


def _load_two_sided_edge_baseline() -> "set[tuple[str, str]] | None":
    """Load the grandfathered asymmetric-edge baseline from
    `tools/openim-validate/two_sided_edge_baseline.json`.

    Returns a set of (entity_id, sd_id) pairs that are in the baseline
    (grandfathered — exempt from the hard-defect gate).  Returns None
    if the file does not exist (which is itself a defect — the baseline
    must be present for the ratchet to be operational).
    """
    baseline_path = Path(__file__).parent / "two_sided_edge_baseline.json"
    if not baseline_path.exists():
        defect("check_two_sided_edges: two_sided_edge_baseline.json missing — "
               "the ratchet baseline must be present for the edge gate to run "
               "(OIM-212 / ADR-0067)")
        return None
    try:
        import json
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        return {(entry["entity_id"], entry["sd_id"]) for entry in data.get("entries", [])}
    except Exception as exc:  # noqa: BLE001
        defect(f"check_two_sided_edges: could not parse two_sided_edge_baseline.json: {exc}")
        return None


def check_two_sided_edges(em: "object", sdm: "object") -> None:
    """HARD DEFECT (ratchet): every entity **Consumed by** SD must have a
    matching **Consumes** entry on the SD, and vice versa.

    Grandfathered pre-existing asymmetric edges (the latent set of 659 pairs
    that existed as of OIM-212 cycle-2) are listed in
    `tools/openim-validate/two_sided_edge_baseline.json`.  Edges in the
    baseline are allowed (they emit WARNINGs so the debt remains visible) but
    do NOT block the build.  Any NEW asymmetric edge that is NOT in the
    baseline is a HARD DEFECT — this is the gate that prevents OIM-208/209
    from adding new one-sided edges.

    The baseline must only shrink.  OIM-216 tracks the burn-down of the
    grandfathered set to empty (true bidirectionality).  When the baseline
    reaches zero entries, delete the file and remove the `_load_two_sided_edge_baseline()`
    call here; the check becomes a pure HARD DEFECT with no exceptions.

    The check REUSES tools/diagrams/parser/ for edge extraction (SSOT — the
    entity parser's `consumed_by` list and the SD parser's `consumes_entities`
    list are the ground truth).  The `consumed_by` list is extracted only from
    the structured consumer list in entity files, not from any trailing prose
    clarification sentence (e.g. the FO-08↔SD-13.2 read-from-master prose is
    correctly excluded by the parser after the OIM-212 cycle-2 M2 fix).

    Added: OIM-212 / ADR-0067.  Hardened from WARNING to HARD DEFECT ratchet:
    OIM-212 cycle-2 (true count 659; baseline snapshot 2026-06-14).
    Would have caught: OIM-204 one-sided edges; OIM-207 SD-13.2 mislabel.
    """
    baseline = _load_two_sided_edge_baseline()
    if baseline is None:
        return  # baseline load failed; defect already emitted

    # Build maps.
    entity_consumed_by: dict[str, set[str]] = {}
    for e in em.entities:
        entity_consumed_by[e.id] = set(e.consumed_by)

    sd_consumes: dict[str, set[str]] = {}
    for sd in sdm.all_sds():
        sd_consumes[sd.id] = set(sd.consumes_entities)

    # Direction 1: entity says "Consumed by SD-X" but SD-X doesn't list entity in Consumes.
    for eid, sds in sorted(entity_consumed_by.items()):
        for sid in sorted(sds):
            if sid not in sd_consumes:
                # SD doesn't exist — already caught by check_index_links / parse errors.
                continue
            if eid not in sd_consumes[sid]:
                if (eid, sid) in baseline:
                    # Grandfathered — warn so the debt remains visible but do not block.
                    warn(f"check_two_sided_edges: {eid} declares '**Consumed by:** {sid}' "
                         f"but {sid} '**Consumes:**' does not list {eid} "
                         f"(grandfathered in OIM-212 baseline; OIM-216 burn-down)")
                else:
                    defect(f"check_two_sided_edges: {eid} declares '**Consumed by:** {sid}' "
                           f"but {sid} '**Consumes:**' does not list {eid} "
                           f"(new asymmetric edge — not in the OIM-212 ratchet baseline; "
                           f"this is a HARD DEFECT)")

    # Direction 2: SD says "Consumes entity-X" but entity-X doesn't list SD in Consumed by.
    for sid, eids in sorted(sd_consumes.items()):
        for eid in sorted(eids):
            if eid not in entity_consumed_by:
                # Entity doesn't exist — already caught by parse errors.
                continue
            if sid not in entity_consumed_by[eid]:
                if (eid, sid) in baseline:
                    warn(f"check_two_sided_edges: {sid} declares '**Consumes:** {eid}' "
                         f"but {eid} '**Consumed by:**' does not list {sid} "
                         f"(grandfathered in OIM-212 baseline; OIM-216 burn-down)")
                else:
                    defect(f"check_two_sided_edges: {sid} declares '**Consumes:** {eid}' "
                           f"but {eid} '**Consumed by:**' does not list {sid} "
                           f"(new asymmetric edge — not in the OIM-212 ratchet baseline; "
                           f"this is a HARD DEFECT)")


# Deferral-language patterns scanned across reader-facing model prose.
# Advisory WARNING only — some deferral language is legitimate (genuine future
# extensions); this surfaces stale instances (e.g. a "later addition" that is
# now built) for human review.
#
# OIM-212 MN-2 carry (OIM-210): bare r"\bdeferred\b" generated false-positives
# on legitimate domain terms ("deferred tax", "deferred compensation",
# "deferred to the accounting layer", "deferred to the next dealing cycle",
# "deferred to ISDA CDM").  Replaced with build-state-specific phrasings
# that only fire on stale model-build language, not on operational or
# domain usage.  OIM-212 MN-3 carry: per-pack count pattern tightened below.
_DEFERRAL_PATTERNS: list[str] = [
    r"a? ?later additions?",
    r"a later entity",
    r"\bdeferred to (?:a later|OIM-\d+|the next (?:item|cycle|build))\b",
    r"\bdeferred (?:extension|entity|item|to be built)\b",
    r"not yet modelled",
    r"future extension",
    r"\bforthcoming\b",
]

# Reader-facing model directories / files scanned for deferral language.
# Builder-facing surfaces (docs/, CLAUDE.md, tools/) are NOT scanned.
_DEFERRAL_SCAN_DIRS: list[str] = [
    "model/entities",
    "model/service-domains",
    "model/diagrams",
]
_DEFERRAL_SCAN_ROOTS: list[str] = [
    "model/README.md",
    "README.md",
]


def check_deferral_language() -> None:
    """Advisory WARNING (not a defect): scan reader-facing model prose for
    deferral phrasing that may describe a now-built entity or capability.

    Patterns flagged: 'a later addition', 'a later entity', build-state
    deferral forms ('deferred to OIM-NN', 'deferred to a later ...', etc.),
    'not yet modelled', 'future extension', 'forthcoming'.

    Bare 'deferred' is NOT flagged — it fires false-positives on legitimate
    domain terms ('deferred tax', 'deferred compensation', 'deferred to
    the accounting layer', 'deferred to ISDA CDM', 'deferred to the next
    dealing cycle').  Only build-state-specific phrasings are flagged.

    A WARNING listing the file:line is emitted for each hit. Human review
    determines whether the phrasing is legitimate (a genuine future extension)
    or stale (an already-built entity still described as 'a later addition',
    the OIM-207 residual pattern).

    Added: OIM-212 / ADR-0067. Deferral-pattern narrowed in OIM-210 cycle-1
    (MN-2 carry) to remove the bare r'\\bdeferred\\b' false-positive source.
    Would have surfaced: OIM-207 residual — FO-02:73, fund-operations/README.md:26.
    """
    combined_re = re.compile(
        "|".join(f"(?:{p})" for p in _DEFERRAL_PATTERNS),
        re.IGNORECASE,
    )

    def _scan_file(path: Path) -> None:
        if not path.is_file():
            return
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            return
        for m in combined_re.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            rel = str(path.relative_to(REPO)).replace("\\", "/")
            warn(f"check_deferral_language: {rel}:{line_no}: "
                 f"deferral phrasing {m.group()!r} — review for stale built-state")

    for dir_rel in _DEFERRAL_SCAN_DIRS:
        scan_dir = REPO / dir_rel
        if not scan_dir.is_dir():
            continue
        for md_file in sorted(scan_dir.rglob("*.md")):
            _scan_file(md_file)

    for file_rel in _DEFERRAL_SCAN_ROOTS:
        _scan_file(REPO / file_rel)


def check_diagram_render_coverage() -> None:
    """Hybrid D generator coverage gate.

    The Hybrid D static-site generator (`tools/diagrams/build.py`) emits
    one HTML page per BD, per SD, and per entity, plus a landing page,
    a landscape, and an ERD page. This check confirms that the latest
    `dist/` directory carries the full set with substantive content, so
    a build that silently drops a declared element (or renders an empty
    page) is caught before it ships.

    Behaviour:

    - If `dist/` is absent (fresh checkout / no build yet), emit a
      warning, not a defect — the validator must still PASS on a clean
      clone so it can run as a pre-commit gate.
    - If `dist/` is present, every declared BD / SD / entity must have
      a corresponding `bd-NN.html` / `sd-NN.M.html` / `entity-X-NN.html`
      file, plus `index.html`, `landscape.html`, `erd.html`. A miss is
      a defect.
    - Substantive coverage:
        (i)   Each SD page contains every declared Service Operation
              by name.
        (ii)  Each entity page contains an `<a>` href to every FK target.
        (iii) Each BD page contains an `<a>` href to every member SD.
        (iv)  The landscape page contains an `<a>` href / target reference
              to every BD landing page.

      All four substantive checks use structural matching (stdlib
      `html.parser`) — SO names must be the text of an `<li>` element;
      FK / member-SD / BD-landing references must be the `href` attribute
      of an `<a>` element. Plain substring matching could pass a typo'd
      SO name (the typo substring-matches itself in source and rendered
      output alike) or let an SO name in unrelated prose mask an empty
      operations list.

    The path can be overridden via the `OPENIM_DIST` env var (a `--dist`
    CLI flag is a possible future extension).
    """
    import os
    dist_path = Path(os.environ.get("OPENIM_DIST", REPO / "dist"))
    if not dist_path.is_dir():
        warn(f"check_diagram_render_coverage: {dist_path.relative_to(REPO) if dist_path.is_relative_to(REPO) else dist_path} "
             f"absent — run `python tools/diagrams/build.py --out dist/` "
             f"first")
        return

    emitted = {p.name for p in dist_path.iterdir() if p.is_file() and p.suffix == ".html"}
    missing: list[str] = []

    # Static pages.
    for fixed in ("index.html", "landscape.html", "erd.html"):
        if fixed not in emitted:
            missing.append(fixed)

    # Catalogue of BDs and their SDs (re-parsed from disk so the check is
    # independent of the generator's in-memory model).
    bd_to_sds: dict[int, list[str]] = {}
    for bd in bd_dirs():
        m = re.match(r"BD-(\d+)-", bd.name)
        if not m:
            continue
        bd_num = int(m.group(1))
        page = f"bd-{bd_num:02d}.html"
        if page not in emitted:
            missing.append(page)
        sd_keys: list[str] = []
        for sd_file in sorted(bd.glob("SD-*.md")):
            sm = re.match(rf"SD-{bd_num:02d}\.(\d+)-", sd_file.name)
            if not sm:
                continue
            sd_key = f"{bd_num:02d}.{sm.group(1)}"
            sd_keys.append(sd_key)
            sd_page = f"sd-{sd_key}.html"
            if sd_page not in emitted:
                missing.append(sd_page)
        bd_to_sds[bd_num] = sd_keys

    # Per-entity files + FK targets — parsed shallow from each entity .md.
    entity_fks: dict[str, list[str]] = {}
    if ENTITY_DIR.is_dir():
        fk_re = re.compile(r"FK\s*[\->→]+\s*((?:E|PM|PB|DR|RA|FO)[_-]?\d{2,3})", re.IGNORECASE)
        for ent_path in sorted(ENTITY_DIR.rglob("*.md")):
            if ent_path.name.upper().startswith("README") or ent_path.name == "INDEX.md":
                continue
            em = re.match(r"^(E|PM|PB|DR|RA|FO)-(\d{2})-", ent_path.name)
            if not em:
                continue
            ent_id = f"{em.group(1)}-{em.group(2)}"
            ent_page = f"entity-{ent_id}.html"
            if ent_page not in emitted:
                missing.append(ent_page)
            fks: list[str] = []
            for fk_m in fk_re.finditer(ent_path.read_text(encoding="utf-8")):
                raw = fk_m.group(1).replace("_", "-").upper()
                if "-" in raw:
                    pfx, num = raw.split("-", 1)
                    fk = f"{pfx}-{num.zfill(2)}"
                else:
                    # Strip leading prefix letters (E / PM / PB / DR / RA / FO).
                    for pfx in ("PM", "PB", "DR", "RA", "FO"):
                        if raw.startswith(pfx):
                            fk = f"{pfx}-{raw[len(pfx):].zfill(2)}"
                            break
                    else:
                        fk = f"{raw[0]}-{raw[1:].zfill(2)}"
                if fk != ent_id and fk not in fks:
                    fks.append(fk)
            entity_fks[ent_id] = fks

    for page in missing:
        defect(f"check_diagram_render_coverage: {page} missing from "
               f"{dist_path.relative_to(REPO) if dist_path.is_relative_to(REPO) else dist_path}/ "
               f"(the generator's coverage assertion must pass)")

    # Substantive coverage — only run if filename coverage is complete (no
    # point reporting "SD-XX missing op Y" if the page itself is absent).
    if missing:
        return

    # (i) SD pages — every declared SO name appears as the text of an
    # <li> element on the SD page. Structural check via stdlib
    # html.parser rather than a plain substring match.
    import html as _html
    sd_h2_op_re = re.compile(r"^##\s+Service Operations\s*$", re.MULTILINE)
    bullet_re = re.compile(r"^-\s+(.+?)\s*$", re.MULTILINE)
    bold_name_re = re.compile(r"\*\*(.+?)\*\*")
    for bd in bd_dirs():
        m = re.match(r"BD-(\d+)-", bd.name)
        if not m:
            continue
        bd_num = int(m.group(1))
        for sd_file in sorted(bd.glob("SD-*.md")):
            sm = re.match(rf"SD-{bd_num:02d}\.(\d+)-", sd_file.name)
            if not sm:
                continue
            sd_key = f"{bd_num:02d}.{sm.group(1)}"
            sd_id = f"SD-{sd_key}"
            text = sd_file.read_text(encoding="utf-8")
            h2m = sd_h2_op_re.search(text)
            if not h2m:
                continue
            start = h2m.end()
            nxt = re.search(r"^##\s+\S", text[start:], re.MULTILINE)
            body = text[start:(start + nxt.start()) if nxt else len(text)]
            op_names: list[str] = []
            for bm in bullet_re.finditer(body):
                rest = bm.group(1).strip()
                bnm = bold_name_re.match(rest)
                if bnm:
                    op_names.append(bnm.group(1).strip())
                else:
                    for sep in (" — ", " – ", " - ", ": ", "."):
                        if sep in rest:
                            op_names.append(rest.split(sep, 1)[0].strip())
                            break
                    else:
                        op_names.append(rest)
            page_text = (dist_path / f"sd-{sd_key}.html").read_text(encoding="utf-8")
            li_texts = _extract_li_texts(page_text)
            for op_name in op_names:
                if not op_name:
                    continue
                escaped = _html.escape(op_name, quote=True)
                if not _li_carries_so_name(li_texts, op_name, escaped):
                    defect(f"check_diagram_render_coverage: sd-{sd_key}.html "
                           f"missing Service Operation '{op_name}' from {sd_id} "
                           f"(SO substantive coverage; structural <li> match)")

    # (ii) Entity pages — every FK target appears as the href value of an
    # <a> element. Hrefs are parsed structurally so a mis-routed (or
    # non-anchor) mention does not pass.
    for ent_id, fks in entity_fks.items():
        page_text = (dist_path / f"entity-{ent_id}.html").read_text(encoding="utf-8")
        hrefs = _extract_anchor_hrefs(page_text)
        for fk in fks:
            target = f"entity-{fk}.html"
            if not _hrefs_resolve_to(hrefs, target):
                defect(f"check_diagram_render_coverage: entity-{ent_id}.html "
                       f"missing FK drill-down to {fk} "
                       f"(FK substantive coverage; no <a> href "
                       f"resolving to {target})")

    # (iii) BD pages — every member SD appears as the href value of an
    # <a> element.
    for bd_num, sd_keys in bd_to_sds.items():
        page_text = (dist_path / f"bd-{bd_num:02d}.html").read_text(encoding="utf-8")
        hrefs = _extract_anchor_hrefs(page_text)
        for sd_key in sd_keys:
            target = f"sd-{sd_key}.html"
            if not _hrefs_resolve_to(hrefs, target):
                defect(f"check_diagram_render_coverage: bd-{bd_num:02d}.html "
                       f"missing drill-down to SD-{sd_key} "
                       f"(BD member-SD substantive coverage; no "
                       f"<a> href resolving to {target})")

    # (iv) Landscape — every BD landing referenced as the href value of
    # an <a> element.
    landscape_text = (dist_path / "landscape.html").read_text(encoding="utf-8")
    landscape_hrefs = _extract_anchor_hrefs(landscape_text)
    for bd_num in bd_to_sds.keys():
        target = f"bd-{bd_num:02d}.html"
        if not _hrefs_resolve_to(landscape_hrefs, target):
            defect(f"check_diagram_render_coverage: landscape.html missing "
                   f"reference to BD-{bd_num:02d} ({target}) "
                   f"(landscape-to-BD substantive coverage; no "
                   f"<a> href resolving to the target)")


# --- structural HTML helpers, stdlib only --- #
def _extract_li_texts(page: str) -> list[str]:
    """Return the text content of every <li> element in `page`.

    Mirror of `tools/diagrams/build.py:_extract_li_texts`. Kept in the
    validator file (not imported from the generator) so the validator
    runs without the `tools/diagrams/` package on sys.path.
    """
    from html.parser import HTMLParser

    class _LIExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._depth = 0
            self._buf: list[str] = []
            self.items: list[str] = []

        def handle_starttag(self, tag, attrs) -> None:  # noqa: ARG002
            if tag == "li":
                if self._depth == 0:
                    self._buf = []
                self._depth += 1

        def handle_endtag(self, tag) -> None:
            if tag == "li" and self._depth > 0:
                self._depth -= 1
                if self._depth == 0:
                    self.items.append("".join(self._buf).strip())
                    self._buf = []

        def handle_data(self, data) -> None:
            if self._depth > 0:
                self._buf.append(data)

    parser = _LIExtractor()
    try:
        parser.feed(page)
        parser.close()
    except Exception:  # noqa: BLE001
        pass
    return parser.items


def _li_carries_so_name(li_texts: list[str], name: str, escaped: str) -> bool:
    """Return True if any <li> text exactly carries the SO name.

    Mirror of `tools/diagrams/build.py:_li_carries_so_name`.
    """
    for li in li_texts:
        stripped = li.strip()
        if stripped == name or stripped == escaped:
            return True
        for sep in (" — ", " – ", " - ", ": ", ". "):
            if stripped.startswith(name + sep) or stripped.startswith(escaped + sep):
                return True
    return False


def _extract_anchor_hrefs(page: str) -> set[str]:
    """Return every `href` (and SVG `xlink:href`) on every `<a>` element.

    Mirror of `tools/diagrams/build.py:_extract_anchor_hrefs`. Captures
    both HTML `<a href="...">` (in the page chrome) and SVG
    `<a xlink:href="...">` (Graphviz emits the SVG-namespace form for
    node drill-down links inside the embedded `<svg>`).
    """
    from html.parser import HTMLParser

    class _AHrefExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.hrefs: set[str] = set()

        def handle_starttag(self, tag, attrs) -> None:
            if tag == "a":
                for k, v in attrs:
                    if v is None:
                        continue
                    # HTML `href` and SVG `xlink:href` both point at a
                    # drill-down target. Either suffices for substantive
                    # coverage; some templates carry the HTML form on the
                    # chrome links and Graphviz emits the SVG form on the
                    # diagram nodes.
                    if k == "href" or k.endswith(":href") or k == "xlink:href":
                        self.hrefs.add(v)

    parser = _AHrefExtractor()
    try:
        parser.feed(page)
        parser.close()
    except Exception:  # noqa: BLE001
        pass
    return parser.hrefs


def _hrefs_resolve_to(hrefs: set[str], target: str) -> bool:
    """Return True if any href in `hrefs` resolves to `target`.

    Mirror of `tools/diagrams/build.py:_hrefs_resolve_to`. Accepts the
    common forms: `target`, `./target`, `/target`, plus `#fragment`
    suffix tolerance.
    """
    for h in hrefs:
        bare = h.split("#", 1)[0].split("?", 1)[0]
        if bare == target:
            return True
        if bare.endswith("/" + target):
            return True
    return False


def main() -> int:
    if not SD_DIR.exists():
        print(f"FATAL: {SD_DIR} not found — run from the OpenIM repo.")
        return 1
    # The `if BUILD_TRAIL_PRESENT` gates cover the checks that read the
    # private build trail (docs/adr/**, docs/BACKLOG.md, docs/cycles/**,
    # CLAUDE.md) — skipped in a distribution tree, byte-identical order
    # when the trail is present.
    counts = check_business_domains()
    check_index(counts)
    check_index_links()
    if BUILD_TRAIL_PRESENT:
        check_adrs()
    check_count_agreement(counts)
    check_prose_counts(counts)
    if BUILD_TRAIL_PRESENT:
        check_adr_index_prose_counts(counts)
        check_backlog_prose_counts(counts)
    check_per_bd_sd_annotations(counts)
    check_per_row_bd_tables(counts)
    check_ownership_map()
    check_ownership_map_producing_side()
    check_consuming_side_partitions()
    check_sd_name_resolution()
    if BUILD_TRAIL_PRESENT:
        check_adr_status_progression()
        check_dispatch_scope_completeness()
        check_close_out_audited_consistency()
    # OIM-212 / ADR-0067 — three new checks.
    parser_models = _load_parser_models()
    if parser_models is not None:
        _em, _sdm = parser_models
        check_count_surface_agreement(_em)
        check_two_sided_edges(_em, _sdm)
    check_deferral_language()
    check_diagram_render_coverage()

    print(f"OpenIM structural-integrity validator — "
          f"{len(counts)} Business Domains, {sum(counts.values())} Service Domains")
    if not BUILD_TRAIL_PRESENT:
        print("  INFO     private build-trail checks skipped "
              "(docs/ not present in this distribution)")
    for w in warnings:
        print(f"  WARNING  {w}")
    for d in defects:
        print(f"  DEFECT   {d}")
    if defects:
        print(f"\nFAIL — {len(defects)} defect(s), {len(warnings)} warning(s).")
        return 1
    print(f"\nPASS — 0 defects, {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
