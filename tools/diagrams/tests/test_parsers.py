"""Golden-output tests for the OpenIM Hybrid D generator parsers.

Each test exercises one of the seven shapes named in OIM-54 brief criterion (n):

1. a sample BD README
2. a sample SD file with SOs
3. a sample SD file without SOs (here: with a single placeholder operation)
4. a core entity file, single-owner
5. a specialisation entity file
6. a co-owned entity file
7. an ownership-map fragment

Plus negative tests confirming the strict-parser contract (unknown
markdown shapes raise ParseError, not silent skips).

Run:
    python -m pytest tools/diagrams/tests/
    python -m unittest discover tools/diagrams/tests/
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Make the tools/diagrams package importable when tests run from any cwd.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from diagrams.parser import (
    parse_service_domains,
    parse_entities,
    parse_ownership_map,
)
from diagrams.parser.service_domains import (
    _parse_bd_readme,
    _parse_sd_file,
    validate_cross_refs,
)
from diagrams.parser.entities import (
    _parse_entity_file,
    validate_entity_references,
    validate_entity_sd_references,
)
from diagrams.parser.errors import ParseError


FIXT = Path(__file__).parent / "fixtures"


def _temp_repo(tmp: Path) -> Path:
    """Lay the fixtures out into a tmp dir mirroring the real repo shape."""
    sd_dir = tmp / "model" / "service-domains"
    sd_dir.mkdir(parents=True)
    bd_dir = sd_dir / "BD-99-sample"
    bd_dir.mkdir()
    shutil.copy(FIXT / "bd_sample" / "README.md", bd_dir / "README.md")
    shutil.copy(FIXT / "bd_sample" / "SD-99.1-sample-with-sos.md", bd_dir)
    shutil.copy(FIXT / "bd_sample" / "SD-99.2-sample-without-sos.md", bd_dir)

    ent_dir = tmp / "model" / "entities"
    (ent_dir / "core").mkdir(parents=True)
    for p in (FIXT / "entities" / "core").glob("*.md"):
        shutil.copy(p, ent_dir / "core" / p.name)
    (ent_dir / "specialisations" / "private-markets").mkdir(parents=True)
    for p in (FIXT / "entities" / "specialisations" / "private-markets").glob("*.md"):
        shutil.copy(p, ent_dir / "specialisations" / "private-markets" / p.name)

    shutil.copy(FIXT / "ownership-map.md", tmp / "model" / "ownership-map.md")
    return tmp


class TestBDReadme(unittest.TestCase):
    """Shape 1 — a sample BD README parses to id, name, office."""

    def test_parses_bd_readme(self) -> None:
        bd = _parse_bd_readme(FIXT / "bd_sample" / "README.md")
        self.assertEqual(bd.id, "BD-99")
        self.assertEqual(bd.num, 99)
        self.assertEqual(bd.name, "Sample Business Domain")
        self.assertEqual(bd.office, "Front")


class TestSDWithSOs(unittest.TestCase):
    """Shape 2 — an SD file with Service Operations + structured Consumes."""

    def test_parses_sd_with_sos(self) -> None:
        sd = _parse_sd_file(
            FIXT / "bd_sample" / "SD-99.1-sample-with-sos.md", 99, 1,
        )
        self.assertEqual(sd.id, "SD-99.1")
        self.assertEqual(sd.name, "Sample With Service Operations")
        self.assertEqual(sd.applies, "BOTH")
        self.assertEqual([o.name for o in sd.operations],
                         ["Operation alpha", "Operation beta", "Operation gamma"])
        self.assertEqual(sd.consumes_entities, ["E-09"])
        self.assertEqual(sd.owns_entities, ["E-99"])
        self.assertIn("SD-99.2", sd.upstream_sds)


class TestSDWithoutSOs(unittest.TestCase):
    """Shape 3 — an SD file with a minimal SO list and no Inputs/outputs section."""

    def test_parses_sd_minimal(self) -> None:
        sd = _parse_sd_file(
            FIXT / "bd_sample" / "SD-99.2-sample-without-sos.md", 99, 2,
        )
        self.assertEqual(sd.id, "SD-99.2")
        self.assertEqual(sd.applies, "PUB")
        self.assertEqual(len(sd.operations), 1)
        self.assertEqual(sd.operations[0].name, "Placeholder operation only")
        self.assertEqual(sd.consumes_entities, [])
        self.assertEqual(sd.owns_entities, [])
        self.assertEqual(sd.upstream_sds, set())


class TestCoreEntity(unittest.TestCase):
    """Shape 4 — a core entity, single-owner, with one FK target."""

    def test_parses_core_single_owner(self) -> None:
        ent = _parse_entity_file(
            FIXT / "entities" / "core" / "E-99-sample-core.md", "E", 99,
        )
        self.assertEqual(ent.id, "E-99")
        self.assertEqual(ent.prefix, "E")
        self.assertEqual(ent.name, "Sample Core Entity")
        self.assertEqual(ent.pack, "core")
        self.assertEqual(ent.owned_by, ["SD-99.1"])
        self.assertEqual(ent.consumed_by, ["SD-99.2"])
        self.assertEqual(ent.fk_targets, ["E-09"])
        self.assertIsNone(ent.specialises)


class TestSpecialisationEntity(unittest.TestCase):
    """Shape 5 — a specialisation entity that declares Specialises + has FK."""

    def test_parses_specialisation_entity(self) -> None:
        ent = _parse_entity_file(
            FIXT / "entities" / "specialisations" / "private-markets" /
            "PM-99-sample-specialisation.md",
            "PM", 99,
        )
        self.assertEqual(ent.id, "PM-99")
        self.assertEqual(ent.prefix, "PM")
        self.assertEqual(ent.pack, "private-markets")
        self.assertEqual(ent.specialises, "E-99")
        self.assertEqual(ent.fk_targets, ["E-99"])
        self.assertEqual(ent.owned_by, ["SD-99.2"])
        self.assertEqual(ent.consumed_by, ["SD-99.1"])


class TestCoOwnedEntity(unittest.TestCase):
    """Shape 6 — a co-owned entity declares two SDs on the Owned by line."""

    def test_parses_co_owned_entity(self) -> None:
        ent = _parse_entity_file(
            FIXT / "entities" / "core" / "E-27-sample-coowned.md", "E", 27,
        )
        self.assertEqual(ent.id, "E-27")
        self.assertEqual(ent.owned_by, ["SD-99.1", "SD-99.2"])
        self.assertEqual(ent.consumed_by, ["SD-99.1"])
        self.assertEqual(ent.specialises, "E-09")


class TestOwnershipMap(unittest.TestCase):
    """Shape 7 — an ownership-map fragment parses to per-entity records."""

    def test_parses_ownership_map(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "model").mkdir()
            shutil.copy(FIXT / "ownership-map.md", tmp / "model" / "ownership-map.md")
            om = parse_ownership_map(tmp)
        self.assertEqual(len(om.records), 4)
        self.assertEqual(om.get("E-09").owners, ["SD-99.1"])
        self.assertEqual(om.get("E-09").pattern, "Single owner")
        coowned = om.get("E-27")
        self.assertEqual(sorted(coowned.owners), ["SD-99.1", "SD-99.2"])
        self.assertEqual(coowned.pattern, "Co-owned")
        self.assertEqual(om.get("PM-99").owners, ["SD-99.2"])


class TestEndToEnd(unittest.TestCase):
    """The seven fixtures parse cleanly through the full pipeline."""

    def test_full_parse(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = _temp_repo(Path(td))
            sdm = parse_service_domains(repo)
            self.assertEqual(len(sdm.business_domains), 1)
            self.assertEqual(len(sdm.all_sds()), 2)
            validate_cross_refs(sdm)
            em = parse_entities(repo)
            self.assertEqual(len(em.entities), 4)
            validate_entity_references(em)
            validate_entity_sd_references(em, {sd.id for sd in sdm.all_sds()})


class TestStrictParser(unittest.TestCase):
    """Negative tests — unknown markdown shapes raise ParseError."""

    def test_missing_applies_tag_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "SD-99.9-broken.md"
            p.write_text(
                "# SD-99.9 — Broken\n\n## Purpose\n\nNo Applies line.\n\n"
                "## Service Operations\n\n- thing\n\n## Entities\n\n- foo\n\n## Standards\n\n- bar\n",
                encoding="utf-8",
            )
            with self.assertRaises(ParseError) as ctx:
                _parse_sd_file(p, 99, 9)
            self.assertIn("Applies", str(ctx.exception))

    def test_prose_under_operations_is_skipped(self) -> None:
        """Prose paragraphs and bold group headers under '## Service
        Operations' are reader content (the SD-12.11 shape) — the parser
        skips them and still collects every bullet as an operation."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "SD-99.8-grouped.md"
            p.write_text(
                "# SD-99.8 — Grouped\n\n**Applies:** BOTH\n\n## Purpose\n\nx\n\n"
                "## Service Operations\n\n"
                "The general capability runs across every form of holding.\n\n"
                "**The general capability — all forms of holding:**\n\n"
                "- **First op** — does the first thing.\n\n"
                "**The private-markets specialisation:**\n\n"
                "- **Second op** — does the second thing.\n\n"
                "## Entities\n\n- foo\n\n## Standards\n\n- bar\n",
                encoding="utf-8",
            )
            sd = _parse_sd_file(p, 99, 8)
            self.assertEqual([op.name for op in sd.operations],
                             ["First op", "Second op"])

    def test_unknown_h2_raises(self) -> None:
        """OIM-54 cycle-2 A-1 — an unknown H2 heading raises ParseError.

        Closes the strict-parser false-integrity claim: the README, ADR-0045
        §1, and cycle-1 brief criterion (c) all claimed strictness; the
        parser's `_extract_section` returned None for unknown headings,
        treating them as benign. This test asserts the strict-mode fix.
        """
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "SD-99.7-bogus.md"
            p.write_text(
                "# SD-99.7 — With Bogus H2\n\n**Applies:** BOTH\n\n"
                "## Purpose\n\nx\n\n"
                "## Service Operations\n\n- a thing\n\n"
                "## Entities\n\n- **Consumes:** none.\n- **Owns:** none.\n\n"
                "## Totally Made Up Section\n\nstuff\n",
                encoding="utf-8",
            )
            with self.assertRaises(ParseError) as ctx:
                _parse_sd_file(p, 99, 7)
            self.assertIn("Totally Made Up Section", str(ctx.exception))


