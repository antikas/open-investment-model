"""Tests for OIM-63 validator checks (the unscanned-count-surface class).

Covers two checks added to tools/openim-validate/validate.py:
  1. check_business_domain_map_subtotals — HARD defect: the Mermaid office
     subgraph subtotals and per-BD node counts in
     model/diagrams/02-business-domain-map.md must agree with the
     filesystem-derived per-BD SD counts, at every level.
  2. check_bd_readme_sd_count — HARD defect: each BD README's
     '**Maturity:**' line "N Service Domains" prose count must match that
     BD's filesystem-derived SD count.

Each check has a POSITIVE test (a clean/synthetic fixture passes) and one or
more NEGATIVE tests (an injected drift IS caught). Negative tests use
in-memory synthetic fixtures — the parsing/comparison logic
(`_parse_bd_map_subtotals`, `_check_bd_map_subtotals_against`,
`_scan_bd_readme_sd_count`) takes text/data in and returns defects out, with
no file I/O — so no mutate-and-restore of the live tree is needed (the
no-mutate-restore lesson, OIM-201).

The negative fixtures reproduce the historical drift shapes named in the
OIM-63 backlog item:
  - cycle-04 ADR-0043 X1 / OIM-61: a per-BD cell sum not matching its office
    subtotal (the middle-office 32-vs-40 mismatch).
  - OIM-60: a BD README Maturity-line SD count out of step with the BD's
    actual SD-file count.

To run:
    python -m pytest tools/openim-validate/tests/test_oim63_checks.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make the tools/ package importable from any working directory.
ROOT = Path(__file__).resolve().parents[3]  # the repo root
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import importlib.util

_VALIDATE_PY = ROOT / "tools" / "openim-validate" / "validate.py"
_spec = importlib.util.spec_from_file_location("_validate", _VALIDATE_PY)
_validate = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_validate)  # type: ignore[union-attr]


def _run_scan(fn, *args, **kwargs):
    """Run a validator scan function with a clean defects/warnings list.

    Returns (defects: list[str], warnings: list[str]).
    """
    orig_defects = _validate.defects[:]
    orig_warnings = _validate.warnings[:]
    _validate.defects.clear()
    _validate.warnings.clear()
    try:
        fn(*args, **kwargs)
        return list(_validate.defects), list(_validate.warnings)
    finally:
        _validate.defects[:] = orig_defects
        _validate.warnings[:] = orig_warnings


# A small, self-consistent synthetic Mermaid fixture — three offices, four
# BDs, all subtotals and cells agreeing. Mirrors the real file's shape
# (subgraph NAME["Label — N SDs"] ... BDNN["... <br/>N SDs"] ... end) without
# depending on the live tree's actual counts.
_CLEAN_MERMAID = """
```mermaid
flowchart TB
    subgraph FRONT["Front office — 20 SDs"]
        direction TB
        BD01["BD-01 Alpha<br/>12 SDs"]:::front
        BD02["BD-02 Beta<br/>8 SDs"]:::front
    end

    subgraph MIDDLE["Middle office — 15 SDs"]
        direction TB
        BD03["BD-03 Gamma<br/>15 SDs"]:::middle
    end

    subgraph BACK["Back office — 5 SDs"]
        direction TB
        BD04["BD-04 Delta<br/>5 SDs"]:::back
    end
```
"""

_CLEAN_COUNTS = {1: 12, 2: 8, 3: 15, 4: 5}  # total = 40


class TestBusinessDomainMapSubtotals(unittest.TestCase):
    """check_business_domain_map_subtotals: office subtotal / per-BD-cell / grand-total agreement."""

    def test_parses_office_blocks_correctly(self) -> None:
        offices = _validate._parse_bd_map_subtotals(_CLEAN_MERMAID)
        self.assertEqual(len(offices), 3)
        by_name = {o["name"]: o for o in offices}
        self.assertEqual(by_name["FRONT"]["subtotal"], 20)
        self.assertEqual(by_name["FRONT"]["bd_cells"], {1: 12, 2: 8})
        self.assertEqual(by_name["MIDDLE"]["subtotal"], 15)
        self.assertEqual(by_name["MIDDLE"]["bd_cells"], {3: 15})
        self.assertEqual(by_name["BACK"]["subtotal"], 5)
        self.assertEqual(by_name["BACK"]["bd_cells"], {4: 5})

    def test_positive_clean_fixture_produces_no_defect(self) -> None:
        """A self-consistent fixture (cells sum to subtotals, subtotals sum
        to the derived total, every BD present) produces zero defects."""
        offices = _validate._parse_bd_map_subtotals(_CLEAN_MERMAID)
        defects, _warnings = _run_scan(
            _validate._check_bd_map_subtotals_against,
            offices, _CLEAN_COUNTS, "test-fixture.md",
        )
        self.assertEqual(defects, [], f"Unexpected defects: {defects}")

    def test_negative_subtotal_not_sum_of_cells_is_caught(self) -> None:
        """cycle-04 ADR-0043 X1 / OIM-61 shape: an office subtotal that does
        NOT equal the sum of its per-BD cells (the middle-office 32-vs-40
        mismatch) IS caught."""
        stale_mermaid = _CLEAN_MERMAID.replace(
            'subgraph MIDDLE["Middle office — 15 SDs"]',
            'subgraph MIDDLE["Middle office — 11 SDs"]',  # stale: cells sum to 15
        )
        offices = _validate._parse_bd_map_subtotals(stale_mermaid)
        defects, _warnings = _run_scan(
            _validate._check_bd_map_subtotals_against,
            offices, _CLEAN_COUNTS, "test-fixture.md",
        )
        self.assertTrue(
            any("MIDDLE" in d and "11" in d and "15" in d for d in defects),
            f"Expected a defect about MIDDLE subtotal 11 vs cell-sum 15; got: {defects}",
        )

    def test_negative_per_bd_cell_stale_against_filesystem_is_caught(self) -> None:
        """A per-BD node's declared SD count out of step with the
        filesystem-derived count for that BD IS caught (independent of
        whether the office subtotal itself still reconciles internally)."""
        stale_mermaid = _CLEAN_MERMAID.replace(
            'BD03["BD-03 Gamma<br/>15 SDs"]:::middle',
            'BD03["BD-03 Gamma<br/>13 SDs"]:::middle',
        ).replace(
            'subgraph MIDDLE["Middle office — 15 SDs"]',
            'subgraph MIDDLE["Middle office — 13 SDs"]',  # keep internal sum consistent
        )
        offices = _validate._parse_bd_map_subtotals(stale_mermaid)
        defects, _warnings = _run_scan(
            _validate._check_bd_map_subtotals_against,
            offices, _CLEAN_COUNTS, "test-fixture.md",  # counts[3] == 15
        )
        self.assertTrue(
            any("BD-03" in d and "13" in d and "15" in d for d in defects),
            f"Expected a defect about BD-03 declaring 13 vs actual 15; got: {defects}",
        )

    def test_negative_office_subtotals_not_summing_to_grand_total_is_caught(self) -> None:
        """The six (here: three) office subtotals must sum to the derived
        repo-wide SD total; a mismatch IS caught even when every individual
        office reconciles internally."""
        counts_with_extra_bd = dict(_CLEAN_COUNTS)
        counts_with_extra_bd[5] = 3  # a BD the fixture's offices never mention
        offices = _validate._parse_bd_map_subtotals(_CLEAN_MERMAID)
        defects, _warnings = _run_scan(
            _validate._check_bd_map_subtotals_against,
            offices, counts_with_extra_bd, "test-fixture.md",
        )
        self.assertTrue(
            any("subtotals sum to 40" in d and "43" in d for d in defects),
            f"Expected a defect about subtotals (40) vs derived total (43); got: {defects}",
        )
        self.assertTrue(
            any("BD-05" in d and "not represented" in d for d in defects),
            f"Expected a defect about BD-05 missing from every office subgraph; got: {defects}",
        )

    def test_negative_bd_missing_from_diagram_is_caught(self) -> None:
        """A BD present in the filesystem-derived counts but absent from
        every office subgraph IS caught (a diagram gap, not just a bad
        count)."""
        counts_with_extra_bd = dict(_CLEAN_COUNTS)
        counts_with_extra_bd[5] = 0  # present in counts, absent from the diagram
        offices = _validate._parse_bd_map_subtotals(_CLEAN_MERMAID)
        defects, _warnings = _run_scan(
            _validate._check_bd_map_subtotals_against,
            offices, counts_with_extra_bd, "test-fixture.md",
        )
        self.assertTrue(
            any("BD-05" in d and "not represented" in d for d in defects),
            f"Expected a defect about BD-05 not represented; got: {defects}",
        )

    def test_positive_live_tree_produces_no_defects(self) -> None:
        """The live model tree's 02-business-domain-map.md produces 0
        defects against the live filesystem-derived per-BD counts."""
        counts = _validate.check_business_domains()
        # check_business_domains() itself may append defects for unrelated
        # reasons; isolate just the subtotal check's own defects.
        orig_defects = _validate.defects[:]
        orig_warnings = _validate.warnings[:]
        _validate.defects.clear()
        _validate.warnings.clear()
        try:
            _validate.check_business_domain_map_subtotals(counts)
            self.assertEqual(
                _validate.defects, [],
                f"check_business_domain_map_subtotals produced defects on the "
                f"live tree: {_validate.defects}",
            )
        finally:
            _validate.defects[:] = orig_defects
            _validate.warnings[:] = orig_warnings


class TestBdReadmeSdCount(unittest.TestCase):
    """check_bd_readme_sd_count: BD README Maturity-line SD-count agreement."""

    def test_positive_matching_count_produces_no_defect(self) -> None:
        text = (
            "# BD-10 Investment Compliance & Guideline Monitoring\n\n"
            "**Maturity:** Provisional · 9 Service Domains for the coded-rule "
            "library, pre- and post-trade monitoring.\n"
        )
        defects, _warnings = _run_scan(
            _validate._scan_bd_readme_sd_count,
            text, "model/service-domains/BD-10.../README.md", 10, {10: 9},
        )
        self.assertEqual(defects, [], f"Unexpected defects: {defects}")

    def test_negative_stale_count_is_caught(self) -> None:
        """OIM-60 shape: the Maturity-line SD count is stale against the
        BD's actual (filesystem-derived) SD-file count. IS caught."""
        text = (
            "# BD-10 Investment Compliance & Guideline Monitoring\n\n"
            "**Maturity:** Provisional · 8 Service Domains for the coded-rule "
            "library, pre- and post-trade monitoring.\n"
        )
        defects, _warnings = _run_scan(
            _validate._scan_bd_readme_sd_count,
            text, "model/service-domains/BD-10.../README.md", 10, {10: 9},
        )
        self.assertTrue(
            any("8 Service Domain" in d and "9 SD file" in d for d in defects),
            f"Expected a defect about 8 vs 9 Service Domains; got: {defects}",
        )

    def test_negative_missing_maturity_count_is_caught(self) -> None:
        """A README whose Maturity line carries no 'N Service Domains'
        token at all is itself a defect (silent drift into an
        unparseable form is not a pass)."""
        text = "# BD-99 Test\n\n**Maturity:** Provisional · handles things.\n"
        defects, _warnings = _run_scan(
            _validate._scan_bd_readme_sd_count,
            text, "model/service-domains/BD-99.../README.md", 99, {99: 5},
        )
        self.assertTrue(
            any("does not state" in d for d in defects),
            f"Expected a defect about the missing SD-count token; got: {defects}",
        )

    def test_positive_live_tree_produces_no_defects(self) -> None:
        """Every live BD README's Maturity line agrees with the
        filesystem-derived SD count for that BD."""
        counts = _validate.check_business_domains()
        orig_defects = _validate.defects[:]
        orig_warnings = _validate.warnings[:]
        _validate.defects.clear()
        _validate.warnings.clear()
        try:
            _validate.check_bd_readme_sd_count(counts)
            self.assertEqual(
                _validate.defects, [],
                f"check_bd_readme_sd_count produced defects on the live tree: "
                f"{_validate.defects}",
            )
        finally:
            _validate.defects[:] = orig_defects
            _validate.warnings[:] = orig_warnings


if __name__ == "__main__":
    unittest.main()
