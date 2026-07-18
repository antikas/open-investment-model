"""Tests for the Item 5 (oim-5b3t) relation-coverage validator check.

Covers `check_relation_coverage` (+ its two split-out sub-checks) in
`tools/openim-validate/validate.py`:

  (a) bidirectional coverage over the FULL edge set (D7) — self and
      polymorphic edges are now in scope, ending the orphan-verb carve-out
      Item 1 deferred for self/polymorphic-only verbs;
  (b) inverse consistency + bijectivity — every verb declares a non-empty
      inverse, no two verbs share an inverse, and no inverse collides with a
      declared forward verb name;
  (c) D8 — `model/relations.md` absent while the entity model exists is
      itself a validator defect.

Each hard check carries a POSITIVE test (clean input produces no defects) and
a NEGATIVE test per planted-defect shape (unmapped edge, orphan verb, inverse
collision). Negative tests build isolated `RelationModel` / `RelationVerb` /
`RelationBinding` fixtures straight from `exports.relations_parse` (the
production dataclasses) rather than mutating the live tree — the
no-mutate-restore lesson (OIM-201) — mirroring the `test_oim212_checks.py`
`_run_scan` idiom.

To run:
    python -m pytest tools/openim-validate/tests/test_relation_coverage.py
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # repo root
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

# Reuse the Item-1 relations.md parse helper's production dataclasses for the
# in-memory negative fixtures — never a hand-rolled parallel shape.
from exports.relations_parse import (          # noqa: E402
    RelationModel, RelationVerb, RelationBinding, parse_relations,
)

# ---------------------------------------------------------------------------
# Import the validator module under test (mirrors test_oim212_checks.py).
# ---------------------------------------------------------------------------
_VALIDATE_PY = ROOT / "tools" / "openim-validate" / "validate.py"
_spec = importlib.util.spec_from_file_location("_validate", _VALIDATE_PY)
_validate = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_validate)  # type: ignore[union-attr]


def _run_scan(fn, *args, **kwargs):
    """Run a validator check in isolation; return (defects, warnings)."""
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


def _verb(lpg: str, inverse: str) -> RelationVerb:
    return RelationVerb(
        lpg=lpg, owl=lpg.lower().replace("_", "-"), inverse=inverse,
        kind="reference", cardinality="n-to-1",
        direction_source="X", direction_target="Y")


# ---------------------------------------------------------------------------
# (a) bidirectional coverage — D7
# ---------------------------------------------------------------------------

class TestBidirectionalCoverage(unittest.TestCase):

    def test_positive_clean_model_no_defects(self) -> None:
        rel = RelationModel(
            verbs={"ISSUED_BY": _verb("ISSUED_BY", "ISSUER_OF")},
            bindings=[RelationBinding("E-02", "issuer_entity_id", "E-01",
                                       "ISSUED_BY", "role", False)],
        )
        fk_edges = {("E-02", "issuer_entity_id")}
        defects, _w = _run_scan(
            _validate._check_relation_bidirectional_coverage, rel, fk_edges, [])
        self.assertEqual(defects, [], f"unexpected defects: {defects}")

    def test_negative_planted_unmapped_edge_fails(self) -> None:
        """A currently-parseable edge with no binding at all IS caught."""
        rel = RelationModel(
            verbs={"ISSUED_BY": _verb("ISSUED_BY", "ISSUER_OF")},
            bindings=[RelationBinding("E-02", "issuer_entity_id", "E-01",
                                       "ISSUED_BY", "role", False)],
        )
        # Plant an extra edge the mapping table does not bind.
        fk_edges = {("E-02", "issuer_entity_id"), ("E-99", "planted_fk_id")}
        defects, _w = _run_scan(
            _validate._check_relation_bidirectional_coverage, rel, fk_edges, [])
        self.assertTrue(
            any("E-99.planted_fk_id" in d and "not bound" in d for d in defects),
            f"expected an unmapped-edge defect for E-99.planted_fk_id; got: {defects}")

    def test_negative_planted_orphan_verb_fails(self) -> None:
        """A declared verb with zero bindings IS caught (D7 carve-out ends
        at Item 5 — applies to self/poly-only verbs too, see next test)."""
        rel = RelationModel(
            verbs={
                "ISSUED_BY": _verb("ISSUED_BY", "ISSUER_OF"),
                "ORPHAN_VERB": _verb("ORPHAN_VERB", "ORPHANED_BY"),
            },
            bindings=[RelationBinding("E-02", "issuer_entity_id", "E-01",
                                       "ISSUED_BY", "role", False)],
        )
        fk_edges = {("E-02", "issuer_entity_id")}
        defects, _w = _run_scan(
            _validate._check_relation_bidirectional_coverage, rel, fk_edges, [])
        self.assertTrue(
            any("ORPHAN_VERB" in d and "binds no edge" in d for d in defects),
            f"expected an orphan-verb defect for ORPHAN_VERB; got: {defects}")

    def test_negative_planted_self_only_verb_with_no_binding_is_orphan(self) -> None:
        """A self/polymorphic-only verb that binds NOTHING is still an orphan
        — the Item-1 carve-out exempted such verbs from the orphan check only
        until the full self/poly edge set was parseable; Item 5 (post Item-2)
        ends that exemption entirely."""
        rel = RelationModel(
            verbs={"SELF_ONLY": _verb("SELF_ONLY", "SELF_ONLY_INV")},
            bindings=[],  # binds nothing at all — not even a self edge
        )
        defects, _w = _run_scan(
            _validate._check_relation_bidirectional_coverage, rel, set(), [])
        self.assertTrue(
            any("SELF_ONLY" in d and "binds no edge" in d for d in defects),
            f"expected an orphan-verb defect for SELF_ONLY; got: {defects}")

    def test_specialises_line_unbound_is_caught(self) -> None:
        rel = RelationModel(
            verbs={"SPECIALISES": _verb("SPECIALISES", "SPECIALISED_BY")},
            bindings=[],
        )
        defects, _w = _run_scan(
            _validate._check_relation_bidirectional_coverage, rel, set(),
            [("DR-01", "E-02")])
        self.assertTrue(
            any("DR-01" in d and "Specialises" in d for d in defects),
            f"expected an unbound-Specialises defect for DR-01; got: {defects}")

    def test_edge_bound_twice_is_caught(self) -> None:
        rel = RelationModel(
            verbs={
                "ISSUED_BY": _verb("ISSUED_BY", "ISSUER_OF"),
                "MANAGED_BY": _verb("MANAGED_BY", "MANAGES"),
            },
            bindings=[
                RelationBinding("E-02", "issuer_entity_id", "E-01",
                                 "ISSUED_BY", "role", False),
                RelationBinding("E-02", "issuer_entity_id", "E-01",
                                 "MANAGED_BY", "role", False),
            ],
        )
        fk_edges = {("E-02", "issuer_entity_id")}
        defects, _w = _run_scan(
            _validate._check_relation_bidirectional_coverage, rel, fk_edges, [])
        self.assertTrue(
            any("issuer_entity_id" in d and "more than one verb" in d for d in defects),
            f"expected a double-bound-edge defect; got: {defects}")


# ---------------------------------------------------------------------------
# (b) inverse consistency + bijectivity
# ---------------------------------------------------------------------------

class TestInverseBijectivity(unittest.TestCase):

    def test_positive_clean_inverses_no_defects(self) -> None:
        rel = RelationModel(
            verbs={
                "ISSUED_BY": _verb("ISSUED_BY", "ISSUER_OF"),
                "MANAGED_BY": _verb("MANAGED_BY", "MANAGES"),
            },
            bindings=[],
        )
        defects, _w = _run_scan(_validate._check_relation_inverse_bijectivity, rel)
        self.assertEqual(defects, [], f"unexpected defects: {defects}")

    def test_negative_planted_inverse_collision_fails(self) -> None:
        """Two verbs claiming the same inverse name IS caught (not a bijection)."""
        rel = RelationModel(
            verbs={
                "ISSUED_BY": _verb("ISSUED_BY", "SHARED_INVERSE"),
                "MANAGED_BY": _verb("MANAGED_BY", "SHARED_INVERSE"),
            },
            bindings=[],
        )
        defects, _w = _run_scan(_validate._check_relation_inverse_bijectivity, rel)
        self.assertTrue(
            any("SHARED_INVERSE" in d and "ISSUED_BY" in d and "MANAGED_BY" in d
                for d in defects),
            f"expected an inverse-collision defect for SHARED_INVERSE; got: {defects}")

    def test_negative_inverse_collides_with_forward_verb_name(self) -> None:
        """An inverse that is ITSELF a declared forward verb IS caught."""
        rel = RelationModel(
            verbs={
                "ISSUED_BY": _verb("ISSUED_BY", "MANAGED_BY"),  # collides!
                "MANAGED_BY": _verb("MANAGED_BY", "MANAGES"),
            },
            bindings=[],
        )
        defects, _w = _run_scan(_validate._check_relation_inverse_bijectivity, rel)
        self.assertTrue(
            any("MANAGED_BY" in d and "collides with a declared forward verb" in d
                for d in defects),
            f"expected a forward-verb-collision defect; got: {defects}")

    def test_negative_missing_inverse_fails(self) -> None:
        rel = RelationModel(
            verbs={"NO_INVERSE": _verb("NO_INVERSE", "")},
            bindings=[],
        )
        defects, _w = _run_scan(_validate._check_relation_inverse_bijectivity, rel)
        self.assertTrue(
            any("NO_INVERSE" in d and "no inverse" in d for d in defects),
            f"expected a missing-inverse defect for NO_INVERSE; got: {defects}")


# ---------------------------------------------------------------------------
# (c) D8 — model-absent relations.md
# ---------------------------------------------------------------------------

class TestD8ModelAbsentRelationsMd(unittest.TestCase):

    def test_relations_absent_entity_model_present_is_defect(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "model" / "entities").mkdir(parents=True)
            defects, _w = _run_scan(_validate.check_relation_coverage, None, root)
        self.assertTrue(
            any("model/relations.md is absent" in d and "D8" in d for d in defects),
            f"expected a D8 defect; got: {defects}")

    def test_relations_and_entity_model_both_absent_is_not_a_defect(self) -> None:
        """No model at all (e.g. a stripped tree without model/entities) is
        NOT itself a D8 defect — the vocabulary is only mandatory once the
        entity model exists."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)  # nothing under root at all
            defects, _w = _run_scan(_validate.check_relation_coverage, None, root)
        self.assertEqual(defects, [], f"unexpected defects: {defects}")


