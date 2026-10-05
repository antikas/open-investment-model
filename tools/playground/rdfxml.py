"""A deterministic RDF/XML writer for the Playground adaptation.

The Playground reads RDF/XML with a DOM parser that matches elements by name
(`src/lib/rdf/parser.ts`). A general RDF serialiser nests one description inside
another where it can, and then the parser meets a property twice (once nested,
once at the top level). This writer instead emits a flat document: one typed
element per subject, every reference an `rdf:resource` attribute, every element
and attribute in sorted order. The same triples always give the same bytes, with
no dependence on the process, the hash seed or the library version.

The output has no blank nodes; a triple whose subject or object is a blank node
is an error.
"""
from __future__ import annotations

from rdflib import BNode, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

from .transform import DCTERMS_NS, KEY_POSITION, ONT_IS_IDENTIFIER, ONT_NS, OPENIM_NS, PROV_NS, SCHEMA_NS

# prefix -> namespace; the order is the order of the xmlns declarations.
PREFIXES = {
    "rdf": str(RDF),
    "rdfs": str(RDFS),
    "owl": str(OWL),
    "skos": str(SKOS),
    "dcterms": DCTERMS_NS,
    "prov": PROV_NS,
    "schema": SCHEMA_NS,
    "ont": ONT_NS,
    "openim": OPENIM_NS,
}

# The element a subject is written as, by its primary type, in document order.
_PRIMARY_TYPES = [
    OWL.Ontology,
    URIRef(PROV_NS + "Entity"),
    OWL.AnnotationProperty,
    OWL.Class,
    OWL.DatatypeProperty,
    OWL.ObjectProperty,
]


def _qname(iri: URIRef) -> str:
    s = str(iri)
    best = None
    for prefix, ns in PREFIXES.items():
        if s.startswith(ns) and (best is None or len(ns) > len(PREFIXES[best])):
            best = prefix
    if best is None:
        raise ValueError(f"no prefix declared for {s}")
    local = s[len(PREFIXES[best]):]
    if not local or not all(ch.isalnum() or ch in "_-." for ch in local):
        raise ValueError(f"cannot write {s} as an element name")
    return f"{best}:{local}"


def _text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _attr(value: str) -> str:
    return _text(value).replace('"', "&quot;")


def _sort_key(pair):
    p, o = pair
    return (str(p), 0 if isinstance(o, URIRef) else 1, str(o), str(getattr(o, "datatype", "") or ""))


def write(triples) -> str:
    by_subject: dict = {}
    for s, p, o in triples:
        if isinstance(s, BNode) or isinstance(o, BNode):
            raise ValueError("blank nodes are not written")
        by_subject.setdefault(s, []).append((p, o))

    def rank(s):
        types = {o for p, o in by_subject[s] if p == RDF.type}
        for i, t in enumerate(_PRIMARY_TYPES):
            if t in types:
                return i, t
        raise ValueError(f"{s} has none of the types the Playground reads")

    def order_key(s):
        r, primary = rank(s)
        if primary != OWL.DatatypeProperty:
            return (r, "", 0, 0, str(s))
        # a datatype property is written under its entity, key columns first and in key
        # order (the Playground's Fabric export takes an entity's FIRST identifier
        # property, so a composite key must lead with its first column)
        props = by_subject[s]
        domain = next((str(o) for p, o in props if p == RDFS.domain), "")
        identifier = any(p == ONT_IS_IDENTIFIER for p, _ in props)
        position = next((int(str(o)) for p, o in props if p == KEY_POSITION), 0)
        return (r, domain, 0 if identifier else 1, position, str(s))

    ordered = sorted(by_subject, key=order_key)

    out = ['<?xml version="1.0" encoding="utf-8"?>', "<rdf:RDF"]
    for prefix, ns in PREFIXES.items():
        out.append(f'  xmlns:{prefix}="{_attr(ns)}"')
    out.append(">")
    for s in ordered:
        _, primary = rank(s)
        out.append(f'  <{_qname(primary)} rdf:about="{_attr(str(s))}">')
        props = sorted(((p, o) for p, o in by_subject[s] if not (p == RDF.type and o == primary)), key=_sort_key)
        for p, o in props:
            q = _qname(p)
            if isinstance(o, URIRef):
                out.append(f'    <{q} rdf:resource="{_attr(str(o))}"/>')
            elif isinstance(o, Literal):
                if o.language:
                    raise ValueError("language-tagged literals are not written")
                dt = o.datatype
                dt_attr = f' rdf:datatype="{_attr(str(dt))}"' if dt and dt != XSD.string else ""
                out.append(f"    <{q}{dt_attr}>{_text(str(o))}</{q}>")
            else:
                raise ValueError(f"unsupported object {o!r}")
        out.append(f"  </{_qname(primary)}>")
    out.append("</rdf:RDF>")
    return "\n".join(out) + "\n"
