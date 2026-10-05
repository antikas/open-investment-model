"""Independent checks on a Playground adaptation.

The checks read the source ontology and the written output as plain RDF graphs
and the mapping as plain rows. They do not use the transform's internals: the
Playground's naming limits and its reading of an ontology are restated here, from
the Playground's own code (`src/store/designerStore.ts`, `src/lib/rdf/parser.ts`),
so a defect in the transform cannot hide behind the same mistake in the checks.

Every function returns a list of defect strings (empty when clean).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from rdflib import BNode, Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

# designerStore.ts:23 - 1-26 characters, letters digits hyphen underscore,
# starting and ending with a letter or digit.
_NAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9_-]{0,24}[A-Za-z0-9])?$")
# parser.ts:104-115
_XSD_TO_TYPE = {"string": "string", "integer": "integer", "int": "integer", "long": "integer",
                "decimal": "decimal", "float": "decimal", "double": "double", "date": "date",
                "dateTime": "datetime", "boolean": "boolean"}
_CARDINALITIES = {"one-to-one", "one-to-many", "many-to-one", "many-to-many"}
_FLIP = {"many-to-one": "one-to-many", "one-to-many": "many-to-one",
         "many-to-many": "many-to-many", "one-to-one": "one-to-one"}
# The Playground sets no length limit on a relationship name (validateOntology,
# designerStore.ts:106-127, checks only identifiers and endpoints); the adaptation
# keeps relationship labels lower snake_case at their full length.
_REL_LABEL_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def _local(iri) -> str:
    s = str(iri)
    if "#" in s:
        return s[s.rfind("#") + 1:]
    if "/" in s:
        return s[s.rfind("/") + 1:]
    return s


def _ont(g: Graph, s, suffix: str):
    """The value of the annotation whose IRI ends in `suffix` (the parser matches
    annotation elements by local name only, parser.ts:32-40)."""
    for p, o in g.predicate_objects(s):
        if str(p).endswith("#" + suffix) or str(p).endswith("/" + suffix):
            return str(o)
    return None


def inventory(source: Graph) -> dict:
    """The named classes, object properties and datatype properties of a source
    graph, counted directly from `rdf:type` (not from any transform output)."""
    def named(t):
        return sorted({s for s in source.subjects(RDF.type, t) if isinstance(s, URIRef)}, key=str)
    return {"class": named(OWL.Class), "object_property": named(OWL.ObjectProperty),
            "datatype_property": named(OWL.DatatypeProperty)}


def playground_view(g: Graph) -> dict:
    """What the Playground parser would build from `g` (parser.ts:145-366)."""
    entities = {}
    for c in sorted({s for s in g.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)}, key=str):
        label = g.value(c, RDFS.label)
        comment = g.value(c, RDFS.comment)
        eid = _local(c)[:1].lower() + _local(c)[1:]
        entities[str(c)] = {"id": eid, "name": str(label) if label is not None else _local(c),
                            "description": str(comment) if comment is not None else "", "properties": []}
    for p in sorted({s for s in g.subjects(RDF.type, OWL.DatatypeProperty) if isinstance(s, URIRef)}, key=str):
        d = g.value(p, RDFS.domain)
        if not isinstance(d, URIRef) or str(d) not in entities:
            continue
        r = g.value(p, RDFS.range)
        t = _XSD_TO_TYPE.get(_local(r), "string") if isinstance(r, URIRef) else "string"
        pt = _ont(g, p, "propertyType")
        if pt in ("string", "integer", "decimal", "double", "date", "datetime", "boolean", "enum"):
            t = pt
        label = g.value(p, RDFS.label)
        entities[str(d)]["properties"].append({
            "iri": str(p), "name": str(label) if label is not None else _local(p), "type": t,
            "identifier": _ont(g, p, "isIdentifier") == "true"})
    relationships = []
    for p in sorted({s for s in g.subjects(RDF.type, OWL.ObjectProperty) if isinstance(s, URIRef)}, key=str):
        d, r = g.value(p, RDFS.domain), g.value(p, RDFS.range)
        if not isinstance(d, URIRef) or not isinstance(r, URIRef):
            continue    # parser.ts:318-319: an unresolved domain or range is skipped
        label = g.value(p, RDFS.label)
        relationships.append({
            "iri": str(p), "id": _local(p), "name": str(label) if label is not None else _local(p),
            "from": _local(d)[:1].lower() + _local(d)[1:], "to": _local(r)[:1].lower() + _local(r)[1:],
            "from_iri": str(d), "to_iri": str(r), "cardinality": _ont(g, p, "cardinality")})
    return {"entities": entities, "relationships": relationships}


def check_playground_rules(view: dict) -> list[str]:
    """The Playground's own validation (`validateOntology`, designerStore.ts:38-125)
    plus the uniqueness the adaptation promises."""
    defects = []
    entities = view["entities"]
    if not entities:
        defects.append("no entity types")
    seen_ids, seen_names = {}, {}
    type_by_name: dict = {}
    for iri, e in entities.items():
        if not e["name"]:
            defects.append(f"entity {iri} has no name")
        elif not _NAME_RE.match(e["name"]):
            defects.append(f"entity name {e['name']!r} ({iri}) breaks the Playground's name rule "
                           f"(1-26 characters of letters, digits, hyphen, underscore)")
        if e["id"] in seen_ids:
            defects.append(f"entity id {e['id']!r} is used by {seen_ids[e['id']]} and {iri}")
        seen_ids[e["id"]] = iri
        folded = e["name"].lower()
        if folded in seen_names:
            defects.append(f"entity name collision: {e['name']!r} is the name of {seen_names[folded]} and {iri}")
        seen_names[folded] = iri
        ids = [p for p in e["properties"] if p["identifier"]]
        if not ids:
            defects.append(f"entity {e['name']!r} ({iri}) has no identifier property")
        for p in ids:
            if p["type"] not in ("string", "integer"):
                defects.append(f"identifier {p['name']!r} of {e['name']!r} is {p['type']}, not string or integer")
        names = Counter(p["name"] for p in e["properties"])
        for p in e["properties"]:
            if not _NAME_RE.match(p["name"]):
                defects.append(f"property name {p['name']!r} of {e['name']!r} breaks the Playground's name rule")
            if names[p["name"]] > 1:
                defects.append(f"property name {p['name']!r} is repeated in {e['name']!r}")
            prior = type_by_name.setdefault(p["name"], (p["type"], e["name"]))
            if prior[0] != p["type"]:
                defects.append(f"property {p['name']!r} is {p['type']} in {e['name']!r} but {prior[0]} in {prior[1]!r}")
    by_id = {e["id"] for e in entities.values()}
    rel_ids = Counter(r["id"] for r in view["relationships"])
    triple_seen = Counter((r["from"], r["name"], r["to"]) for r in view["relationships"])
    for r in view["relationships"]:
        if rel_ids[r["id"]] > 1:
            defects.append(f"relationship id {r['id']!r} is used more than once")
        if r["from"] not in by_id or r["to"] not in by_id:
            defects.append(f"relationship {r['iri']} points to an entity that does not exist")
        if not _REL_LABEL_RE.match(r["name"]):
            defects.append(f"relationship label {r['name']!r} ({r['iri']}) is not lower snake_case")
        if triple_seen[(r["from"], r["name"], r["to"])] > 1:
            defects.append(f"relationship {r['name']!r} from {r['from']} to {r['to']} is drawn more than once")
        if r["cardinality"] not in _CARDINALITIES:
            defects.append(f"relationship {r['iri']} has no valid cardinality (found {r['cardinality']!r}); "
                           f"its relation verb states none the transform can read")
    return sorted(set(defects))


def check_descriptions(out: Graph) -> list[str]:
    """Every entity description carries the entity's OpenIM code."""
    defects = []
    for c in sorted({s for s in out.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)}, key=str):
        code = _local(c)
        comment = str(out.value(c, RDFS.comment) or "")
        if not re.match(r"^" + re.escape(code) + r"\b", comment):
            defects.append(f"description of {c} does not start with its OpenIM code {code}")
    return defects


