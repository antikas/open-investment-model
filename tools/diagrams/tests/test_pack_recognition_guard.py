"""Mechanical guard — pack-recognition completeness across tools/.

Background.  A recurring class-walk-not-instance-grep defect (reproduced in
OIM-201 cycles 1, 2 and 3) came from the pack list being hardcoded independently
in multiple consumers: adding a pack meant remembering every copy.  OIM-201
cycle-3 installed a stopgap guard here that asserted against the literal
`pack_colours` dict in dot_gen and a hardcoded slug list in site.py.

OIM-211 removed the underlying duplication: there is now one pack-registry SSOT
at tools/pack_registry.py, and every consumer imports it.  With a single source
there is no second copy to drift, so the old literal-parsing assertions are
obsolete.  This test is kept as a belt-and-braces regression check, re-pointed
at the SSOT:

1. The registry (`pack_registry.PACK_COLOURS`) covers every pack the parsed
   entity model knows about.  Adding a pack directory without adding its row to
   `PACKS` fails here — one edit, one place, enforced.

2. The diagram renderer is actually wired to the registry (dot_gen consumes
   `pack_registry.PACK_COLOURS`, not a private copy), and every pack present in
   the model renders with the registry's colour.

3. site.py still derives its ERD prose from the parsed model, never a hardcoded
   pack count / slug list.

All assertions run against the LIVE entity model and the LIVE render-stage
source.  No Graphviz binary is required — the test only imports Python modules
and reads source text.

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

import pack_registry
from diagrams.parser import parse_entities
from diagrams.render import dot_gen


class TestRegistryCoversModelPacks(unittest.TestCase):
    """pack_registry.PACK_COLOURS must cover every pack the entity model knows.

    Guards P-MAJ-NEW-1 / the class-walk-not-instance-grep class: adding a new
    specialisation pack directory without adding its row to pack_registry.PACKS
    now fails the test suite rather than silently rendering the new pack in
    default grey.  With the registry as the single source, this is the ONE place
    that has to stay in step with the model.
    """

    def test_registry_covers_all_model_packs(self) -> None:
        """set(pack_registry.PACK_COLOURS) ⊇ set(entity_model.by_pack())."""
        em = parse_entities(ROOT)
        model_packs = set(em.by_pack().keys())
        registry_packs = set(pack_registry.PACK_COLOURS.keys())
        missing = model_packs - registry_packs
        self.assertEqual(
            missing,
            set(),
            f"pack_registry.PACK_COLOURS is missing entries for pack(s): "
            f"{sorted(missing)}. Add the pack's row to PACKS in "
            f"tools/pack_registry.py — the single source every consumer reads.",
        )


class TestRendererWiredToRegistry(unittest.TestCase):
    """dot_gen must consume the registry, not keep a private colour copy."""

    def test_dot_gen_uses_registry_palette(self) -> None:
        """dot_gen references pack_registry.PACK_COLOURS (no re-hardcoded dict)."""
        src = Path(dot_gen.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "pack_registry.PACK_COLOURS",
            src,
            "tools/diagrams/render/dot_gen.py must read the pack palette from "
            "pack_registry.PACK_COLOURS (OIM-211 SSOT), not a local dict.",
        )
        # Guard against a re-introduced private literal copy of the palette.
        self.assertNotRegex(
            src,
            r"pack_colours\s*=\s*\{",
            "dot_gen.py re-introduced a literal 'pack_colours = {...}' dict — "
            "the palette must come from pack_registry.PACK_COLOURS.",
        )

    def test_erd_renders_registry_colours(self) -> None:
        """Every pack present in the model renders with the registry's colour."""
        em = parse_entities(ROOT)
        dot = dot_gen.entity_erd_dot(em)
        for pack in em.by_pack():
            fill, stroke = pack_registry.PACK_COLOURS[pack]
            self.assertIn(
                fill, dot,
                f"pack {pack!r} fill colour {fill} not found in ERD DOT output",
            )
            self.assertIn(
                stroke, dot,
                f"pack {pack!r} stroke colour {stroke} not found in ERD DOT output",
            )


class TestSitePyNoHardcodedPackEnumeration(unittest.TestCase):
    """site.py must derive pack count/list from the parsed model, not hardcode it.

    Guards the reader-facing HTML regression: if someone re-hardcodes
    'four specialisation packs' (or 'five specialisation packs') as a literal
    string in the ERD prose, this test fails — the correct form derives from
    entity_model.by_pack() at render time.
    """

    SITE_PY = ROOT / "tools" / "diagrams" / "render" / "site.py"

    # Patterns that indicate a hardcoded pack enumeration in reader-facing prose.
    FORBIDDEN_PATTERNS = [
        r"four specialisation packs",
        r"five specialisation packs",
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
            "entity_model.by_pack() — see the _packs_by_model / _spec_packs "
            "derivation block in render_entities_and_erd().",
        )


if __name__ == "__main__":
    unittest.main()
