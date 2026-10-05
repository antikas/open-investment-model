"""Planted defects: each one must be caught by the independent checks.

A check that cannot fail proves nothing, so every test here starts from the
adaptation of the mini ontology, which passes, damages it in one named way, and
requires the checks to report exactly that damage.
"""
from __future__ import annotations

import copy

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from playground import transform, verify
from playground.tests.mini import NS, PG


def mutable_copy(g: Graph) -> Graph:
    out = Graph()
    for t in g:
        out.add(t)
    return out


def class_named(g: Graph, name: str) -> URIRef:
    for s, _, o in g.triples((None, RDFS.label, None)):
        if str(o) == name and (s, RDF.type, OWL.Class) in g:
            assert isinstance(s, URIRef), f"{s} is a class but not an IRI"
            return s
    raise LookupError(f"no class labelled {name!r}")


def defects(source, out, rows):
    return verify.verify_all(source, out, rows)


def test_the_unmodified_adaptation_passes(source_graph, out_graph, built):
    assert defects(source_graph, out_graph, built[0].rows) == []


def test_a_name_collision_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    b = class_named(g, "ListedEquity")
    g.remove((b, RDFS.label, None))
    g.add((b, RDFS.label, Literal("LegalEntity")))
    found = defects(source_graph, g, built[0].rows)
    assert any("name collision" in d and "LegalEntity" in d for d in found), found


def test_a_name_collision_differing_only_in_case_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    b = class_named(g, "ListedEquity")
    g.remove((b, RDFS.label, None))
    g.add((b, RDFS.label, Literal("legalentity")))
    assert any("name collision" in d for d in defects(source_graph, g, built[0].rows))


def test_an_over_length_entity_name_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    c = class_named(g, "LegalEntity")
    g.remove((c, RDFS.label, None))
    g.add((c, RDFS.label, Literal("A" * 27)))
    found = defects(source_graph, g, built[0].rows)
    assert any("breaks the Playground's name rule" in d and "A" * 27 in d for d in found), found


def test_an_over_length_property_name_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    p = URIRef(NS + "E-01#entity_name")
    g.remove((p, RDFS.label, None))
    g.add((p, RDFS.label, Literal("p" * 27)))
    assert any("property name" in d and "breaks" in d for d in defects(source_graph, g, built[0].rows))


def test_an_unsafe_character_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    c = class_named(g, "LegalEntity")
    g.remove((c, RDFS.label, None))
    g.add((c, RDFS.label, Literal("Legal Entity")))
    assert any("breaks the Playground's name rule" in d for d in defects(source_graph, g, built[0].rows))


def test_an_entity_without_an_identifier_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    for s, p, o in list(g.triples((None, URIRef(transform.ONT_IS_IDENTIFIER), None))):
        if str(s).startswith(NS + "E-01#"):
            g.remove((s, p, o))
    found = defects(source_graph, g, built[0].rows)
    assert any("has no identifier property" in d and "LegalEntity" in d for d in found), found


def test_an_identifier_of_the_wrong_type_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    p = URIRef(NS + "E-05#quantity")
    g.add((p, URIRef(transform.ONT_IS_IDENTIFIER), Literal("true", datatype=XSD.boolean)))
    found = defects(source_graph, g, built[0].rows)
    assert any("not string or integer" in d for d in found), found


def test_a_dropped_relationship_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    victim = URIRef(PG + "PM-10_plan_id")
    assert (victim, RDF.type, OWL.ObjectProperty) in g
    for t in list(g.triples((victim, None, None))):
        g.remove(t)
    found = defects(source_graph, g, built[0].rows)
    assert any("relationship" in d and str(victim) in d and "not drawn" in d for d in found), found


def test_one_dropped_member_of_an_expanded_verb_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    victim = URIRef(PG + "specialises_FO-12_E-01")
    for t in list(g.triples((victim, None, None))):
        g.remove(t)
    found = defects(source_graph, g, built[0].rows)
    assert any(str(victim) in d for d in found), found


def test_a_relationship_drawn_to_the_wrong_class_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    p = URIRef(NS + "managed-by")
    g.remove((p, RDFS.range, None))
    g.add((p, RDFS.range, URIRef(NS + "PB-03")))
    assert any("changed its domain or range" in d for d in defects(source_graph, g, built[0].rows))


