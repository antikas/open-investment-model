"""Tests for the OIM-213 validator check (FIBO-curie resolvability).

Covers check_fibo_curie_resolvability in tools/openim-validate/validate.py:
every `fibo-*:Class` / `cmns-*:Class` curie asserted anywhere under model/
must resolve against the verified resolvable-curie reference
(fibo_curie_reference.json). A fabricated FIBO citation is a HARD defect.

Each check has POSITIVE tests (verified-real curies and the live tree pass)
and NEGATIVE tests (an injected known-fabricated curie IS caught). Negative
tests inject synthetic text through the pure helpers
(`_extract_fibo_curie_tokens`, `_check_fibo_curie_tokens`) — text/data in,
defects out, no file I/O — so no mutate-and-restore of the live tree is
needed (the no-mutate-restore lesson, OIM-201).

The negative fixtures reproduce the historical defect shapes named in the
OIM-213 backlog item:
  - OIM-202/OIM-204: `fibo-sec-fund-fund:FundShareClassUnit` — a plausible
    class name fabricated under a real FIBO prefix (the exact curie that
    slipped the OIM-202 audit).
  - A fabricated prefix (a module that does not exist in FIBO at all).
  - A deleted reference file (the gate cannot be silently disabled).

To run:
    python -m pytest tools/openim-validate/tests/test_oim213_checks.py
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


# A synthetic reference mirroring the real file's shape — a real-prefix
# entry with a small verified class set, plus a Commons prefix.
_SYNTH_REFERENCE = {
    "fibo-sec-fund-fund": {"CollectiveInvestmentVehicle", "FundUnit", "FundManager"},
    "fibo-fbc-fi-fi": {"FinancialInstrument", "FinancialInstrumentIdentifier"},
    "cmns-org": {"LegalEntity", "LegalPerson"},
}


class TestCurieTokenExtraction(unittest.TestCase):
    """_extract_fibo_curie_tokens: what is (and is not) an asserted curie."""

    def test_extracts_backticked_and_plain_curies(self) -> None:
        text = (
            "Aligns to `fibo-sec-fund-fund:CollectiveInvestmentVehicle` and "
            "cmns-org:LegalEntity at the structural level.\n"
        )
        tokens = _validate._extract_fibo_curie_tokens(text)
        self.assertIn(("fibo-sec-fund-fund", "CollectiveInvestmentVehicle"), tokens)
        self.assertIn(("cmns-org", "LegalEntity"), tokens)
        self.assertEqual(len(tokens), 2)

    def test_prefix_only_module_mention_is_not_a_curie(self) -> None:
        """`fibo-ind-ir-ir` (interest rates) asserts a module, not a class —
        not matched."""
        text = "The rate/FX slice aligns to `fibo-ind-ir-ir` (interest rates)."
        self.assertEqual(_validate._extract_fibo_curie_tokens(text), [])

    def test_ellipsis_form_is_not_a_curie(self) -> None:
        """The deliberately non-specific `fibo-cae-...:CorporateAction` form
        asserts a concept area, not a resolvable curie — not matched."""
        text = "Corporate-action facet: `fibo-cae-...:CorporateAction` (CAE)."
        self.assertEqual(_validate._extract_fibo_curie_tokens(text), [])

    def test_filename_with_colon_line_number_is_not_a_curie(self) -> None:
        """A file path like fibo-alignment.md:79 must not match (the `.`
        breaks the prefix before the colon; the local name is not
        class-shaped)."""
        text = "See fibo-alignment.md:79 for the FO-02 row."
        self.assertEqual(_validate._extract_fibo_curie_tokens(text), [])


class TestCurieResolution(unittest.TestCase):
    """_check_fibo_curie_tokens: resolution against the reference."""

    def test_positive_verified_curies_produce_no_defect(self) -> None:
        tokens = [
            ("fibo-sec-fund-fund", "CollectiveInvestmentVehicle"),
            ("fibo-fbc-fi-fi", "FinancialInstrumentIdentifier"),
            ("cmns-org", "LegalEntity"),
        ]
        defects, _warnings = _run_scan(
            _validate._check_fibo_curie_tokens,
            "test-fixture.md", tokens, _SYNTH_REFERENCE,
        )
        self.assertEqual(defects, [], f"Unexpected defects: {defects}")

    def test_negative_fabricated_class_under_real_prefix_is_caught(self) -> None:
        """OIM-202/OIM-204 shape: `fibo-sec-fund-fund:FundShareClassUnit` —
        a plausible class name fabricated under a real FIBO prefix (the exact
        historical curie). IS caught."""
        tokens = _validate._extract_fibo_curie_tokens(
            "FIBO's `fibo-sec-fund-fund:FundShareClassUnit` captures the "
            "class as a structural concept within a fund."
        )
        self.assertEqual(tokens, [("fibo-sec-fund-fund", "FundShareClassUnit")])
        defects, _warnings = _run_scan(
            _validate._check_fibo_curie_tokens,
            "test-fixture.md", tokens, _SYNTH_REFERENCE,
        )
        self.assertTrue(
            any("FundShareClassUnit" in d and "does not resolve" in d for d in defects),
            f"Expected a does-not-resolve defect for FundShareClassUnit; got: {defects}",
        )

    def test_negative_fabricated_prefix_is_caught(self) -> None:
        """A curie under a module that does not exist in FIBO at all IS
        caught (the unknown-prefix shape)."""
        tokens = [("fibo-sec-fund-shcls", "ShareClass")]
        defects, _warnings = _run_scan(
            _validate._check_fibo_curie_tokens,
            "test-fixture.md", tokens, _SYNTH_REFERENCE,
        )
        self.assertTrue(
            any("fibo-sec-fund-shcls:ShareClass" in d and "prefix" in d for d in defects),
            f"Expected an unknown-prefix defect; got: {defects}",
        )

    def test_negative_historical_oim204_fabrications_all_caught(self) -> None:
        """The other OIM-204 cycle-1 fabrications (all since de-specified in
        the entity files) would each be caught by the gate today."""
        fabricated = [
            ("fibo-fbc-pas-caa", "UnitOfOwnership"),
            ("fibo-sec-fund-fund", "FundSubscriptionOrder"),
            ("fibo-sec-fund-fund", "FundRedemptionOrder"),
            ("fibo-sec-fund-fund", "FundDistribution"),
        ]
        # Resolve against the REAL shipped reference, not the synthetic one —
        # proves the live reference does not quietly whitelist them.
        reference = _validate._load_fibo_curie_reference(
            _validate.FIBO_CURIE_REFERENCE
        )
        self.assertIsNotNone(reference, "shipped fibo_curie_reference.json must load")
        defects, _warnings = _run_scan(
            _validate._check_fibo_curie_tokens,
            "test-fixture.md", fabricated, reference,
        )
        for _prefix, cls in fabricated:
            self.assertTrue(
                any(cls in d for d in defects),
                f"Expected {cls} to be flagged; got: {defects}",
            )


class TestReferenceLoadingAndLiveTree(unittest.TestCase):
    """The reference file gate and the live-tree positive."""

    def test_shipped_reference_loads_and_covers_known_prefixes(self) -> None:
        reference = _validate._load_fibo_curie_reference(
            _validate.FIBO_CURIE_REFERENCE
        )
        self.assertIsNotNone(reference)
        self.assertIn("fibo-sec-fund-fund", reference)
        self.assertIn("CollectiveInvestmentVehicle", reference["fibo-sec-fund-fund"])
        self.assertIn("cmns-org", reference)

    def test_negative_missing_reference_file_is_a_defect(self) -> None:
        """Deleting the reference file must NOT silently disable the gate —
        it is itself a HARD defect (the OIM-212 baseline precedent)."""
        defects, _warnings = _run_scan(
            _validate.check_fibo_curie_resolvability,
            Path("nonexistent-fibo-curie-reference.json"),
        )
        self.assertTrue(
            any("cannot be silently disabled" in d for d in defects),
            f"Expected a missing-reference defect; got: {defects}",
        )

    def test_positive_live_tree_produces_no_defects(self) -> None:
        """Every curie asserted under the live model/ tree resolves — the
        OIM-213 sweep left no fabricated curie."""
        defects, _warnings = _run_scan(_validate.check_fibo_curie_resolvability)
        self.assertEqual(
            defects, [],
            f"check_fibo_curie_resolvability produced defects on the live "
            f"tree: {defects}",
        )


if __name__ == "__main__":
    unittest.main()
