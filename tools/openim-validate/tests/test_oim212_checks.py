"""Tests for OIM-212 validator checks (ADR-0067).

Covers three checks added to tools/openim-validate/validate.py:
  1. check_count_surface_agreement  — HARD defect (count-surface agreement)
  2. check_two_sided_edges          — WARNING (entity↔SD bidirectional edges)
  3. check_deferral_language        — advisory WARNING

Each hard check has a POSITIVE test (clean tree passes) and a NEGATIVE test
(injected defect is genuinely caught).  Negative tests use isolated in-memory
fixtures, NOT mutate-and-restore of the live tree — the no-mutate-restore
lesson (OIM-201).

The negative fixtures are designed to capture the historical defect shapes:
  - OIM-204: one-sided edge (entity says Consumed by SD-X, SD-X Consumes
    nothing back) + d2 count token out of step.
  - OIM-206: d2 count token out of step (same class as OIM-204).
  - OIM-207: entities/INDEX.md Pack-sizes prose paragraph with wrong count +
    SD-13.2 one-sided edge mislabel.

To run:
    python -m pytest tools/openim-validate/tests/test_oim212_checks.py
    python -m unittest tools.openim-validate.tests.test_oim212_checks
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from typing import NamedTuple

# Make the tools/ package importable from any working directory.
ROOT = Path(__file__).resolve().parents[3]  # the repo root
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

# ---------------------------------------------------------------------------
# Import the validator module under test.
# ---------------------------------------------------------------------------
import importlib.util

_VALIDATE_PY = ROOT / "tools" / "openim-validate" / "validate.py"
_spec = importlib.util.spec_from_file_location("_validate", _VALIDATE_PY)
_validate = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_validate)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Helpers — thin wrappers that run a check in isolation and collect output.
# ---------------------------------------------------------------------------

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
        # Restore the module-level lists so other tests start clean.
        _validate.defects[:] = orig_defects
        _validate.warnings[:] = orig_warnings


# ---------------------------------------------------------------------------
# Fake entity / SD model stubs for isolated in-memory testing.
# ---------------------------------------------------------------------------

class _FakeEntity:
    """Minimal entity stub matching the interface used by the checks."""

    def __init__(self, eid: str, consumed_by: list[str]):
        self.id = eid
        self.consumed_by = consumed_by


class _FakeSD:
    """Minimal SD stub matching the interface used by the checks."""

    def __init__(self, sid: str, consumes: list[str]):
        self.id = sid
        self.consumes_entities = consumes


class _FakeEntityModel:
    """Minimal EntityModel stub."""

    def __init__(self, entities: list[_FakeEntity]):
        self.entities = entities

    def by_pack(self) -> dict[str, list]:
        # One core entity and one per pack for simplicity.
        return {"core": [e for e in self.entities if e.id.startswith("E-")]}


class _FakeEntityModelWithPacks:
    """EntityModel stub with per-pack counts for count-surface tests."""

    def __init__(
        self,
        core_count: int = 38,
        pack_counts: dict | None = None,
    ):
        if pack_counts is None:
            pack_counts = {
                "public-markets": 11,
                "fund-operations": 9,
                "private-markets": 14,
                "derivatives": 5,
                "real-assets": 5,
            }
        # Build fake entity lists.
        core = [_FakeEntity(f"E-{i:02d}", []) for i in range(1, core_count + 1)]
        by_pack: dict[str, list] = {"core": core}
        for pack_name, count in pack_counts.items():
            prefix = {
                "public-markets": "PB",
                "fund-operations": "FO",
                "private-markets": "PM",
                "derivatives": "DR",
                "real-assets": "RA",
            }[pack_name]
            by_pack[pack_name] = [
                _FakeEntity(f"{prefix}-{i:02d}", [])
                for i in range(1, count + 1)
            ]
        self._by_pack = by_pack
        self.entities = [e for ents in by_pack.values() for e in ents]

    def by_pack(self) -> dict[str, list]:
        return self._by_pack


class _FakeSDModel:
    """Minimal ServiceDomainModel stub."""

    def __init__(self, sds: list[_FakeSD]):
        self._sds = sds

    def all_sds(self) -> list[_FakeSD]:
        return self._sds


# ---------------------------------------------------------------------------
# 1. check_count_surface_agreement
# ---------------------------------------------------------------------------

class TestCountSurfaceAgreement(unittest.TestCase):
    """HARD defect check: entity count tokens must agree with the derived counts.

    POSITIVE: A text with correct counts produces no defects.
    NEGATIVE (OIM-204/206 shape): A d2 label with a stale count IS caught.
    NEGATIVE (OIM-207 shape): The Pack-sizes prose paragraph with a wrong
    per-pack count IS caught.
    """

    def _derived_counts(self, em) -> dict:
        return _validate._derive_entity_counts(em)

    def test_positive_correct_counts_produce_no_defect(self) -> None:
        """A text with accurate current-state counts produces 0 defects."""
        em = _FakeEntityModelWithPacks()
        counts = self._derived_counts(em)
        # total = 38 + 11 + 9 + 14 + 5 + 5 = 82; core = 38; spec = 44
        self.assertEqual(counts["total"], 82)
        self.assertEqual(counts["core"], 38)
        self.assertEqual(counts["total_spec"], 44)

        # Text matching the canonical layer-stack.d2 / README.md phrasings.
        clean_text = (
            "82 entities (38 core + 5 specialisation packs)\n"
            "generalised core of 38\n"
            "with the 38 core entities, the OpenIM entity model is **82 entities**.\n"
            "**44 specialisation entities** across the five (11 + 9 + 14 + 5 + 5)\n"
            "public-markets 11, fund-operations 9, private-markets 14, "
            "derivatives 5, real-assets 5\n"
        )
        defects, _warnings = _run_scan(
            _validate._scan_entity_count_tokens, clean_text, "test-surface.md", counts
        )
        self.assertEqual(defects, [], f"Unexpected defects: {defects}")

    def test_negative_d2_entity_count_stale_is_caught(self) -> None:
        """OIM-204 / OIM-206 shape: a stale d2 'NN entities' token IS caught.

        The historical d2/layer-stack.d2 blind spot (M1 root cause): the d2
        label stores newlines as the literal two-character escape backslash+n,
        so the on-disk bytes are '...\\n81 entities...' — the character before
        '81' is the letter 'n', which prevented the \\b word-boundary from
        firing and made the total-count token invisible to the check.

        This test builds its fixture from the ACTUAL layer-stack.d2 bytes
        (read file → mutate the total token), so it fails when the real
        surface would.  A Python real-newline fixture would NOT reproduce this
        defect and would yield a false-green test (the M1 pre-mortem finding).
        """
        em = _FakeEntityModelWithPacks()  # total = 82
        counts = self._derived_counts(em)

        # Read the actual d2 file and mutate the total token 86 → 79.
        # This reproduces the exact on-disk bytes the check must scan.
        # The fake model derives total=82; the injected stale token is 79 — the
        # validator must catch the 79 vs 82 mismatch.
        d2_path = ROOT / "model" / "diagrams" / "d2" / "layer-stack.d2"
        if not d2_path.exists():
            self.skipTest("layer-stack.d2 not found — skipping real-bytes d2 negative test")
        real_d2 = d2_path.read_text(encoding="utf-8")

        # The literal backslash-n followed by "86" is the token: r'\n86 entities'
        import re as _re
        stale_d2 = _re.sub(r'\\n86 entities', r'\\n79 entities', real_d2)
        self.assertIn(
            r"\n79 entities",
            stale_d2,
            "Mutation did not produce the expected stale token in d2 fixture",
        )

        defects, _warnings = _run_scan(
            _validate._scan_entity_count_tokens, stale_d2, "model/diagrams/d2/layer-stack.d2", counts
        )
        self.assertTrue(
            any("79" in d and "82" in d for d in defects),
            f"Expected a defect about 79 vs 82 entities from real d2 bytes; got: {defects}",
        )

    def test_negative_pack_sizes_prose_stale_is_caught(self) -> None:
        """OIM-207 shape: a stale Pack-sizes prose paragraph IS caught.

        The historical entities/INDEX.md blind spot: the 'Pack sizes' prose
        paragraph 'public-markets 11, fund-operations 8, ...' was not scanned,
        so a stale per-pack count (e.g. fund-operations 5 before FO-06/07/08
        were added) passed silently.
        """
        em = _FakeEntityModelWithPacks()  # fund-operations = 9
        counts = self._derived_counts(em)

        # Inject the OIM-207 defect shape: fund-operations says 5 instead of 9.
        stale_prose = (
            "five specialisation packs are different sizes — "
            "**public-markets 11, fund-operations 5, private-markets 14, "
            "derivatives 5, real-assets 5**."
        )
        defects, _warnings = _run_scan(
            _validate._scan_entity_count_tokens, stale_prose, "model/entities/INDEX.md", counts
        )
        self.assertTrue(
            any("fund-operations" in d and "5" in d for d in defects),
            f"Expected a defect about fund-operations count 5 vs 9; got: {defects}",
        )

    def test_negative_parenthesised_gloss_stale_is_caught(self) -> None:
        """OIM-207 shape: a stale parenthesised gloss '(11 + 5 + 14 + 5 + 5)' IS caught.

        The gloss form in entities/INDEX.md was the OIM-207 Pack-sizes blind spot.
        The check must catch when any addend in the gloss is wrong.
        """
        em = _FakeEntityModelWithPacks()  # fund-operations = 9
        counts = self._derived_counts(em)

        # Stale gloss: says fund-operations is 5 (the OIM-207 stale value).
        stale_gloss = "across the five (11 + 5 + 14 + 5 + 5); with the 38 core"
        defects, _warnings = _run_scan(
            _validate._scan_entity_count_tokens, stale_gloss, "model/entities/INDEX.md", counts
        )
        self.assertTrue(
            any("5 + 14 + 5 + 5" in d or "gloss" in d for d in defects),
            f"Expected a defect about the stale parenthesised gloss; got: {defects}",
        )

    def test_positive_live_tree_passes(self) -> None:
        """The live model tree produces 0 defects from check_count_surface_agreement.

        This is the POSITIVE test against the actual repo — the check is clean
        after the OIM-212 fixes.
        """
        parser_models = _validate._load_parser_models()
        if parser_models is None:
            self.skipTest("Parser models unavailable — skipping live-tree positive test")
        em, _sdm = parser_models
        orig_defects = _validate.defects[:]
        orig_warnings = _validate.warnings[:]
        _validate.defects.clear()
        _validate.warnings.clear()
        try:
            _validate.check_count_surface_agreement(em)
            self.assertEqual(
                _validate.defects,
                [],
                f"check_count_surface_agreement produced defects on live tree: "
                f"{_validate.defects}",
            )
        finally:
            _validate.defects[:] = orig_defects
            _validate.warnings[:] = orig_warnings


# ---------------------------------------------------------------------------
# 2. check_two_sided_edges
# ---------------------------------------------------------------------------

class TestTwoSidedEdges(unittest.TestCase):
    """HARD DEFECT (ratchet) check: entity↔SD bidirectional edge consistency.

    Grandfathered edges (in the OIM-212 baseline) emit WARNINGs only.
    NEW edges not in the baseline are HARD DEFECTS.

    POSITIVE: A symmetric entity↔SD pair produces no warnings or defects.
    NEGATIVE (OIM-212 gate): a NEW asymmetric edge NOT in the baseline IS a DEFECT.
    NEGATIVE (grandfathered): an edge IN the baseline is a WARNING, not a defect.
    GATE PROOF: a new one-sided edge not in any baseline must be DEFECT.
    """

    def test_positive_symmetric_edge_produces_no_warning(self) -> None:
        """A perfectly symmetric entity↔SD pair produces 0 warnings and 0 defects."""
        entity = _FakeEntity("E-01", consumed_by=["SD-13.2"])
        sd = _FakeSD("SD-13.2", consumes=["E-01"])
        em = _FakeEntityModel([entity])
        sdm = _FakeSDModel([sd])
        defects, warnings = _run_scan(_validate.check_two_sided_edges, em, sdm)
        self.assertEqual(
            [w for w in warnings if "two_sided_edges" in w],
            [],
            f"Unexpected two-sided-edge warnings for symmetric pair: {warnings}",
        )
        self.assertEqual(
            [d for d in defects if "two_sided_edges" in d],
            [],
            f"Unexpected two-sided-edge defects for symmetric pair: {defects}",
        )

    def test_negative_new_edge_not_in_baseline_is_hard_defect(self) -> None:
        """M3 gate proof: a NEW asymmetric edge NOT in the baseline is a HARD DEFECT.

        This is the injection proof that the ratchet works: OIM-208/209 cannot
        add a new one-sided edge without triggering a blocking DEFECT.

        Uses entity/SD IDs that are guaranteed not to be in the baseline
        (synthetic IDs that do not exist in the model).
        """
        # Synthetic entities/SDs that are not in the baseline.
        entity = _FakeEntity("E-99", consumed_by=["SD-99.9"])
        sd = _FakeSD("SD-99.9", consumes=[])  # does NOT list E-99 back
        em = _FakeEntityModel([entity])
        sdm = _FakeSDModel([sd])
        defects, _ = _run_scan(_validate.check_two_sided_edges, em, sdm)
        self.assertTrue(
            any("E-99" in d and "SD-99.9" in d and "HARD DEFECT" in d for d in defects),
            f"Expected a HARD DEFECT about E-99/SD-99.9 new one-sided edge; got: {defects}",
        )

    def test_negative_entity_consumed_by_sd_not_in_sd_consumes(self) -> None:
        """OIM-204 shape: entity says Consumed by SD-X, SD-X does not list entity.

        This is direction 1 of the OIM-204 one-sided-edge defect class: the
        entity file declares 'Consumed by: SD-X' but SD-X has no 'Consumes'
        entry for the entity.  Because the IDs used here are synthetic (not in
        any baseline), this must surface as a HARD DEFECT.
        """
        entity = _FakeEntity("FO-99", consumed_by=["SD-12.9"])
        # SD-12.9 does NOT list FO-99 in its Consumes (the historical defect shape).
        sd = _FakeSD("SD-12.9", consumes=[])
        em = _FakeEntityModel([entity])
        sdm = _FakeSDModel([sd])
        defects, _ = _run_scan(_validate.check_two_sided_edges, em, sdm)
        self.assertTrue(
            any("FO-99" in d and "SD-12.9" in d for d in defects),
            f"Expected a defect about FO-99/SD-12.9 one-sided edge; got: {defects}",
        )

    def test_negative_sd_consumes_entity_not_in_entity_consumed_by(self) -> None:
        """OIM-207 shape: SD says Consumes entity, entity does not list SD.

        This is direction 2 of the OIM-207 SD-13.2 mislabel defect class: the
        SD file declares 'Consumes: E-XX' but E-XX does not list SD-13.2 in
        'Consumed by'.  Uses a synthetic SD ID not in the baseline.
        """
        # Entity does NOT list SD-99.1 in Consumed by.
        entity = _FakeEntity("E-01", consumed_by=[])
        # SD-99.1 claims to consume E-01 (synthetic ID not in baseline).
        sd = _FakeSD("SD-99.1", consumes=["E-01"])
        em = _FakeEntityModel([entity])
        sdm = _FakeSDModel([sd])
        defects, _ = _run_scan(_validate.check_two_sided_edges, em, sdm)
        self.assertTrue(
            any("SD-99.1" in d and "E-01" in d for d in defects),
            f"Expected a defect about SD-99.1/E-01 one-sided edge; got: {defects}",
        )

    def test_positive_live_tree_produces_no_defects_only_baseline_warnings(self) -> None:
        """The live tree produces zero defects; baseline edges surface as warnings.

        After the OIM-212 cycle-2 ratchet, the check is a HARD DEFECT for any
        NEW asymmetric edge.  The 659 grandfathered edges emit WARNINGs only;
        the live tree produces zero defects.
        """
        parser_models = _validate._load_parser_models()
        if parser_models is None:
            self.skipTest("Parser models unavailable — skipping live-tree positive test")
        em, sdm = parser_models
        orig_defects = _validate.defects[:]
        orig_warnings = _validate.warnings[:]
        _validate.defects.clear()
        _validate.warnings.clear()
        try:
            _validate.check_two_sided_edges(em, sdm)
            self.assertEqual(
                _validate.defects,
                [],
                f"check_two_sided_edges produced defects on live tree: {_validate.defects}",
            )
            # Confirm the check IS producing warnings (the grandfathered set is visible).
            self.assertTrue(
                len(_validate.warnings) > 0,
                "check_two_sided_edges produced zero warnings on live tree — "
                "expected 659 grandfathered baseline edges to surface as warnings",
            )
        finally:
            _validate.defects[:] = orig_defects
            _validate.warnings[:] = orig_warnings


# ---------------------------------------------------------------------------
# 3. check_deferral_language
# ---------------------------------------------------------------------------

class TestDeferralLanguage(unittest.TestCase):
    """Advisory WARNING: deferral phrasing scan.

    This check does NOT produce defects; it produces WARNINGs for human review.
    Tests confirm:
      - The known OIM-207 residuals (FO-02:73, fund-operations/README.md:26)
        are no longer present after the OIM-212 fixes.
      - The check would surface a 'a later addition' pattern injected into a
        probe file (proving the check works).

    Note: since the check reads the live filesystem, we verify the FIXED state
    rather than injecting fixtures (the fixed files are the source of truth).
    """

    def test_fo02_residual_is_fixed(self) -> None:
        """FO-02-share-unit-class.md:73 no longer contains 'a later addition'."""
        fo02 = ROOT / "model" / "entities" / "specialisations" / "fund-operations" / "FO-02-share-unit-class.md"
        if not fo02.exists():
            self.skipTest("FO-02 file not found")
        text = fo02.read_text(encoding="utf-8")
        lines = text.splitlines()
        # Line 73 (0-indexed: 72) should not carry the deferral phrasing.
        # Use a broader search across the file to confirm the stale phrase is gone.
        self.assertNotIn(
            "a later addition",
            text,
            "FO-02-share-unit-class.md still contains 'a later addition' — "
            "the OIM-212 residual fix was not applied or was reverted",
        )

    def test_fo_readme_residual_is_fixed(self) -> None:
        """fund-operations/README.md:26 no longer contains 'later additions'."""
        fo_readme = (
            ROOT / "model" / "entities" / "specialisations"
            / "fund-operations" / "README.md"
        )
        if not fo_readme.exists():
            self.skipTest("fund-operations README not found")
        text = fo_readme.read_text(encoding="utf-8")
        self.assertNotIn(
            "later additions",
            text,
            "fund-operations/README.md still contains 'later additions' — "
            "the OIM-212 residual fix was not applied or was reverted",
        )

    def test_deferral_check_surfaces_a_later_addition(self) -> None:
        """The check correctly surfaces 'a later addition' phrasing.

        Probes the regex patterns directly against an in-memory string
        to confirm the check logic is active (pattern compilation succeeds
        and the combined_re matches the deferral phrase).
        """
        combined_re = re.compile(
            "|".join(f"(?:{p})" for p in _validate._DEFERRAL_PATTERNS),
            re.IGNORECASE,
        )
        sample = "The fee-accrual entity is a later addition to this pack."
        matches = list(combined_re.finditer(sample))
        self.assertTrue(
            len(matches) > 0,
            "Expected the deferral pattern to match 'a later addition' but got no match",
        )

    def test_deferral_check_surfaces_later_additions_plural(self) -> None:
        """The check surfaces the plural 'later additions' form (fund-operations/README.md:26 shape)."""
        combined_re = re.compile(
            "|".join(f"(?:{p})" for p in _validate._DEFERRAL_PATTERNS),
            re.IGNORECASE,
        )
        sample = "The per-period hedge P&L and fee-accrual grain are later additions."
        matches = list(combined_re.finditer(sample))
        self.assertTrue(
            len(matches) > 0,
            "Expected the deferral pattern to match 'later additions' but got no match",
        )


# ---------------------------------------------------------------------------
# 4. Guard tests for OIM-210 deferral-pattern narrowing (ADR-0067 + OIM-210)
# ---------------------------------------------------------------------------

class TestDeferralPatternNarrowing(unittest.TestCase):
    """Guard tests for the OIM-210 MN-2 deferral-pattern narrowing.

    OIM-210 cycle-1 replaced the over-broad r'\\bdeferred\\b' with
    build-state-specific phrasings.  These guard tests assert:
      (a) The new build-state patterns DO fire (positive coverage).
      (b) Legitimate domain uses of 'deferred' do NOT fire (false-positive guard).

    Added: OIM-210 cycle-2 fold (ADR-0067 guard-test discipline — OIM-212 precedent).
    """

    def _combined_re(self):
        return re.compile(
            "|".join(f"(?:{p})" for p in _validate._DEFERRAL_PATTERNS),
            re.IGNORECASE,
        )

    # -- (a) Build-state phrasings MUST fire --

    def test_deferred_to_oim_nn_fires(self) -> None:
        """'deferred to OIM-NN' is a stale-build phrasing and MUST be caught."""
        pattern = self._combined_re()
        sample = "The fee entity was deferred to OIM-215 when the pack is next extended."
        matches = list(pattern.finditer(sample))
        self.assertTrue(
            len(matches) > 0,
            "Expected 'deferred to OIM-NN' to match but got no match. "
            "Check that the _DEFERRAL_PATTERNS list includes the OIM-NN form.",
        )

    def test_deferred_to_a_later_fires(self) -> None:
        """'deferred to a later' is a stale-build phrasing and MUST be caught."""
        pattern = self._combined_re()
        sample = "This entity was deferred to a later item in the backlog."
        matches = list(pattern.finditer(sample))
        self.assertTrue(
            len(matches) > 0,
            "Expected 'deferred to a later' to match but got no match.",
        )

    def test_deferred_to_the_next_cycle_fires(self) -> None:
        """'deferred to the next cycle' is a stale-build phrasing and MUST be caught."""
        pattern = self._combined_re()
        sample = "The sub-TA wiring was deferred to the next cycle."
        matches = list(pattern.finditer(sample))
        self.assertTrue(
            len(matches) > 0,
            "Expected 'deferred to the next cycle' to match but got no match.",
        )

    def test_deferred_extension_fires(self) -> None:
        """'deferred extension' is a stale-build phrasing and MUST be caught."""
        pattern = self._combined_re()
        sample = "The prime-broker consumer wiring is a deferred extension."
        matches = list(pattern.finditer(sample))
        self.assertTrue(
            len(matches) > 0,
            "Expected 'deferred extension' to match but got no match.",
        )

    # -- (b) Legitimate domain uses must NOT fire --

    def test_deferred_tax_does_not_fire(self) -> None:
        """'deferred tax' is a legitimate domain term and must NOT be caught."""
        pattern = self._combined_re()
        sample = "BD-17 covers the deferred tax accounting service domain."
        matches = [m for m in pattern.finditer(sample)]
        self.assertEqual(
            matches, [],
            f"'deferred tax' produced unexpected matches: {[m.group() for m in matches]}. "
            "Check that bare 'deferred' is NOT in _DEFERRAL_PATTERNS.",
        )

    def test_deferred_compensation_does_not_fire(self) -> None:
        """'deferred compensation' is a legitimate domain term and must NOT be caught."""
        pattern = self._combined_re()
        sample = "SD-17.5 covers deferred compensation arrangements."
        matches = [m for m in pattern.finditer(sample)]
        self.assertEqual(
            matches, [],
            f"'deferred compensation' produced unexpected matches: {[m.group() for m in matches]}. "
            "Check that bare 'deferred' is NOT in _DEFERRAL_PATTERNS.",
        )

    def test_deferred_to_isda_cdm_does_not_fire(self) -> None:
        """'deferred to ISDA CDM' is a legitimate architecture-boundary statement."""
        pattern = self._combined_re()
        sample = "The transaction-grain contract model is deferred to ISDA CDM."
        matches = [m for m in pattern.finditer(sample)]
        self.assertEqual(
            matches, [],
            f"'deferred to ISDA CDM' produced unexpected matches: {[m.group() for m in matches]}. "
            "The pattern should only match 'deferred to OIM-NN' or 'deferred to a later ...'.",
        )

    def test_deferred_to_the_next_dealing_cycle_does_not_fire(self) -> None:
        """'deferred to the next dealing cycle' is operational semantics, not build-state."""
        pattern = self._combined_re()
        # 'dealing cycle' does not match 'item|cycle|build' in the pattern
        # because the pattern is 'next (item|cycle|build)' and 'dealing cycle'
        # would only match if 'dealing' were absent — this tests the boundary.
        # Note: the current pattern 'the next (?:item|cycle|build)' WILL match
        # 'deferred to the next cycle' — but 'deferred to the next dealing cycle'
        # includes the word 'dealing' before 'cycle', so it does NOT match the
        # pattern 'deferred to the next cycle' (which is literal).
        sample = "The order's settlement is deferred to the next dealing cycle."
        # This should NOT match because 'dealing cycle' != 'cycle' (word boundary OK,
        # but the full phrase 'the next dealing cycle' != 'the next cycle').
        matches = [m for m in pattern.finditer(sample)]
        self.assertEqual(
            matches, [],
            f"'deferred to the next dealing cycle' produced unexpected matches: "
            f"{[m.group() for m in matches]}. "
            "The pattern 'the next (?:item|cycle|build)' should not match 'the next dealing cycle'.",
        )

    def test_deferred_to_accounting_layer_does_not_fire(self) -> None:
        """'deferred to the accounting layer' is an architecture-boundary statement."""
        pattern = self._combined_re()
        sample = "The tax-lot basis tracking is deferred to the accounting layer."
        matches = [m for m in pattern.finditer(sample)]
        self.assertEqual(
            matches, [],
            f"'deferred to the accounting layer' produced unexpected matches: "
            f"{[m.group() for m in matches]}.",
        )


if __name__ == "__main__":
    unittest.main()