class TestSubstantiveCoverage(unittest.TestCase):
    """OIM-54 cycle-2 A-2 / A-3 — substantive coverage beyond filenames.

    The validator's `check_diagram_render_coverage` and the generator's
    `_substantive_coverage_gaps` check that each SD page contains its
    declared Service Operations, each entity page contains its FK
    drill-downs, each BD page contains its member-SD drill-downs, and
    the landscape contains every BD reference. This test exercises the
    SO-coverage leg: an SD page hand-edited to drop one operation must
    produce a substantive-coverage defect.
    """

    def test_so_coverage_gap_detected(self) -> None:
        import shutil
        from diagrams.build import (
            _substantive_coverage_gaps, _expected_files,
        )
        with tempfile.TemporaryDirectory() as td:
            repo = _temp_repo(Path(td))
            sdm = parse_service_domains(repo)
            em = parse_entities(repo)
            # Hand-build a dist/ that mimics the generator's output shape but
            # deliberately omits an SO from the SD-99.1 page.
            out = repo / "dist"
            out.mkdir()
            # The fixture SD-99.1 has three operations: alpha / beta / gamma.
            # Render an SD page that lists only alpha and beta — gamma must
            # be flagged as a missing-SO defect.
            (out / "sd-99.1.html").write_text(
                "<html><body>"
                "<h2>SD-99.1 — Sample With Service Operations</h2>"
                "<ul><li>Operation alpha</li><li>Operation beta</li></ul>"
                "</body></html>",
                encoding="utf-8",
            )
            # Render the other expected pages with stub content so filename
            # coverage doesn't blow up first.
            for name in _expected_files(sdm, em) - {"sd-99.1.html"}:
                (out / name).write_text(
                    "<html><body>stub</body></html>", encoding="utf-8",
                )
            gaps = _substantive_coverage_gaps(out, sdm, em)
            # The check should flag 'Operation gamma' as missing from sd-99.1.
            so_gaps = [g for g in gaps if "Operation gamma" in g]
            self.assertTrue(
                so_gaps,
                f"expected substantive-coverage gap for 'Operation gamma'; "
                f"got {gaps}",
            )