def check_inverses(out: Graph) -> list[str]:
    """An owl:inverseOf pair of drawn relationships has swapped domain and range."""
    defects = []
    drawn = {r["iri"]: r for r in playground_view(out)["relationships"]}
    for a, b in out.subject_objects(OWL.inverseOf):
        ra, rb = drawn.get(str(a)), drawn.get(str(b))
        if ra is None or rb is None:
            continue
        if ra["from_iri"] != rb["to_iri"] or ra["to_iri"] != rb["from_iri"]:
            defects.append(f"{a} and {b} are inverses but their domain and range are not swapped")
    return defects


def check_identifiers(source: Graph, out: Graph) -> list[str]:
    """Every entity's identifier is the key the model declares for it, or the
    key declared on its nearest ancestor when its own key is a foreign key.

    The model's declared key is the source annotation `keyPosition` (1 = primary
    key). Read here from the source graph, independently of the transform."""
    defects = []
    key_pos = [p for p in set(source.predicates()) if str(p).endswith("/keyPosition")]
    view = playground_view(out)
    out_by_iri = {p["iri"]: p for e in view["entities"].values() for p in e["properties"]}

    def own_keys(cls: str) -> list[str]:
        cands = []
        for p in source.subjects(RDFS.domain, URIRef(cls)):
            if (p, RDF.type, OWL.DatatypeProperty) not in source:
                continue
            for kp in key_pos:
                pos = source.value(p, kp)
                if pos is not None and str(p) in out_by_iri and out_by_iri[str(p)]["type"] in ("string", "integer"):
                    cands.append((int(str(pos)), str(p)))
        return [p for _, p in sorted(cands)]

    def ancestors(cls: str):
        seen, frontier = {cls}, [cls]
        while frontier:
            nxt = []
            for x in frontier:
                for parent in sorted(str(o) for o in source.objects(URIRef(x), RDFS.subClassOf)):
                    if parent not in seen:
                        seen.add(parent)
                        yield parent
                        nxt.append(parent)
            frontier = nxt

    for iri, ent in sorted(view["entities"].items()):
        ids = [p for p in ent["properties"] if p["identifier"]]
        if not ids:
            continue    # reported by check_playground_rules
        keys = own_keys(iri)
        if keys:
            # a composite key marks every one of its columns, and nothing else
            if {p["iri"] for p in ids} != set(keys):
                defects.append(f"identifiers of {iri} are {sorted(p['iri'] for p in ids)}, "
                               f"not its declared key {sorted(keys)}")
            continue
        parent_keys = next((own_keys(a) for a in ancestors(iri) if own_keys(a)), None)
        if parent_keys is None:
            defects.append(f"{iri} has an identifier but no declared or inherited key in the source")
        elif (sorted(p["name"] for p in ids) != sorted(out_by_iri[k]["name"] for k in parent_keys)
              or not all(str(out.value(URIRef(p["iri"]), RDFS.comment) or "").startswith("Inherited key:") for p in ids)):
            defects.append(f"identifiers of {iri} are not the key inherited from its ancestor ({parent_keys})")
    for iri in sorted(view["entities"]):
        if not own_keys(iri) and not any(own_keys(a) for a in ancestors(iri)):
            defects.append(f"entity {iri} has no declared or inherited key in the source")
    return defects


