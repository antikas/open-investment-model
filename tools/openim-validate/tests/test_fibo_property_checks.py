"""Tests for the object-property leg of check_fibo_curie_resolvability (F2).

The class leg (OIM-213) gates `fibo-*:Class` curies; this leg gates
`fibo-*:objectProperty` curies asserted under model/ (the relation-verb FIBO
alignment). A fabricated object-property citation — a plausible verb invented
under a real FIBO prefix — is a HARD defect, exactly as a fabricated class is.

Negative tests inject synthetic text through the pure helpers
(`_extract_fibo_property_tokens`, `_check_fibo_property_tokens`) — text/data in,
defects out, no file I/O, no mutate-and-restore of the live tree.

To run:
    python -m pytest tools/openim-validate/tests/test_fibo_property_checks.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import importlib.util

_VALIDATE_PY = ROOT / "tools" / "openim-validate" / "validate.py"
_spec = importlib.util.spec_from_file_location("_validate", _VALIDATE_PY)
_validate = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_validate)  # type: ignore[union-attr]


def _run_scan(fn, *args, **kwargs):
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


# A synthetic object-property reference mirroring the real file's shape.
_SYNTH_PROP_REFERENCE = {
    "fibo-fnd-rel-rel": {"isIssuedBy", "isHeldBy", "isGeneratedBy"},
    "fibo-sec-fund-fund": {"isSubFundOf"},
    "fibo-be-oac-cctl": {"isSubsidiaryOf", "isAffiliateOf"},
}


class TestPropertyTokenExtraction(unittest.TestCase):
    """_extract_fibo_property_tokens: what is (and is not) a property curie."""

    def test_extracts_lowercamel_property_curies(self) -> None:
        text = (
            "Aligns to `fibo-fnd-rel-rel:isIssuedBy` and "
            "`fibo-sec-fund-fund:isSubFundOf` at the relation level.\n"
        )
        tokens = _validate._extract_fibo_property_tokens(text)
        self.assertIn(("fibo-fnd-rel-rel", "isIssuedBy"), tokens)
        self.assertIn(("fibo-sec-fund-fund", "isSubFundOf"), tokens)
        self.assertEqual(len(tokens), 2)

    def test_class_curie_is_not_a_property_token(self) -> None:
        """An UpperCamel class curie must NOT be picked up by the property
        pattern (the two gates are disjoint by local-name case)."""
        text = "Aligns to `fibo-sec-fund-fund:CollectiveInvestmentVehicle`."
        self.assertEqual(_validate._extract_fibo_property_tokens(text), [])

    def test_bare_module_prefix_is_not_a_property_token(self) -> None:
        text = "The rate/FX slice aligns to `fibo-ind-ir-ir` (interest rates)."
        self.assertEqual(_validate._extract_fibo_property_tokens(text), [])

    def test_property_curie_is_not_a_class_token(self) -> None:
        """Symmetry: the class extractor must NOT pick up a lowerCamel property
        curie — so a property curie is gated only against object_properties."""
        text = "Aligns to `fibo-fnd-rel-rel:isIssuedBy`."
        self.assertEqual(_validate._extract_fibo_curie_tokens(text), [])


class TestPropertyResolution(unittest.TestCase):
    """_check_fibo_property_tokens: resolution against the property reference."""

    def test_positive_verified_properties_produce_no_defect(self) -> None:
        tokens = [
            ("fibo-fnd-rel-rel", "isIssuedBy"),
            ("fibo-sec-fund-fund", "isSubFundOf"),
            ("fibo-be-oac-cctl", "isSubsidiaryOf"),
        ]
        defects, _ = _run_scan(
            _validate._check_fibo_property_tokens,
            "test-fixture.md", tokens, _SYNTH_PROP_REFERENCE,
        )
        self.assertEqual(defects, [], f"Unexpected defects: {defects}")

    def test_negative_fabricated_property_under_real_prefix_is_caught(self) -> None:
        """The OIM-204 fabrication shape at the edge level: a plausible verb
        invented under a real FIBO prefix IS caught."""
        tokens = _validate._extract_fibo_property_tokens(
            "FIBO's `fibo-fnd-rel-rel:isManagedByGeneralPartner` models the "
            "fund-manager relationship."
        )
        self.assertEqual(
            tokens, [("fibo-fnd-rel-rel", "isManagedByGeneralPartner")])
        defects, _ = _run_scan(
            _validate._check_fibo_property_tokens,
            "test-fixture.md", tokens, _SYNTH_PROP_REFERENCE,
        )
        self.assertTrue(
            any("isManagedByGeneralPartner" in d and "does not resolve" in d
                for d in defects),
            f"Expected a does-not-resolve defect; got: {defects}",
        )

    def test_negative_property_under_prefix_with_no_props_is_caught(self) -> None:
        """A property curie under a prefix that has no verified object
        properties (a class-only or unknown prefix) IS caught."""
        tokens = [("fibo-fbc-pas-caa", "hasFabricatedRelation")]
        defects, _ = _run_scan(
            _validate._check_fibo_property_tokens,
            "test-fixture.md", tokens, _SYNTH_PROP_REFERENCE,
        )
        self.assertTrue(
            any("fibo-fbc-pas-caa:hasFabricatedRelation" in d and "prefix" in d
                for d in defects),
            f"Expected an unknown-prefix defect; got: {defects}",
        )


class TestPropertyReferenceLoadingAndLiveTree(unittest.TestCase):
    """The property reference loader and the live-tree positive."""

    def test_shipped_property_reference_loads_and_covers_aligned_props(self) -> None:
        reference = _validate._load_fibo_property_reference(
            _validate.FIBO_CURIE_REFERENCE)
        self.assertIsNotNone(reference)
        self.assertIn("isIssuedBy", reference["fibo-fnd-rel-rel"])
        self.assertIn("isSubFundOf", reference["fibo-sec-fund-fund"])
        self.assertIn("hasCounterparty", reference["fibo-fnd-agr-ctr"])
        self.assertIn("hasUnderlier", reference["fibo-fbc-fi-fi"])

    def test_negative_fabricated_property_caught_against_live_reference(self) -> None:
        """A fabricated property is caught against the REAL shipped reference —
        proves the live reference does not quietly whitelist it."""
        reference = _validate._load_fibo_property_reference(
            _validate.FIBO_CURIE_REFERENCE)
        self.assertIsNotNone(reference)
        defects, _ = _run_scan(
            _validate._check_fibo_property_tokens,
            "test-fixture.md",
            [("fibo-sec-fund-fund", "isManagedByFabricatedRole")],
            reference,
        )
        self.assertTrue(
            any("isManagedByFabricatedRole" in d for d in defects),
            f"Expected the fabricated property to be flagged; got: {defects}",
        )

    def test_positive_live_tree_produces_no_defects(self) -> None:
        """Every class AND object-property curie under the live model/ tree
        resolves — the F2 alignment cites only verified FIBO properties."""
        defects, _ = _run_scan(_validate.check_fibo_curie_resolvability)
        self.assertEqual(
            defects, [],
            f"check_fibo_curie_resolvability produced defects on the live "
            f"tree: {defects}",
        )


if __name__ == "__main__":
    unittest.main()
