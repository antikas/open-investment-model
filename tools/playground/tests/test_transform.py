"""The transform's rules, on the mini source ontology."""
from __future__ import annotations

import re

import pytest
from rdflib import Literal, URIRef
from rdflib.query import ResultRow
from rdflib.namespace import OWL, RDFS, XSD

from playground import transform, verify
from playground.tests.mini import NS, PG


def row(result, code_or_iri):
    key = code_or_iri if code_or_iri.startswith("http") else NS + code_or_iri
    return next(r for r in result.rows if r.source_iri == key)


def triples(result, s=None, p=None):
    return [(a, b, c) for (a, b, c) in result.triples if (s is None or a == s) and (p is None or b == p)]


# --- the mapping accounts for every named source construct -----------------

def test_one_row_per_named_class_object_property_and_datatype_property(source_graph, result):
    # counted here from the source graph with SPARQL, not from the transform
    def count(t):
        q = f"SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {{ ?s a <{t}> . FILTER(isIRI(?s)) }}"
        row = next(iter(source_graph.query(q)))
        assert isinstance(row, ResultRow), "a SELECT query returns result rows"
        return int(str(row[0]))
    expected = {"class": count(OWL.Class), "object_property": count(OWL.ObjectProperty),
                "datatype_property": count(OWL.DatatypeProperty)}
    got = {k: sum(1 for r in result.rows if r.kind == k) for k in expected}
    assert got == expected
    assert len({r.source_iri for r in result.rows}) == len(result.rows) == sum(expected.values())
    assert verify.check_mapping(source_graph, result.rows) == []


def test_every_construct_not_drawn_one_to_one_has_a_reason(result):
    for r in result.rows:
        if r.shown in ("no", "expanded"):
            assert r.reason.strip(), r.source_iri


# --- entities -----------------------------------------------------------------

def test_entity_names_are_unique_short_and_in_the_character_set(result):
    names = {r.openim_code: r.target_name for r in result.rows if r.kind == "class"}
    assert len({n.lower() for n in names.values()}) == len(names)
    for n in names.values():
        assert re.fullmatch(r"[A-Za-z0-9_]{1,26}", n), n
    assert names["E-01"] == "LegalEntity"
    assert names["E-02"] == "InstrumentAsset"
    assert names["FO-12"] == "ETFAPAgreement"                       # still names the agreement, not the party
    assert names["FO-11"] == "ETFCreationBasket"                    # parenthetical gloss dropped
    r = row(result, "FO-12")
    assert "hyphenated words reduced to initials" in r.reason and "ETF Authorised-Participant Agreement" in r.reason


def test_same_title_gets_a_distinct_name(result):
    names = {r.openim_code: r.target_name for r in result.rows if r.kind == "class"}
    assert {names["E-05"], names["PB-03"]} == {"Order", "Order_2"}


def test_every_entity_description_carries_its_openim_code(result):
    for r in result.rows:
        if r.kind == "class":
            (desc,) = [o for (_, _, o) in triples(result, URIRef(r.source_iri), RDFS.comment)]
            assert str(desc).startswith(r.openim_code + " "), (r.openim_code, desc)


def test_entities_are_coloured_by_code_prefix(result):
    colours = {str(s).rsplit("/", 1)[-1]: str(o) for s, p, o in result.triples if p == transform.ONT_COLOR}
    assert colours["E-01"] == transform.PREFIX_COLOUR["E"]
    assert colours["PB-01"] == transform.PREFIX_COLOUR["PB"]
    assert colours["FO-12"] == transform.PREFIX_COLOUR["FO"]


# --- datatype properties ---------------------------------------------------------

def test_long_property_names_are_shortened_within_the_limit_and_keep_the_source_name(result):
    r = row(result, NS + "FO-12#required_probability_of_success")
    assert r.target_name == "required_prob_success"        # "of" dropped, probability abbreviated
    assert len(r.target_name) <= 26
    (comment,) = [o for (_, _, o) in triples(result, URIRef(r.source_iri), RDFS.comment)]
    assert "Source name: required_probability_of_success." in str(comment)
    assert "property-name-shorten" in r.rules