def check_every_drawn_relationship_is_mapped(out: Graph, rows: list) -> list[str]:
    """No relationship is drawn that the mapping does not name as a target, and a
    row that says 'not drawn' is not drawn."""
    defects = []
    targets = {t for r in rows if r.shown != "no" for t in r.target_iri.split(";") if t}
    not_drawn = {r.source_iri for r in rows if r.shown == "no"}
    for rel in playground_view(out)["relationships"]:
        if rel["iri"] not in targets:
            defects.append(f"relationship {rel['iri']} is drawn but no mapping row names it"
                           + (" (its row says it is not drawn)" if rel["iri"] in not_drawn else ""))
    return defects


def check_inverse_cardinalities(out: Graph) -> list[str]:
    """The cardinalities of an inverse pair of drawn relationships are flips of
    each other (many-to-one against one-to-many)."""
    defects = []
    drawn = {r["iri"]: r for r in playground_view(out)["relationships"]}
    for a, b in out.subject_objects(OWL.inverseOf):
        ra, rb = drawn.get(str(a)), drawn.get(str(b))
        if ra is None or rb is None:
            continue
        if _FLIP.get(ra["cardinality"]) != rb["cardinality"]:
            defects.append(f"{a} ({ra['cardinality']}) and {b} ({rb['cardinality']}) are inverses "
                           f"but their cardinalities are not flips of each other")
    return defects


