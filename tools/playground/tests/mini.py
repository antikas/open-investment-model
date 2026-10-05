"""A small source ontology in the shape of the released OpenIM ontology, built
in memory, with one example of every construct the adaptation has a rule for."""
from __future__ import annotations

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, XSD

NS = "https://w3id.org/openim/ontology/"
PG = NS + "playground/"        # where the adaptation mints its own terms
FIBO = "https://spec.edmcouncil.org/fibo/ontology/"
KEY_POSITION = URIRef(NS + "keyPosition")


def iri(code: str) -> URIRef:
    return URIRef(NS + code)


class Builder:
    def __init__(self) -> None:
        self.g = Graph()
        self.g.add((URIRef(NS.rstrip("/")), RDF.type, OWL.Ontology))
        self.g.add((URIRef(NS.rstrip("/")), RDFS.label, Literal("OpenIM canonical entity ontology")))
        self.g.add((URIRef(NS.rstrip("/")), OWL.versionInfo, Literal("0.2.0")))

    def cls(self, code: str, title: str, summary: str = "", parent: str | None = None, fibo: str | None = None):
        c = iri(code)
        self.g.add((c, RDF.type, OWL.Class))
        self.g.add((c, RDFS.label, Literal(f"{code} {title}")))
        if summary:
            self.g.add((c, RDFS.comment, Literal(summary)))
        if parent:
            self.g.add((c, RDFS.subClassOf, iri(parent)))
        if fibo:
            self.g.add((c, OWL.equivalentClass, URIRef(FIBO + fibo)))
        return c

    def dp(self, code: str, name: str, xsd=XSD.string, declared: str = "varchar", key: int | None = None):
        p = URIRef(f"{NS}{code}#{name}")
        if key:
            self.g.add((p, KEY_POSITION, Literal(key)))
        self.g.add((p, RDF.type, OWL.DatatypeProperty))
        self.g.add((p, RDFS.label, Literal(name)))
        self.g.add((p, RDFS.comment, Literal(f"Declared type: {declared}.")))
        self.g.add((p, RDFS.domain, iri(code)))
        self.g.add((p, RDFS.range, xsd))
        return p

    def _side(self, codes):
        if len(codes) == 1:
            return iri(codes[0])
        node = BNode()
        lst = BNode()
        Collection(self.g, lst, [iri(c) for c in codes])
        self.g.add((node, RDF.type, OWL.Class))
        self.g.add((node, OWL.unionOf, lst))
        return node

    def verb(self, name: str, label: str, domain, range_, comment: str, inverse: str | None = None):
        v = URIRef(NS + name)
        self.g.add((v, RDF.type, OWL.ObjectProperty))
        self.g.add((v, RDFS.label, Literal(label)))
        self.g.add((v, RDFS.comment, Literal(comment)))
        self.g.add((v, RDFS.domain, self._side(domain)))
        self.g.add((v, RDFS.range, self._side(range_)))
        if inverse:
            self.g.add((v, OWL.inverseOf, URIRef(NS + inverse)))
        return v

    def column(self, owner: str, name: str, target: str, verb: str | None = None, declared: str = "varchar",
               key: int | None = None):
        p = URIRef(f"{NS}{owner}#{name}")
        if key:
            self.g.add((p, KEY_POSITION, Literal(key)))
        self.g.add((p, RDF.type, OWL.ObjectProperty))
        self.g.add((p, RDFS.label, Literal(name)))
        self.g.add((p, RDFS.comment, Literal(f"Declared type: {declared} (FK \u2192 {target}).")))
        self.g.add((p, RDFS.domain, iri(owner)))
        self.g.add((p, RDFS.range, iri(target)))
        if verb:
            self.g.add((p, RDFS.subPropertyOf, URIRef(NS + verb)))
        return p


def forward_comment(kind: str, card: str, inverse_lpg: str) -> str:
    return f"OpenIM relation verb \u2014 {kind}, {card}. Inverse: {inverse_lpg}."


def inverse_comment(forward: str, kind: str, card: str) -> str:
    return f"Inverse of openim:{forward} ({kind}, {card})."