# ---------------------------------------------------------------------------
# Live-tree positive tests
# ---------------------------------------------------------------------------

class TestLiveModel(unittest.TestCase):
    """The real model/relations.md + entity model pass cleanly, and the
    self/polymorphic-only verbs deferred from Item 1 now bind >=1 edge."""

    def test_positive_live_tree_passes(self) -> None:
        defects, _w = _run_scan(_validate.check_relation_coverage)
        self.assertEqual(
            defects, [],
            f"check_relation_coverage produced defects on the live tree: {defects}")

    def test_deferred_self_and_polymorphic_verbs_bind_at_least_one_edge(self) -> None:
        """D7: the self/polymorphic-only verbs the Item-1 carve-out deferred
        each bind >=1 real edge on the live model, now that Item 2's parser
        reads self/poly FKs (`fk_targets`) and the carve-out ends here."""
        rel = parse_relations(ROOT)
        bound_verbs = {b.verb for b in rel.bindings}
        deferred = [
            "ANNEXED_TO", "SUBSIDIARY_OF", "SUB_PORTFOLIO_OF", "SUPERSEDED_BY",
            "SUBFUND_OF", "CORRECTS", "HAS_SUBJECT", "HOLDS_INTEREST_IN",
        ]
        present = [v for v in deferred if v in rel.verbs]
        self.assertTrue(
            present,
            "none of the expected deferred self/poly verbs are declared in "
            "model/relations.md — fixture drifted from the model")
        for v in present:
            self.assertIn(
                v, bound_verbs,
                f"deferred verb {v} binds no edge — the D7 carve-out should "
                f"have ended at Item 5")


if __name__ == "__main__":
    unittest.main()
