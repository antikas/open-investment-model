"""Mechanical guard — pack-recognition completeness across tools/diagrams/render/.

This test converts the recurring class-walk-not-instance-grep defect (reproduced
in OIM-201 cycles 1, 2 and 3) into a machine-enforced constraint:

1. Every pack known to the parsed entity model has a colour entry in
   dot_gen.pack_colours.  Adding a sixth pack without extending pack_colours
   causes this test to fail immediately — no brief author needs to remember.

2. tools/diagrams/render/site.py MUST NOT contain a hardcoded exact four-slug
   or five-slug specialisation-pack enumeration.  The ERD prose must be derived
   from the parsed model, not a frozen literal list.

Both assertions run against the LIVE entity model (parsed from the real repo)
and the LIVE render-stage source files.  No Graphviz binary is required — the
test only imports Python modules and reads source text.

To run (from the repo root):
    python -m pytest tools/diagrams/tests/test_pack_recognition_guard.py
    python -m unittest tools.diagrams.tests.test_pack_recognition_guard
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import unittest

# Make the tools/ package importable from any working directory.
ROOT = Path(__file__).resolve().parents[3]  # the repo root
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from diagrams.parser import parse_entities
from diagrams.render import dot_gen


class TestPackColourCompleteness(unittest.TestCase):
    """dot_gen.pack_colours must cover every pack the entity model knows about.

    Guards P-MAJ-NEW-1 / the recurring radius-was-wrong class: adding a new
    specialisation pack without extending pack_colours now fails the test suite
    rather than silently rendering the new pack in default grey.
    """

    def test_pack_colours_covers_all_model_packs(self) -> None:
        """Every pack returned by entity_model.by_pack() has a colour entry."""
        em = parse_entities(ROOT)
        model_packs = set(em.by_pack().keys())
        colour_packs = _extract_pack_colours()
        missing = model_packs - colour_packs
        self.assertEqual(
            missing,
            set(),
            f"dot_gen.pack_colours is missing entries for pack(s): {sorted(missing)}. "
            f"Add a colour entry for each new pack to tools/diagrams/render/dot_gen.py "
            f"'pack_colours' dict (OIM-211 will consolidate this into a pack-registry SSOT).",
        )

    def test_pack_colours_is_superset_of_model_packs(self) -> None:
        """Alias assertion: set(pack_colours) ⊇ set(entity_model.by_pack())."""
        em = parse_entities(ROOT)
        model_packs = set(em.by_pack().keys())
        colour_packs = _extract_pack_colours()
        self.assertTrue(
            colour_packs.issuperset(model_packs),
            f"pack_colours is not a superset of model packs.\n"
            f"  model packs : {sorted(model_packs)}\n"
            f"  colour packs: {sorted(colour_packs)}\n"
            f"  missing     : {sorted(model_packs - colour_packs)}",
        )


class TestSitePyNoHardcodedPackEnumeration(unittest.TestCase):
    """site.py must derive pack count/list from the parsed model, not hardcode it.

    Guards the reader-facing HTML regression: if someone re-hardcodes
    'four specialisation packs' (or 'five specialisation packs') as a literal
    string in the ERD prose, this test fails — the correct form derives from
    entity_model.by_pack() at render time.

    The check is a source-level assertion (no Graphviz needed): it scans
    tools/diagrams/render/site.py for the four known forbidden literal patterns.
    """

    SITE_PY = ROOT / "tools" / "diagrams" / "render" / "site.py"

    # Patterns that indicate a hardcoded pack enumeration in reader-facing prose.
    # These are the exact strings that caused the P-MAJ-NEW-1 finding.
    FORBIDDEN_PATTERNS = [
        # The original four-pack literal the cycle-2 audit caught:
        r"four specialisation packs",
        # Guard against a naive 'fix' that just bumps the number:
        r"five specialisation packs",
        # Guard against a hardcoded slug list in the ERD prose line:
        r"private-markets, public-markets, derivatives, real-assets\)",
    ]

    def test_site_py_has_no_hardcoded_pack_enumeration(self) -> None:
        """site.py must not contain a hardcoded exact pack count/slug list."""
        source = self.SITE_PY.read_text(encoding="utf-8")
        violations = []
        for pat in self.FORBIDDEN_PATTERNS:
            if re.search(pat, source):
                violations.append(pat)
        self.assertEqual(
            violations,
            [],
            f"tools/diagrams/render/site.py contains hardcoded pack enumeration(s):\n"
            + "\n".join(f"  pattern: {p!r}" for p in violations)
            + "\n\nThe ERD prose must derive pack count and slug list from "
            "entity_model.by_pack() — see the fix at the _packs_by_model / "
            "_spec_packs derivation block in render_entities_and_erd().",
        )


def _extract_pack_colours() -> set[str]:
    """Read the pack_colours dict from dot_gen by executing entity_erd_dot
    with a minimal stub model and capturing the colour keys from the dict
    as defined in the source — without needing Graphviz.

    Strategy: read the pack_colours dict directly from the dot_gen module
    by introspecting the entity_erd_dot function source.  Since pack_colours
    is a local dict inside the function, we parse it from the source text.
    This is robust as long as the dict keeps the same form (one key per line).
    """
    src = Path(dot_gen.__file__).read_text(encoding="utf-8")
    # Match every quoted string key in the pack_colours dict block.
    # The dict opens with 'pack_colours = {' and closes with '}'.
    m = re.search(
        r'pack_colours\s*=\s*\{([^}]+)\}',
        src,
        re.DOTALL,
    )
    if not m:
        raise AssertionError(
            "Could not locate 'pack_colours' dict in tools/diagrams/render/dot_gen.py. "
            "The guard test expects a dict literal named 'pack_colours' inside "
            "entity_erd_dot(). Check that the function still uses this form."
        )
    keys = re.findall(r'"([^"]+)"\s*:', m.group(1))
    return set(keys)


if __name__ == "__main__":
    unittest.main()