def test_a_broken_inverse_pair_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    child = URIRef(PG + "issued-by_E-05_E-01")
    g.remove((child, RDFS.domain, None))
    g.add((child, RDFS.domain, URIRef(NS + "E-02")))
    found = defects(source_graph, g, built[0].rows)
    assert any("inverses but their domain and range are not swapped" in d for d in found), found


def test_a_missing_inverse_declaration_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    child = URIRef(PG + "issued-by_E-05_E-01")
    for o in list(g.objects(child, OWL.inverseOf)):
        g.remove((child, OWL.inverseOf, o))
    found = defects(source_graph, g, built[0].rows)
    assert any("owl:inverseOf" in d for d in found), found


def test_a_type_clash_across_entities_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    p = URIRef(NS + "PM-10#version")
    g.remove((p, RDFS.range, None))
    g.add((p, RDFS.range, XSD.integer))
    found = defects(source_graph, g, built[0].rows)
    assert any("property 'version'" in d and "integer" in d and "string" in d for d in found), found


def test_a_description_without_the_openim_code_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    c = class_named(g, "LegalEntity")
    g.remove((c, RDFS.comment, None))
    g.add((c, RDFS.comment, Literal("A person or organisation.")))
    assert any("does not start with its OpenIM code" in d for d in defects(source_graph, g, built[0].rows))


def test_a_missing_cardinality_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    p = URIRef(NS + "managed-by")
    g.remove((p, URIRef(transform.ONT_CARDINALITY), None))
    assert any("cardinality" in d for d in defects(source_graph, g, built[0].rows))


# --- the mapping -------------------------------------------------------------------------

def test_a_dropped_mapping_row_is_caught(source_graph, out_graph, built):
    rows = [r for r in built[0].rows if r.source_iri != NS + "E-02#issuer_entity_id"]
    assert any("mapping has no row" in d for d in defects(source_graph, out_graph, rows))


def test_a_duplicated_mapping_row_is_caught(source_graph, out_graph, built):
    rows = list(built[0].rows) + [copy.copy(built[0].rows[0])]
    assert any("2 rows" in d for d in defects(source_graph, out_graph, rows))


def test_a_mapping_row_for_something_not_in_the_source_is_caught(source_graph, out_graph, built):
    extra = copy.copy(built[0].rows[0])
    extra.source_iri = NS + "E-99"
    assert any("not a named" in d for d in defects(source_graph, out_graph, list(built[0].rows) + [extra]))


def test_a_not_drawn_row_without_a_reason_is_caught(source_graph, out_graph, built):
    rows = [copy.copy(r) for r in built[0].rows]
    victim = next(r for r in rows if r.shown == "no")
    victim.reason = ""
    assert any("gives no reason" in d for d in defects(source_graph, out_graph, rows))


# --- traceability -----------------------------------------------------------------------------

def test_a_triple_added_outside_the_rules_is_caught(built):
    res = built[0]
    stray = (URIRef(NS + "E-01"), RDFS.seeAlso, URIRef("https://example.org/"))
    out = set(res.triples) | {stray}
    found = verify.check_traceability(res.source_triples, out, res.ledger, transform.RULES)
    assert any("added without a rule" in d for d in found), found


def test_a_triple_removed_outside_the_rules_is_caught(built):
    res = built[0]
    victim = next(t for t in sorted(res.triples, key=str) if t[1] == RDFS.range and str(t[0]).endswith("#entity_name"))
    out = set(res.triples) - {victim}
    found = verify.check_traceability(res.source_triples, out, res.ledger, transform.RULES)
    assert any("removed without a rule" in d for d in found), found


def test_a_ledger_entry_with_no_rule_is_caught(built):
    res = built[0]
    ledger = [("made-up-rule", op, t) if i == 0 else (r, op, t) for i, (r, op, t) in enumerate(res.ledger)]
    found = verify.check_traceability(res.source_triples, res.triples, ledger, transform.RULES)
    assert any("unknown rule" in d for d in found), found


# --- identifiers come from the model's declared key ---------------------------------------------

def adapt(source: Graph, provenance):
    """Transform a (damaged) source graph and read the written output back."""
    from playground import rdfxml
    res = transform.transform(source, provenance)
    out = Graph()
    out.parse(data=rdfxml.write(res.triples), format="xml")
    return res, out