def check_duplicate_columns(source: Graph, out: Graph, rows: list) -> list[str]:
    """A foreign-key column is not drawn when its relation verb draws the same two
    classes, and is drawn when no verb does. Each 'not drawn' claim is checked
    against the output."""
    defects = []
    drawn = {r["iri"]: r for r in playground_view(out)["relationships"]}
    by_source = {r.source_iri: r for r in rows}
    for r in rows:
        if r.kind != "object_property" or "#" not in r.source_iri:
            continue
        src = URIRef(r.source_iri)
        dom, rng = source.value(src, RDFS.domain), source.value(src, RDFS.range)
        verb = source.value(src, RDFS.subPropertyOf)
        verb_row = by_source.get(str(verb)) if verb is not None else None
        twins = [t for t in (verb_row.target_iri.split(";") if verb_row else []) if t
                 and drawn.get(t) and drawn[t]["from_iri"] == str(dom) and drawn[t]["to_iri"] == str(rng)]
        if twins and r.shown != "no":
            defects.append(f"{r.source_iri} is drawn although its verb already draws {dom} to {rng} ({twins[0]})")
        if not twins and r.shown == "no":
            defects.append(f"{r.source_iri} is not drawn but no relation verb draws {dom} to {rng}")
        if r.shown == "no" and twins and "relationship-duplicate-dropped" not in r.rules:
            defects.append(f"{r.source_iri} is not drawn without the duplicate rule")
    return defects


def check_inverse_coverage(source: Graph, out: Graph, rows: list) -> list[str]:
    """Every inverse pair of the source survives: for each relationship drawn
    for one verb there is a relationship drawn for its inverse verb with the
    domain and range swapped, and the two are declared owl:inverseOf each other."""
    defects = []
    drawn = {r["iri"]: r for r in playground_view(out)["relationships"]}
    targets = {r.source_iri: [t for t in r.target_iri.split(";") if t] for r in rows
               if r.kind == "object_property" and r.shown != "no"}
    for v, w in source.subject_objects(OWL.inverseOf):
        if str(v) not in targets or str(w) not in targets:
            continue
        for t in targets[str(v)]:
            rel = drawn.get(t)
            if rel is None:
                continue
            partners = [u for u in targets[str(w)]
                        if drawn.get(u) and drawn[u]["from_iri"] == rel["to_iri"] and drawn[u]["to_iri"] == rel["from_iri"]]
            if not partners:
                defects.append(f"{t} (verb {v}) has no inverse drawn for {w}")
            elif not any((URIRef(t), OWL.inverseOf, URIRef(u)) in out for u in partners):
                defects.append(f"{t} is not declared owl:inverseOf its inverse")
    return defects


def check_mapping(source: Graph, rows: list) -> list[str]:
    """One row per named class, object property and datatype property of the
    source, no more and no fewer, no row twice."""
    defects = []
    inv = inventory(source)
    wanted = {kind: set(map(str, iris)) for kind, iris in inv.items()}
    by_kind = defaultdict(list)
    for r in rows:
        by_kind[r.kind].append(r.source_iri)
    for kind, iris in wanted.items():
        have = by_kind.get(kind, [])
        counts = Counter(have)
        for iri, n in counts.items():
            if n > 1:
                defects.append(f"mapping has {n} rows for {kind} {iri}")
        for iri in sorted(iris - set(have)):
            defects.append(f"mapping has no row for {kind} {iri}")
        for iri in sorted(set(have) - iris):
            defects.append(f"mapping has a row for {iri} that is not a named {kind} of the source")
    unknown = set(by_kind) - set(wanted)
    for kind in sorted(unknown):
        defects.append(f"mapping has rows of unknown kind {kind!r}")
    for r in rows:
        if r.shown not in ("yes", "expanded", "no"):
            defects.append(f"row {r.source_iri} has playground_shows {r.shown!r}")
        if r.shown in ("no", "expanded") and not r.reason.strip():
            defects.append(f"row {r.source_iri} is not drawn one-to-one and gives no reason")
        if r.shown == "no" and (r.objects or r.target_iri):
            defects.append(f"row {r.source_iri} is not shown but names a target")
        if r.shown != "no":
            targets = [t for t in r.target_iri.split(";") if t]
            if len(targets) != r.objects or not targets:
                defects.append(f"row {r.source_iri} says {r.objects} objects but names {len(targets)} targets")
    return defects