class TestBDNarrativeEdgeStyle(unittest.TestCase):
    """OIM-54 cycle-3 B-1 (P2-3 closure) — narrative-bd-* edges render
    with a distinct Graphviz style from structured / SD-narrative edges.

    The cycle-2 B-4 fix replaced BD fan-out (one edge per member SD per
    narrative BD reference) with a single aggregate edge from the BD
    landing node, carrying the new `narrative-bd-input` /
    `narrative-bd-output` edge kind. The cycle-2 P2-3 audit caught that
    the renderer never inspected `edge.kind` — the data half landed but
    the visual half did not. This test asserts the renderer now branches:
    the BD-narrative aggregate edges render dashed + gray + thinner; the
    structured / SD-narrative cross-BD edges render solid (the default).
    """

    def test_landscape_renders_distinct_bd_narrative_style(self) -> None:
        from diagrams.parser.service_domains import (
            BusinessDomain, ServiceDomain, ServiceDomainModel,
        )
        from diagrams.parser.entities import EntityModel
        from diagrams.graph.build import CapabilityEdge, GraphBundle
        from diagrams.render.dot_gen import landscape_dot

        # Two-BD synthetic model. BD-01 / BD-02 each carry one SD.
        # Use real dataclass field names (bd_num / sd_num / path; computed
        # bd_id property).
        dummy = Path(".")
        sd_01_1 = ServiceDomain(
            id="SD-01.1", bd_num=1, sd_num=1, name="Alpha Service",
            applies="BOTH", path=dummy,
        )
        sd_02_1 = ServiceDomain(
            id="SD-02.1", bd_num=2, sd_num=1, name="Beta Service",
            applies="BOTH", path=dummy,
        )
        bd1 = BusinessDomain(
            id="BD-01", num=1, slug="alpha", name="Alpha", office="Front",
            path=dummy, service_domains=[sd_01_1],
        )
        bd2 = BusinessDomain(
            id="BD-02", num=2, slug="beta", name="Beta", office="Middle",
            path=dummy, service_domains=[sd_02_1],
        )
        sdm = ServiceDomainModel(business_domains=[bd1, bd2])
        em = EntityModel(entities=[])
        # One pure BD-narrative pair (BD-01 -> BD-02) and one structured
        # pair (BD-02 -> BD-01) — landscape must render these distinctly.
        edges = [
            CapabilityEdge(source="BD-01", target="SD-02.1",
                           kind="narrative-bd-input"),
            CapabilityEdge(source="SD-02.1", target="SD-01.1",
                           kind="consumes-sd"),
        ]
        bundle = GraphBundle(sd_model=sdm, entity_model=em, edges=edges)

        dot = landscape_dot(sdm, bundle)
        # Find the cross-BD edge lines (not the subgraph-internal node lines).
        bd_aggregate_line = None
        structured_line = None
        for line in dot.splitlines():
            s = line.strip()
            if "bd_01 -> bd_02" in s:
                bd_aggregate_line = s
            elif "bd_02 -> bd_01" in s:
                structured_line = s
        self.assertIsNotNone(
            bd_aggregate_line,
            f"expected BD-01 -> BD-02 edge in landscape DOT; got:\n{dot}",
        )
        self.assertIsNotNone(
            structured_line,
            f"expected BD-02 -> BD-01 edge in landscape DOT; got:\n{dot}",
        )
        # The BD-narrative-only pair must carry the dashed + gray style.
        self.assertIn("dashed", bd_aggregate_line)
        self.assertIn("#808080", bd_aggregate_line)
        # The structured pair must be plain (no dashed style attribute).
        self.assertNotIn("dashed", structured_line)
        self.assertNotIn("#808080", structured_line)