def test_an_entity_with_no_declared_or_inherited_key_fails(source_graph, provenance):
    src = mutable_copy(source_graph)
    # a new entity with a column but no declared key and no parent
    keyless = URIRef(NS + "E-90")
    src.add((keyless, RDF.type, OWL.Class))
    src.add((keyless, RDFS.label, Literal("E-90 Keyless")))
    p = URIRef(NS + "E-90#some_id")
    for t in ((p, RDF.type, OWL.DatatypeProperty), (p, RDFS.label, Literal("some_id")),
              (p, RDFS.domain, keyless), (p, RDFS.range, XSD.string)):
        src.add(t)
    res, out = adapt(src, provenance)
    found = defects(src, out, res.rows)
    assert any("has no declared or inherited key" in d and "E-90" in d for d in found), found
    assert any("has no identifier property" in d for d in found), found    # a name rule would have guessed some_id


def test_removing_the_key_declaration_of_an_entity_with_a_parent_inherits_it(source_graph, provenance):
    src = mutable_copy(source_graph)
    p = URIRef(NS + "FO-12#ap_agreement_id")
    src.remove((p, transform.KEY_POSITION, None))
    res, out = adapt(src, provenance)
    row = next(r for r in res.rows if r.source_iri == NS + "FO-12")
    assert "identifier-inherited" in row.rules          # FO-12 specialises E-01
    assert defects(src, out, res.rows) == []


def test_an_identifier_moved_to_a_non_key_property_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    wrong, right = URIRef(NS + "E-02#instrument_id"), URIRef(NS + "E-02#instrument_code")
    g.remove((right, URIRef(transform.ONT_IS_IDENTIFIER), None))
    g.add((wrong, URIRef(transform.ONT_IS_IDENTIFIER), Literal("true", datatype=XSD.boolean)))
    found = defects(source_graph, g, built[0].rows)
    assert any("not its declared key" in d for d in found), found


def test_an_inherited_identifier_that_is_not_the_ancestors_key_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    p = URIRef(PG + "key/PB-01_instrument_code")
    g.remove((p, RDFS.label, None))
    g.add((p, RDFS.label, Literal("something_else")))
    found = defects(source_graph, g, built[0].rows)
    assert any("not the key inherited from its ancestor" in d for d in found), found


# --- cardinalities and duplicate foreign keys (the generator's own gate covers them) ---------------

def test_an_unflipped_inverse_cardinality_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    p = URIRef(NS + "manages")
    g.remove((p, URIRef(transform.ONT_CARDINALITY), None))
    g.add((p, URIRef(transform.ONT_CARDINALITY), Literal("many-to-one")))    # should be one-to-many
    found = defects(source_graph, g, built[0].rows)
    assert any("not flips of each other" in d for d in found), found


def test_a_foreign_key_drawn_next_to_its_verb_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    col = URIRef(NS + "E-02#manager_id")
    g.add((col, RDFS.domain, URIRef(NS + "E-02")))
    g.add((col, RDFS.range, URIRef(NS + "E-01")))
    g.add((col, URIRef(transform.ONT_CARDINALITY), Literal("many-to-one")))
    found = defects(source_graph, g, built[0].rows)
    assert any("its row says it is not drawn" in d and str(col) in d for d in found), found


def test_a_not_drawn_foreign_key_with_no_verb_twin_is_caught(source_graph, out_graph, built):
    rows = [copy.copy(r) for r in built[0].rows]
    victim = next(r for r in rows if r.source_iri == NS + "PM-10#plan_id")
    victim.shown, victim.objects, victim.target_iri, victim.reason = "no", 0, "", "claimed duplicate"
    victim.rules = ["relationship-duplicate-dropped"]
    found = defects(source_graph, out_graph, rows)
    assert any("no relation verb draws" in d for d in found), found


def test_a_relationship_label_that_is_not_snake_case_is_caught(source_graph, out_graph, built):
    g = mutable_copy(out_graph)
    p = URIRef(NS + "managed-by")
    g.remove((p, RDFS.label, None))
    g.add((p, RDFS.label, Literal("Managed By")))
    assert any("not lower snake_case" in d for d in defects(source_graph, g, built[0].rows))
