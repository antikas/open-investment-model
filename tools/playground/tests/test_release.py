"""The adaptation of the released ontology, when this checkout carries it.

A public checkout of an OpenIM release has `exports/openim.rdf`; these checks run
against it. A checkout without it (the model's build home, where the file is
generated into a staging tree) skips them, and the same checks run there against
a freshly generated ontology.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph
from rdflib.query import ResultRow
from rdflib.namespace import OWL

from playground import generate, transform, verify

ROOT = Path(__file__).resolve().parents[3]
RELEASED = ROOT / "exports" / "openim.rdf"

pytestmark = pytest.mark.skipif(
    not RELEASED.is_file() or not (ROOT / "CITATION.cff").is_file(),
    reason="no exports/openim.rdf in this checkout (generated into staging by the build home)")


@pytest.fixture(scope="module")
def built():
    return generate.build(ROOT, RELEASED)


def test_the_release_adapts_without_a_defect_and_every_change_has_a_rule(built):
    result, rdf_text, _ = built
    out = Graph()
    out.parse(data=rdf_text, format="xml")
    src = transform.load_graph(RELEASED)
    assert verify.verify_all(src, out, result.rows) == []
    assert verify.check_traceability(result.source_triples, transform.flatten(out), result.ledger, transform.RULES) == []


def test_the_mapping_counts_match_the_source_counted_independently(built):
    src = Graph()
    src.parse(str(RELEASED), format="xml")

    def count(t):
        q = f"SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {{ ?s a <{t}> . FILTER(isIRI(?s)) }}"
        row = next(iter(src.query(q)))
        assert isinstance(row, ResultRow), "a SELECT query returns result rows"
        return int(str(row[0]))
    result = built[0]
    for kind, t in (("class", OWL.Class), ("object_property", OWL.ObjectProperty),
                    ("datatype_property", OWL.DatatypeProperty)):
        assert sum(1 for r in result.rows if r.kind == kind) == count(t)


def test_the_ontology_header_names_the_release_source_and_digest(built):
    from release_version import read_release_version
    _, rdf_text, _ = built
    assert f"<owl:versionInfo>{read_release_version(ROOT)}</owl:versionInfo>" in rdf_text
    assert transform.file_sha256(RELEASED) in rdf_text
    assert f"/raw/v{read_release_version(ROOT)}/exports/openim.rdf" in rdf_text