class TestStructuralCoverage(unittest.TestCase):
    """OIM-54 cycle-3 E-1 (P2-2 closure) — substantive-coverage check uses
    structural matching, not substring matching, for SO list items on SD
    pages.

    The cycle-2 P2-2 audit caught that the existing check used
    `escaped not in page` substring matching, so an SO name typo'd in
    source (and consequently rendered with the same typo) would still
    substring-match itself; or an SO name appearing elsewhere on the
    page (a heading, a cross-reference) would mask an empty operations
    list. The cycle-3 fix anchors the check to the `<ul>` / `<li>`
    structure under the `Service Operations` heading.
    """

    def test_typoed_so_name_fails_structural_check(self) -> None:
        """An SD page that puts a typo'd SO name into the ops list (and
        also carries the correct name in unrelated prose) fails the
        structural check — the substring check would have passed."""
        import tempfile
        from pathlib import Path as _P
        from diagrams.build import (
            _substantive_coverage_gaps, _expected_files,
        )
        with tempfile.TemporaryDirectory() as td:
            repo = _temp_repo(_P(td))
            sdm = parse_service_domains(repo)
            em = parse_entities(repo)
            out = repo / "dist"
            out.mkdir()
            # The fixture SD-99.1 declares three operations: alpha / beta
            # / gamma. Render an SD page where the ops list contains a
            # typo'd 'Operation gama' (missing the second 'm') but the
            # prose body mentions all three legitimate operation names
            # (alpha / beta / gamma). Substring matching would PASS
            # ("Operation gamma" appears in the body prose). Structural
            # matching must FAIL — "Operation gamma" is not a <li>.
            (out / "sd-99.1.html").write_text(
                "<html><body>"
                "<h2>SD-99.1 — Sample With Service Operations</h2>"
                "<h3>Service Operations</h3>"
                "<ul>"
                "<li>Operation alpha</li>"
                "<li>Operation beta</li>"
                "<li>Operation gama</li>"  # the typo
                "</ul>"
                "<h3>Cross-reference</h3>"
                "<p>This SD pairs with Operation gamma elsewhere "
                "in the model.</p>"
                "</body></html>",
                encoding="utf-8",
            )
            for name in _expected_files(sdm, em) - {"sd-99.1.html"}:
                (out / name).write_text(
                    "<html><body>stub</body></html>", encoding="utf-8",
                )
            gaps = _substantive_coverage_gaps(out, sdm, em)
            so_gaps = [g for g in gaps if "Operation gamma" in g]
            self.assertTrue(
                so_gaps,
                f"expected structural-coverage gap for 'Operation gamma' "
                f"(typo'd in list, mentioned in prose); got {gaps}",
            )


if __name__ == "__main__":
    unittest.main()