def check_output_against_mapping(source: Graph, out: Graph, rows: list) -> list[str]:
    """Every row's targets exist in the output, in the shape the row claims."""
    defects = []
    view = playground_view(out)
    drawn = {r["iri"]: r for r in view["relationships"]}
    classes = {str(s) for s in out.subjects(RDF.type, OWL.Class)}
    props = {}
    for ent in view["entities"].values():
        for p in ent["properties"]:
            props[p["iri"]] = ent
    for r in rows:
        if r.shown == "no":
            continue
        targets = [t for t in r.target_iri.split(";") if t]
        if r.kind == "class":
            own_id = view["entities"].get(r.source_iri, {}).get("id")
            for t in targets:
                if t == r.source_iri:
                    if t not in classes:
                        defects.append(f"class {r.source_iri}: target {t} is not a class of the output")
                elif props.get(t) is None or props[t]["id"] != own_id:
                    defects.append(f"class {r.source_iri}: extra target {t} is not a property of its entity")
        elif r.kind == "datatype_property":
            d = source.value(URIRef(r.source_iri), RDFS.domain)
            for t in targets:
                ent = props.get(t)
                if ent is None:
                    defects.append(f"datatype property {r.source_iri}: target {t} is not a property of any output entity")
                elif d is not None and ent["id"] != _local(d)[:1].lower() + _local(d)[1:]:
                    defects.append(f"datatype property {r.source_iri}: target {t} is on {ent['id']}, not on the source domain")
        elif r.kind == "object_property":
            src = URIRef(r.source_iri)
            d, rg = source.value(src, RDFS.domain), source.value(src, RDFS.range)
            allowed = None
            if r.shown == "yes":
                allowed = {(str(d), str(rg))} if isinstance(d, URIRef) and isinstance(rg, URIRef) else None
            for t in targets:
                rel = drawn.get(t)
                if rel is None:
                    defects.append(f"object property {r.source_iri}: relationship {t} is not drawn in the output")
                    continue
                if allowed is not None and (rel["from_iri"], rel["to_iri"]) not in allowed:
                    defects.append(f"object property {r.source_iri}: relationship {t} changed its domain or range")
                if r.shown == "expanded" and (URIRef(t), RDFS.subPropertyOf, src) not in out:
                    defects.append(f"object property {r.source_iri}: relationship {t} is not a sub-property of it")
    return sorted(set(defects))


def check_union_coverage(source: Graph, out: Graph, rows: list) -> list[str]:
    """A source object property with a union domain or range is drawn only for
    member pairs of that union."""
    from rdflib.collection import Collection
    defects = []
    drawn = {r["iri"]: r for r in playground_view(out)["relationships"]}

    def members(term):
        if isinstance(term, BNode):
            lst = source.value(term, OWL.unionOf)
            if lst is None:
                raise ValueError(f"blank node {term} is used as a domain or range but is not an owl:unionOf class")
            return {str(m) for m in Collection(source, lst)}
        return {str(term)}
    for r in rows:
        if r.kind != "object_property" or r.shown != "expanded":
            continue
        src = URIRef(r.source_iri)
        dom, rng = members(source.value(src, RDFS.domain)), members(source.value(src, RDFS.range))
        for t in (x for x in r.target_iri.split(";") if x):
            rel = drawn.get(t)
            if rel and (rel["from_iri"] not in dom or rel["to_iri"] not in rng):
                defects.append(f"{t} is drawn for a class pair outside the union of {r.source_iri}")
    return defects


def check_traceability(source_triples: set, out_triples: set, ledger: list, known_rules) -> list[str]:
    """Every triple the output adds to or removes from the source is in the
    ledger under a named rule, and the ledger lists nothing the output does not
    show."""
    defects = []
    added, removed = out_triples - source_triples, source_triples - out_triples
    led_add = {t for rule, op, t in ledger if op == "add"}
    led_rem = {t for rule, op, t in ledger if op == "remove"}
    for rule, _op, _t in ledger:
        if rule not in known_rules:
            defects.append(f"ledger names an unknown rule {rule!r}")
    for t in sorted(added - led_add, key=str)[:20]:
        defects.append(f"triple added without a rule: {t}")
    for t in sorted(removed - led_rem, key=str)[:20]:
        defects.append(f"triple removed without a rule: {t}")
    for t in sorted(led_add - added, key=str)[:20]:
        defects.append(f"ledger adds a triple the output does not contain: {t}")
    for t in sorted(led_rem - removed, key=str)[:20]:
        defects.append(f"ledger removes a triple the output still contains: {t}")
    return defects


def verify_all(source: Graph, out: Graph, rows: list) -> list[str]:
    """All the checks that need only the two graphs and the mapping."""
    defects = []
    defects += check_mapping(source, rows)
    defects += check_playground_rules(playground_view(out))
    defects += check_descriptions(out)
    defects += check_inverses(out)
    defects += check_output_against_mapping(source, out, rows)
    defects += check_union_coverage(source, out, rows)
    defects += check_inverse_coverage(source, out, rows)
    defects += check_identifiers(source, out)
    defects += check_inverse_cardinalities(out)
    defects += check_every_drawn_relationship_is_mapped(out, rows)
    defects += check_duplicate_columns(source, out, rows)
    return defects
