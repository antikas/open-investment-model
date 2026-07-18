"""Pack-registry SSOT — the single source of pack identity across `tools/`.

The OpenIM model has one core entity base plus a fixed set of specialisation
packs.  Every fact about "which packs exist" — the entity-id prefix, the
directory slug, the reader-facing display name, and the render palette — lives
here, once.  Each `tools/` consumer imports from this module instead of keeping
its own hardcoded copy.

Why this exists (OIM-211): the pack list used to be re-declared independently
in the validator, the diagram parser, the diagram renderer, and the export
parser — a prefix alternation here, a slug->prefix map there, a colour table
somewhere else.  Every new consumer was another place to forget when a pack was
added, and the same "checked all of tools/ but missed a sibling" defect
(P-MAJ-NEW-1, the class-walk-not-instance-grep lesson) reproduced across three
audit rings.  Consolidating to one table removes the duplication at the root:
adding a pack is a single edit here, and every consumer picks it up.

Ordering — the tuple below is the canonical reader-facing order established by
OIM-215: the core base first, then the specialisation packs in the order
public-markets -> fund-operations -> private-markets -> derivatives ->
real-assets (PB -> FO -> PM -> DR -> RA).  OIM-215 deferred single-sourcing this
order to OIM-211; this module is now its SSOT.

Note on parse/render order: the entity parser groups packs by directory-listing
order (alphabetical), which is a *separate* concern from this reader-facing
canonical order.  Consumers that need "which packs and their identity" read this
registry; the ERD cluster order continues to follow the parsed model's own
grouping, unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pack:
    """One pack's identity: prefix, slug, display name, and render palette."""

    prefix: str        # entity-id prefix (e.g. "E", "PB", "FO", "PM", "DR", "RA")
    slug: str          # directory slug / canonical lowercase name
    display_name: str  # reader-facing name
    fill: str          # palette fill colour (hex)
    stroke: str        # palette stroke colour (hex)
    is_core: bool      # True for the core base; False for specialisation packs


# The one ordered table.  Canonical OIM-215 order: core, then PB, FO, PM, DR, RA.
# Palette colours are carried over verbatim from the previous dot_gen.pack_colours
# table (behaviour-preserving — the render output is identical per slug).
PACKS: tuple[Pack, ...] = (
    Pack("E",  "core",            "Core",            "#dfe8f7", "#5b7aa6", True),
    Pack("PB", "public-markets",  "Public-markets",  "#e5efe1", "#5b8a48", False),
    Pack("FO", "fund-operations", "Fund-Operations", "#fef3e2", "#b07d2a", False),
    Pack("PM", "private-markets", "Private-markets", "#e9e2f0", "#7a5b9b", False),
    Pack("DR", "derivatives",     "Derivatives",     "#fbf0d8", "#a07b2c", False),
    Pack("RA", "real-assets",     "Real-assets",     "#f7dfe0", "#a65b5b", False),
)


# --- derived views (all single-sourced from PACKS) -------------------------

#: Every pack prefix, in canonical order — including the core "E".
PREFIXES: tuple[str, ...] = tuple(p.prefix for p in PACKS)

#: Specialisation-pack prefixes only (no core), in canonical order.
SPEC_PREFIXES: tuple[str, ...] = tuple(p.prefix for p in PACKS if not p.is_core)

#: Specialisation-pack slugs only (no core), in canonical order.
SPEC_SLUGS: tuple[str, ...] = tuple(p.slug for p in PACKS if not p.is_core)

#: Regex-alternation body for every prefix (e.g. "E|PB|FO|PM|DR|RA").  Drop this
#: inside an existing group: r"(" + PREFIX_ALT + r")-\d{2}".  Prefixes are
#: mutually exclusive, so alternation order does not affect matching.
PREFIX_ALT: str = "|".join(PREFIXES)

#: Regex-alternation body for specialisation prefixes only (no core "E").
SPEC_PREFIX_ALT: str = "|".join(SPEC_PREFIXES)

#: Regex-alternation body for specialisation slugs (e.g. "public-markets|...").
SPEC_SLUG_ALT: str = "|".join(SPEC_SLUGS)

#: prefix -> slug, for every pack (e.g. {"E": "core", "PM": "private-markets", ...}).
PREFIX_TO_SLUG: dict[str, str] = {p.prefix: p.slug for p in PACKS}

#: slug -> prefix, specialisation packs only (used to resolve a pack directory
#: name to its entity prefix).
SLUG_TO_PREFIX: dict[str, str] = {p.slug: p.prefix for p in PACKS if not p.is_core}

#: slug -> (fill, stroke) render palette, for every pack.  Replaces the previous
#: dot_gen.pack_colours dict verbatim.
PACK_COLOURS: dict[str, tuple[str, str]] = {p.slug: (p.fill, p.stroke) for p in PACKS}