def build_mini() -> Graph:
    b = Builder()
    b.cls("E-01", "Legal Entity", "A person or organisation.", fibo="fbc/LegalEntity")
    b.cls("E-02", "Instrument / Asset", "A financial instrument.")
    b.cls("E-05", "Order", "An order record.")
    b.cls("PB-03", "Order", "A public-markets order.")
    b.cls("PB-01", "Listed Equity", "A listed share.", parent="E-02")
    b.cls("FO-12", "ETF Authorised-Participant Agreement", "The standing AP agreement.", parent="E-01")
    b.cls("FO-11", "ETF Creation Basket (Portfolio Composition File)", "The creation basket.")
    b.cls("PM-10", "Fund Terms", "The terms of a fund.")
    b.cls("E-33", "Financial Plan", "A plan.")

    b.dp("E-01", "entity_id", key=1); b.dp("E-01", "entity_name"); b.dp("E-01", "parent_entity_id")
    b.dp("E-02", "instrument_code", key=1); b.dp("E-02", "instrument_id"); b.dp("E-02", "instrument_name")
    b.dp("E-05", "order_id", key=1); b.dp("E-05", "quantity", XSD.decimal, "decimal")
    b.dp("PB-03", "order_id", key=1); b.dp("PB-03", "quantity", XSD.decimal, "decimal")
    b.dp("PB-01", "share_class"); b.dp("PB-01", "primary_listing_mic")
    b.dp("FO-12", "ap_agreement_id", key=1); b.dp("FO-12", "authority_verification_note")
    b.dp("FO-12", "creation_redemption_order_id"); b.dp("FO-12", "required_probability_of_success")
    b.dp("FO-11", "basket_id", key=1)
    b.dp("PM-10", "terms_id", key=1); b.dp("PM-10", "hurdle_id", key=2); b.dp("PM-10", "version", XSD.integer, "int")
    b.dp("E-33", "financial_plan_id", key=1); b.dp("E-33", "version")
    b.dp("E-33", "goal_set", RDFS.Literal, "array")

    # a verb over a union domain, its per-column foreign keys, and its inverse
    b.verb("issued-by", "ISSUED_BY", ["E-02", "E-05"], ["E-01"], forward_comment("role", "n-to-1", "ISSUER_OF"), "issuer-of")
    b.verb("issuer-of", "ISSUER_OF", ["E-01"], ["E-02", "E-05"], inverse_comment("issued-by", "role", "n-to-1"), "issued-by")
    b.column("E-02", "issuer_entity_id", "E-01", "issued-by")
    b.column("E-05", "issuer_entity_id", "E-01", "issued-by")
    # a verb between one pair of classes
    b.verb("managed-by", "MANAGED_BY", ["E-02"], ["E-01"], forward_comment("role", "n-to-1", "MANAGES"), "manages")
    b.verb("manages", "MANAGES", ["E-01"], ["E-02"], inverse_comment("managed-by", "role", "n-to-1"), "managed-by")
    b.column("E-02", "manager_id", "E-01", "managed-by")
    # specialisation: union domain and union range, evidence in rdfs:subClassOf
    b.verb("specialises", "SPECIALISES", ["PB-01", "FO-12"], ["E-02", "E-01"], forward_comment("is-a", "n-to-n", "SPECIALISED_BY"), "specialised-by")
    b.verb("specialised-by", "SPECIALISED_BY", ["E-02", "E-01"], ["PB-01", "FO-12"], inverse_comment("specialises", "is-a", "n-to-n"), "specialises")
    # union on both sides with no evidence for any pair
    b.verb("linked-to", "LINKED_TO", ["E-01", "E-02"], ["E-05", "PB-03"], forward_comment("reference", "1-to-n", "LINKED_FROM"), "linked-from")
    b.verb("linked-from", "LINKED_FROM", ["E-05", "PB-03"], ["E-01", "E-02"], inverse_comment("linked-to", "reference", "1-to-n"), "linked-to")
    # a specialisation whose declared key is a foreign key to its parent
    b.column("PB-01", "instrument_id", "E-02", key=1)
    # a simple verb whose label is longer than a property name may be
    b.verb("clearing-relationship-covers", "CLEARING_RELATIONSHIP_COVERS", ["E-01"], ["E-05"],
           forward_comment("reference", "1-to-n", "COVERED_BY_CLEARING_RELATIONSHIP"), "covered-by-clearing-relationship")
    b.verb("covered-by-clearing-relationship", "COVERED_BY_CLEARING_RELATIONSHIP", ["E-05"], ["E-01"],
           inverse_comment("clearing-relationship-covers", "reference", "1-to-n"), "clearing-relationship-covers")
    # a foreign key with no verb
    b.column("PM-10", "plan_id", "E-33")
    return b.g