def test_a_name_with_two_types_is_widened_to_string_everywhere(result):
    ranges = {str(s).rsplit("#", 1)[0].rsplit("/", 1)[-1]: o for s, p, o in result.triples
              if p == RDFS.range and str(s).endswith("#version")}
    assert ranges == {"PM-10": XSD.string, "E-33": XSD.string}
    assert "property-type-widen" in row(result, NS + "PM-10#version").rules
    assert "property-type-widen" not in row(result, NS + "E-33#version").rules


def test_a_literal_range_is_typed_string_explicitly(result):
    p = URIRef(NS + "E-33#goal_set")
    assert (p, transform.ONT_PROPERTY_TYPE, Literal("string")) in result.triples


def test_every_entity_has_identifiers_of_string_or_integer_type_and_a_composite_key_marks_every_column(result, built):
    view = verify.playground_view(result.graph())
    for e in view["entities"].values():
        ids = [p for p in e["properties"] if p["identifier"]]
        assert ids, e["name"]
        assert all(p["type"] in ("string", "integer") for p in ids)
    terms = next(e for e in view["entities"].values() if e["name"] == "FundTerms")
    # PM-10 declares the two-column key (terms_id, hurdle_id): both are identifiers,
    # written first and in key order (the Playground's Fabric export takes the first)
    assert {p["name"] for p in terms["properties"] if p["identifier"]} == {"terms_id", "hurdle_id"}
    # in the written file the key columns lead their entity, in key order
    text = built[1]
    first_terms = text.index('rdf:about="' + NS + 'PM-10#terms_id"')
    first_hurdle = text.index('rdf:about="' + NS + 'PM-10#hurdle_id"')
    other = [text.index('rdf:about="' + NS + "PM-10#" + n + '"') for n in ("version",) if ('PM-10#' + n) in text]
    assert first_terms < first_hurdle and all(first_hurdle < o for o in other)
    single = next(e for e in view["entities"].values() if e["name"] == "LegalEntity")
    assert len([p for p in single["properties"] if p["identifier"]]) == 1
    # the composite columns say so in the mapping
    r = row(result, NS + "PM-10#hurdle_id")
    assert "column 2 of the entity's 2-column declared key (terms_id, hurdle_id)" in r.reason
    assert "identifier-key" in r.rules


def test_identifier_is_the_key_the_model_declares_not_one_guessed_from_names(result):
    ident = {}
    for s_, p_, _o in result.triples:
        if p_ == transform.ONT_IS_IDENTIFIER and "#" in str(s_):
            ident.setdefault(str(s_).rsplit("/", 1)[-1].split("#")[0], set()).add(str(s_).split("#")[1])
    assert ident["E-02"] == {"instrument_code"}        # declared key; instrument_id is a decoy a name rule would pick
    assert ident["FO-12"] == {"ap_agreement_id"}
    assert ident["PM-10"] == {"terms_id", "hurdle_id"}  # a composite key marks every column
    assert "identifier-key" in row(result, NS + "E-02#instrument_code").rules
    assert "identifier-key" not in row(result, NS + "E-02#instrument_id").rules


def test_an_entity_whose_key_is_a_foreign_key_inherits_its_ancestors_key(result):
    r = row(result, "PB-01")
    assert "identifier-inherited" in r.rules and r.objects == 2
    new_prop = r.target_iri.split(";")[1]
    assert new_prop == PG + "key/PB-01_instrument_code"
    p = URIRef(new_prop)
    assert (p, RDFS.label, Literal("instrument_code")) in result.triples
    assert (p, RDFS.domain, URIRef(NS + "PB-01")) in result.triples
    assert (p, RDFS.range, XSD.string) in result.triples
    assert (p, transform.ONT_IS_IDENTIFIER, Literal("true", datatype=XSD.boolean)) in result.triples
    (comment,) = [o for (_, _, o) in triples(result, p, RDFS.comment)]
    assert str(comment).startswith("Inherited key:") and "E-02" in str(comment)
    # no name-based fallback remains
    assert not any("fallback" in rule for rule in transform.RULES)
    # the added property is counted
    assert result.stats["properties"] == sum(1 for r2 in result.rows if r2.kind == "datatype_property") + 1


# --- relationships -------------------------------------------------------------------

def test_a_foreign_key_that_duplicates_its_verb_is_not_drawn_and_names_the_verb(result):
    for col in ("E-02#issuer_entity_id", "E-05#issuer_entity_id", "E-02#manager_id"):
        r = row(result, NS + col)
        assert r.shown == "no" and r.objects == 0 and r.target_iri == "", col
        assert "relationship-duplicate-dropped" in r.rules
        assert "duplicates the relation verb" in r.reason
    assert "'issued_by'" in row(result, NS + "E-02#issuer_entity_id").reason
    assert "'managed_by'" in row(result, NS + "E-02#manager_id").reason
    # the column keeps its canonical IRI, label and description, without a domain or range
    col = URIRef(NS + "E-02#manager_id")
    assert triples(result, col, RDFS.domain) == [] and triples(result, col, RDFS.range) == []
    assert triples(result, col, RDFS.label) != []


def test_a_foreign_key_with_no_verb_is_drawn_under_a_unique_adaptation_identifier(result):
    r = row(result, NS + "PM-10#plan_id")
    assert r.shown == "yes" and r.target_iri == PG + "PM-10_plan_id"
    ids = [verify._local(x["iri"]) for x in verify.playground_view(result.graph())["relationships"]]
    assert len(ids) == len(set(ids))


def test_every_term_the_adaptation_mints_is_in_its_own_namespace(result, provenance):
    source_subjects = {t[0] for t in result.source_triples}
    minted = {t[0] for t in result.triples if t[0] not in source_subjects}
    allowed = {URIRef(transform.ADAPTATION_IRI), URIRef(provenance.source_url)}
    outside = {str(m) for m in minted if m not in allowed and not str(m).startswith(PG)}
    assert outside == set()
    assert any(str(m).startswith(PG) for m in minted)


def test_the_drawn_relationship_count_and_inverse_count_are_in_the_stats(result):
    view = verify.playground_view(result.graph())
    assert result.stats["relationships"] == len(view["relationships"])
    g = result.graph()
    paired = {x["iri"] for x in view["relationships"] if list(g.objects(URIRef(x["iri"]), OWL.inverseOf))}
    assert result.stats["relationships_with_inverse"] == len(paired)
    assert paired and len(paired) < len(view["relationships"])      # the foreign key with no verb has none


def test_relationship_labels_are_not_shortened(result):
    r = row(result, NS + "clearing-relationship-covers")
    assert r.target_name == "clearing_relationship_covers" and len(r.target_name) > transform.NAME_MAX
    assert row(result, NS + "covered-by-clearing-relationship").target_name == "covered_by_clearing_relationship"


def test_cardinality_comes_from_the_verb_and_flips_for_the_inverse(result):
    card = {s: str(o) for s, p, o in result.triples if p == transform.ONT_CARDINALITY}
    assert card[URIRef(NS + "managed-by")] == "many-to-one"
    assert card[URIRef(NS + "manages")] == "one-to-many"
    assert card[URIRef(PG + "PM-10_plan_id")] == "many-to-one"       # no verb: foreign-key default


def test_a_verb_over_a_union_is_drawn_once_per_member_pair(result):
    r = row(result, NS + "issued-by")
    assert r.shown == "expanded" and r.objects == 2
    assert set(r.target_iri.split(";")) == {PG + "issued-by_E-02_E-01", PG + "issued-by_E-05_E-01"}
    assert triples(result, URIRef(NS + "issued-by"), RDFS.domain) == []     # the parent is not drawn
    child = URIRef(PG + "issued-by_E-05_E-01")
    assert (child, RDFS.domain, URIRef(NS + "E-05")) in result.triples
    assert (child, RDFS.range, URIRef(NS + "E-01")) in result.triples
    assert (child, RDFS.subPropertyOf, URIRef(NS + "issued-by")) in result.triples


def test_inverse_pairs_survive_pair_by_pair(result):
    assert (URIRef(PG + "issued-by_E-05_E-01"), OWL.inverseOf, URIRef(PG + "issuer-of_E-01_E-05")) in result.triples
    assert (URIRef(PG + "issuer-of_E-01_E-05"), OWL.inverseOf, URIRef(PG + "issued-by_E-05_E-01")) in result.triples
    # a verb between one pair of classes is kept as it is, with its source inverseOf
    assert (URIRef(NS + "managed-by"), OWL.inverseOf, URIRef(NS + "manages")) in result.triples


def test_a_union_by_union_verb_is_drawn_only_for_the_pairs_the_source_states(result):
    r = row(result, NS + "specialises")
    assert set(r.target_iri.split(";")) == {PG + "specialises_PB-01_E-02", PG + "specialises_FO-12_E-01"}
    assert "union-pairs-from-subclass" in r.rules
    inv = row(result, NS + "specialised-by")
    assert set(inv.target_iri.split(";")) == {PG + "specialised-by_E-02_PB-01", PG + "specialised-by_E-01_FO-12"}


def test_a_union_by_union_verb_with_no_evidence_is_not_drawn_and_says_why(result):
    for name in ("linked-to", "linked-from"):
        r = row(result, NS + name)
        assert r.shown == "no" and r.objects == 0 and r.target_iri == ""
        assert "no pair" in r.reason and "union-drop" in r.rules


def test_relationship_labels_are_lower_snake_case(result):
    for rel in verify.playground_view(result.graph())["relationships"]:
        assert re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", rel["name"]), rel


def test_domains_and_ranges_of_drawn_relationships_are_single_classes_of_the_ontology(result):
    view = verify.playground_view(result.graph())
    classes = set(view["entities"])
    for rel in view["relationships"]:
        assert rel["from_iri"] in classes and rel["to_iri"] in classes


# --- provenance ---------------------------------------------------------------------------

def test_header_names_the_source_release_file_and_digest(result, provenance):
    g = result.graph()
    onto = URIRef(transform.ADAPTATION_IRI)
    assert (onto, OWL.versionInfo, Literal("1.2.3")) in g
    src = URIRef(provenance.source_url)
    assert provenance.source_url == "https://github.com/example/openim/raw/v1.2.3/exports/openim.rdf"
    assert (onto, transform.PROV_WAS_DERIVED_FROM, src) in g
    assert (onto, transform.DCTERMS_SOURCE, src) in g
    assert (src, transform.SCHEMA_SHA256, Literal(provenance.source_sha256)) in g
    assert re.fullmatch(r"[0-9a-f]{64}", provenance.source_sha256)
    assert (URIRef(transform.SOURCE_ONTOLOGY_IRI), None, None) not in g


# --- every change traces to a named rule -------------------------------------------------------

def test_every_added_or_removed_triple_is_in_the_ledger_under_a_named_rule(source_graph, built):
    from rdflib import Graph
    res, rdf_text, _ = built
    out = Graph()
    out.parse(data=rdf_text, format="xml")
    src_flat, out_flat = transform.flatten(source_graph), transform.flatten(out)
    assert out_flat == res.triples
    assert verify.check_traceability(src_flat, out_flat, res.ledger, transform.RULES) == []
    assert (out_flat - src_flat) and (src_flat - out_flat)
    used = {rule for rule, _, _ in res.ledger}
    assert used <= set(transform.RULES)


def test_the_output_has_no_build_identifiers(built):
    for text in (built[1], built[2]):
        assert not re.search(r"OIM[-]\d|ADR[-]\d|cycle[-]\d", text)


# --- property-name shortening keeps the meaning -----------------------------------------------

@pytest.mark.parametrize("source_name,expected", [
    ("authority_verification_note", "authority_verif_note"),
    ("basket_leg_settlement_status", "basket_leg_settle_status"),
    ("contractual_settlement_date", "contractual_settle_date"),
    ("creation_redemption_order_id", "creation_redeem_order_id"),
    ("goal_progress_measurement_id", "goal_progress_measure_id"),
    ("look_through_arrangement_ref", "look_through_arrgmt_ref"),
    ("pre_trade_compliance_status", "pre_trade_compl_status"),
    ("recommended_commitment_amount", "rec_commitment_amount"),
    ("redemption_fee_basis_points", "redemption_fee_bps"),
    ("required_probability_of_success", "required_prob_success"),
    ("sfdr_article_classification", "sfdr_article_classif"),
    ("taxonomy_alignment_percentage", "taxonomy_alignment_pct"),
    ("trading_limit_creation_units", "trading_limit_create_units"),
    ("units_leg_settlement_status", "units_leg_settle_status"),
    ("wash_sale_adjustment_amount", "wash_sale_adj_amount"),
])
def test_long_property_names_are_abbreviated_not_cut(source_name, expected):
    short = transform.shorten_snake(source_name)
    assert short == expected and len(short) <= transform.NAME_MAX
    if source_name.endswith("_id"):
        assert short.endswith("_id")          # an identifier never loses its _id


def test_a_name_no_abbreviation_fits_still_keeps_its_id_suffix():
    short = transform.shorten_snake("a" + "bcdfghjklm" * 4 + "_id")
    assert len(short) <= transform.NAME_MAX and short.endswith("_id")


@pytest.mark.parametrize("title,expected", [
    ("Legal Entity", "LegalEntity"),
    ("Margin & Collateral Balance", "MarginCollateralBalance"),
    ("ETF Creation/Redemption Order", "ETFCreationRedemptionOrder"),
    ("ETF Authorised-Participant Agreement", "ETFAPAgreement"),
    ("Classification Type & Value", "ClassificationTypeValue"),
    ("Service-Provider Appointment", "ServiceProviderAppointment"),
    ("Deal / Investment Opportunity", "DealInvestmentOpportunity"),
    ("Master Agreement & Collateral Terms", "MasterAgmtCollateralTerms"),
    ("ETF Creation Basket (Portfolio Composition File)", "ETFCreationBasket"),
])
def test_long_entity_titles_are_abbreviated_with_their_meaning_kept(title, expected):
    name, steps = transform.entity_name_for(title)
    assert name == expected and len(name) <= transform.NAME_MAX
    assert bool(steps) == (len(re.sub(r"[^A-Za-z0-9]", "", title)) > transform.NAME_MAX)


def test_a_title_no_step_can_fit_is_cut_by_dropping_words_and_says_so():
    name, steps = transform.entity_name_for("Alpha Bravo Charlie Delta Echo Foxtrot Golf")
    assert len(name) <= transform.NAME_MAX and name.startswith("AlphaBravo")
    assert any("dropped" in x for x in steps)


def test_an_inherited_composite_key_is_written_in_key_order_not_alphabetical_order(source_graph, provenance):
    """A specialisation of PM-10 (key terms_id, hurdle_id) whose own key is a foreign
    key inherits both columns; `hurdle_id` sorts before `terms_id`, key order is the reverse."""
    from rdflib import Graph
    from playground import rdfxml
    from playground.tests.mini import KEY_POSITION, Builder
    b = Builder()
    for t in source_graph:
        b.g.add(t)
    b.cls("PM-11", "Hurdle Detail", "A detail.", parent="PM-10")
    b.column("PM-11", "terms_id", "PM-10", key=1)
    b.dp("PM-11", "detail_note")
    res = transform.transform(b.g, provenance)
    row_ = row(res, "PM-11")
    assert "identifier-inherited" in row_.rules and row_.objects == 3
    added = row_.target_iri.split(";")[1:]
    assert sorted(added) == [PG + "key/PM-11_hurdle_id", PG + "key/PM-11_terms_id"]
    text = rdfxml.write(res.triples)
    assert text.index(PG + "key/PM-11_terms_id") < text.index(PG + "key/PM-11_hurdle_id")        # key order
    assert (URIRef(PG + "key/PM-11_terms_id"), KEY_POSITION, Literal(1)) in res.triples
    assert (URIRef(PG + "key/PM-11_hurdle_id"), KEY_POSITION, Literal(2)) in res.triples
    out = Graph()
    out.parse(data=text, format="xml")
    assert verify.verify_all(b.g, out, res.rows) == []
