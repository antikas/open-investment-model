"""Open Investment Model -> Ontology Playground transform.

Reads the released OpenIM OWL ontology (`exports/openim.rdf`) and produces the
graph the Ontology Playground reads, plus a mapping table that accounts for every
named class, object property and datatype property of the source.

The transform works on SETS of triples. The source graph is flattened (each
`owl:unionOf` domain or range is replaced by one marker triple), then a fixed list
of named rules replaces, removes or adds triples. Every change goes through
`_Edit.replace` / `_Edit.add`, which records it in a ledger with the rule that made
it. The ledger is therefore a complete account of the difference between the
source and the output: any triple the source has and the output lacks (or the
reverse) is in the ledger, attributed to one rule from `RULES`.

Nothing here reads the OpenIM model markdown. The only inputs are the released
ontology file, its release version and its public location (from `CITATION.cff`).

The Playground rules the transform satisfies (parser: `src/lib/rdf/parser.ts`,
validation: `validateOntology` in `src/store/designerStore.ts`) are cited next to
the constants and rules below as `parser.ts:NNN` and `designerStore.ts:NNN`; the
file and line numbers refer to microsoft/Ontology-Playground at the commit named
in the tools README.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, XSD

# --- vocabularies ---------------------------------------------------------

OPENIM_NS = "https://w3id.org/openim/ontology/"
SOURCE_ONTOLOGY_IRI = OPENIM_NS.rstrip("/")
ADAPTATION_IRI = OPENIM_NS + "playground"
# The annotation terms the Playground parser reads (isIdentifier, color,
# cardinality, propertyType) live in the adaptation's own namespace, never in the
# canonical OpenIM namespace.
ONT_NS = ADAPTATION_IRI + "#"
# Terms the adaptation itself mints (a relationship split per class pair, an
# inherited identifier property, a foreign-key relationship under a unique
# identifier) live here, never in the canonical OpenIM namespace: a graph that
# merges the adaptation with the canonical ontology gains no term the canonical
# model does not define.
PLAYGROUND_NS = ADAPTATION_IRI + "/"
DCTERMS_NS = "http://purl.org/dc/terms/"
PROV_NS = "http://www.w3.org/ns/prov#"
SCHEMA_NS = "https://schema.org/"

# The model's declared key column of an entity carries this annotation: its
# 1-based position among the entity's declared key columns (1 = primary key).
KEY_POSITION = URIRef(OPENIM_NS + "keyPosition")

ONT_IS_IDENTIFIER = URIRef(ONT_NS + "isIdentifier")
ONT_COLOR = URIRef(ONT_NS + "color")
ONT_CARDINALITY = URIRef(ONT_NS + "cardinality")
ONT_PROPERTY_TYPE = URIRef(ONT_NS + "propertyType")
DCTERMS_SOURCE = URIRef(DCTERMS_NS + "source")
DCTERMS_LICENSE = URIRef(DCTERMS_NS + "license")
DCTERMS_FORMAT = URIRef(DCTERMS_NS + "format")
DCTERMS_HAS_VERSION = URIRef(DCTERMS_NS + "hasVersion")
PROV_WAS_DERIVED_FROM = URIRef(PROV_NS + "wasDerivedFrom")
PROV_ENTITY = URIRef(PROV_NS + "Entity")
SCHEMA_MEDIA_OBJECT = URIRef(SCHEMA_NS + "MediaObject")
SCHEMA_SHA256 = URIRef(SCHEMA_NS + "sha256")
MIT_LICENSE_IRI = URIRef("https://spdx.org/licenses/MIT.html")

# A marker standing for one `owl:unionOf` domain or range in the flattened source.
# It is a plain string subtype, not an IRI, so it can never be written out.
_UNION_PREFIX = "union-of:"


class UnionMarker(str):
    """The members of one `owl:unionOf` class, as a single hashable value."""

    def __new__(cls, members):
        return super().__new__(cls, _UNION_PREFIX + "|".join(sorted(str(m) for m in members)))

    @property
    def members(self) -> list[str]:
        return str(self)[len(_UNION_PREFIX):].split("|")

# --- the Playground's own limits -------------------------------------------

# designerStore.ts:23 - names are 1-26 characters of letters, digits, hyphen and
# underscore, starting and ending with a letter or digit (entity and property
# names, enforced by designerStore.ts:29-36 and checked at :64 and :88).
NAME_MAX = 26
NAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9_-]{0,24}[A-Za-z0-9])?$")

# parser.ts:104-115 - the XSD local name -> Playground property type table; a
# range it does not list falls back to 'string' (parser.ts:245-253).
XSD_TO_TYPE = {
    "string": "string", "integer": "integer", "int": "integer", "long": "integer",
    "decimal": "decimal", "float": "decimal", "double": "double", "date": "date",
    "dateTime": "datetime", "boolean": "boolean",
}
# designerStore.ts:78-84 - an identifier property is a string or an integer.
IDENTIFIER_TYPES = ("string", "integer")
# parser.ts:117-122 - the cardinalities the parser accepts.
CARDINALITY = {"n-to-1": "many-to-one", "1-to-n": "one-to-many",
               "n-to-n": "many-to-many", "1-to-1": "one-to-one"}
_FLIP = {"many-to-one": "one-to-many", "one-to-many": "many-to-one",
         "many-to-many": "many-to-many", "one-to-one": "one-to-one"}

# Entity colours by identifier prefix: the Playground's own palette
# (designerStore.ts ENTITY_COLORS). parser.ts:182 defaults a colourless entity to
# one blue; a colour per prefix makes the groups of the model visible.
PREFIX_COLOUR = {"E": "#0078D4", "PB": "#107C10", "PM": "#5C2D91",
                 "DR": "#D83B01", "RA": "#008272", "FO": "#FFB900"}

_STOPWORDS = frozenset({"a", "an", "and", "by", "for", "in", "of", "on", "per", "the", "to"})

# --- the named rules --------------------------------------------------------

RULES: dict[str, str] = {
    "ontology-header": "The adaptation's own header replaces the source header: "
        "label, comment, release version, and the source file's public URL, "
        "SHA-256 and licence.",
    "entity-name": "An entity's name is its title in PascalCase, at most 26 "
        "letters and digits, unique; a longer title loses its parenthetical "
        "gloss, then its hyphenated words shrink to initials, then words are "
        "abbreviated from a fixed table, so the name keeps the title's meaning; "
        "only if it still does not fit are trailing words dropped and, last, the "
        "name cut at 26 characters (every step is recorded in the mapping).",
    "entity-description": "An entity's description starts with its OpenIM code "
        "and title, then the source description.",
    "entity-colour": "An entity is coloured by the prefix of its OpenIM code.",
    "identifier-key": "The Playground needs an identifier property per entity: "
        "every column of the entity's own declared key (the string or integer "
        "datatype properties with an openim:keyPosition) is marked as identifier. "
        "A composite key marks each of its columns; they are written first, in "
        "key order.",
    "identifier-inherited": "The entity has no own key column of that kind (a "
        "specialisation's key is its parent's key, carried by a foreign key "
        "that is drawn as a relationship), so a property named and typed like "
        "each column of its nearest ancestor's declared key is added to the entity "
        "and marked as identifier.",
    "property-name-shorten": "A property name over 26 characters drops stop "
        "words, then abbreviates words from a fixed table (bps, pct, adj, settle, "
        "...) in table order until it fits; a trailing _id is never dropped. The "
        "source name is kept in the description.",
    "property-name-unique": "A property name that clashes within its entity "
        "after shortening gets a numeric suffix.",
    "property-type-widen": "A property name used with different types in "
        "different entities is widened to string everywhere (the Playground "
        "requires one type per name); the declared type stays in the description.",
    "property-type-literal": "A property whose range is rdfs:Literal "
        "(document, map, array) is typed string explicitly, as the Playground "
        "would default it.",
    "relationship-iri-qualify": "A foreign-key column drawn as a relationship "
        "(one with no relation verb between the same two classes) is identified "
        "in the adaptation's own namespace by <owner code>_<column>, because the "
        "Playground identifies a relationship by the last part of its IRI and "
        "column names repeat across entities.",
    "relationship-duplicate-dropped": "A foreign-key column whose relation verb "
        "already draws the same two classes is not drawn a second time; it keeps "
        "its canonical IRI, label and description, without a domain or range.",
    "relationship-label": "A relationship label is the verb or column name in "
        "lower snake_case, with no length change (the Playground sets no length "
        "limit on relationship names).",
    "relationship-cardinality": "A relationship carries its cardinality: a "
        "relation verb states it, its inverse flips it, and a foreign-key column "
        "takes its verb's (many-to-one when it has none).",
    "union-expand": "A relation verb whose domain or range is a union of "
        "classes is drawn as one relationship per member pair, each a "
        "sub-property of the verb, because the Playground reads one class as "
        "domain and one as range.",
    "union-pairs-from-subclass": "A verb whose domain and range are both "
        "unions is drawn for the pairs the source states as rdfs:subClassOf "
        "(the specialisation verb), not for every combination.",
    "union-drop": "A union domain or range with no pair-level evidence is not "
        "drawn; the verb keeps its label, description and inverse.",
    "inverse-pairing": "The relationships drawn for a verb and for its inverse "
        "are declared owl:inverseOf each other, pair by pair.",
}

# --- data classes -----------------------------------------------------------


@dataclass
class MappingRow:
    source_iri: str
    kind: str                  # class | object_property | datatype_property
    openim_code: str
    target_iri: str = ""       # ';'-separated when one source property yields several
    target_name: str = ""
    shown: str = "no"          # yes | expanded | no
    objects: int = 0           # Playground entities / properties / relationships it yields
    rules: list[str] = field(default_factory=list)
    reason: str = ""

    def csv_fields(self) -> list[str]:
        return [self.source_iri, self.kind, self.openim_code, self.target_iri,
                self.target_name, self.shown, str(self.objects),
                ";".join(sorted(set(self.rules))), self.reason]


MAPPING_HEADER = ["source_iri", "kind", "openim_code", "target_iri", "target_name",
                  "playground_shows", "playground_objects", "rules", "reason"]
KIND_ORDER = {"class": 0, "object_property": 1, "datatype_property": 2}


@dataclass
class Provenance:
    release_version: str
    source_url: str
    source_sha256: str


@dataclass
class Result:
    triples: set                       # the output triples (no blank nodes)
    source_triples: set                # the flattened source triples
    ledger: list                       # (rule, 'add' | 'remove', triple)
    rows: list                         # MappingRow, sorted
    provenance: Provenance
    stats: dict

    def graph(self) -> Graph:
        g = Graph()
        for t in self.triples:
            g.add(t)
        return g


# --- reading and flattening the source ---------------------------------------


def file_sha256(path: Path) -> str:
    """SHA-256 of a file with CRLF line endings normalised to LF, so the digest
    of a Windows checkout equals the digest of the published bytes."""
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def load_graph(path: Path) -> Graph:
    g = Graph()
    g.parse(str(path), format="xml")
    return g


def is_union_marker(term) -> bool:
    return isinstance(term, UnionMarker)


def flatten(graph: Graph) -> set:
    """The graph as a set of triples with no blank nodes: each `owl:unionOf`
    class used as a domain or range becomes a marker IRI, and the blank nodes'
    own triples are dropped."""
    triples = set()
    for s, p, o in graph:
        if isinstance(s, BNode):
            continue
        if isinstance(o, BNode):
            union = graph.value(o, OWL.unionOf)
            if union is None or p not in (RDFS.domain, RDFS.range):
                raise ValueError(f"unsupported blank node object: {s} {p}")
            o = UnionMarker(Collection(graph, union))
        triples.add((s, p, o))
    return triples


# --- naming ------------------------------------------------------------------


def _fix_charset(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_-")
    return name


def entity_title(label: str, code: str) -> str:
    """`E-01 Legal Entity` -> `Legal Entity`."""
    prefix = code + " "
    return label[len(prefix):] if label.startswith(prefix) else label


def entity_name_for(title: str, limit: int = NAME_MAX) -> tuple[str, list[str]]:
    """An entity name from a title: PascalCase, within `limit` letters and digits,
    keeping the title's meaning. Returns (name, the steps that were needed).

    A title that already fits is only joined in PascalCase. Otherwise, in order and
    only until it fits: drop a parenthetical gloss; reduce each hyphenated compound
    to its initials ("Authorised-Participant" to "AP"); abbreviate words from the
    fixed table ("Agreement" to "Agmt"); and, only if it still does not fit, drop
    trailing words and, as the final step, cut at `limit` characters. Each step used
    is returned and recorded in the mapping. The full title stays in the entity's
    description and in the mapping."""
    def pascal(words) -> str:
        return "".join(w[0].upper() + w[1:] for w in words)

    def tokens(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", text)

    def flat(toks) -> list[str]:
        return [w for t in toks for w in t.split("-")]

    toks = tokens(title)
    full = pascal(flat(toks))
    if len(full) <= limit:
        return full, []
    steps: list[str] = []
    stripped = tokens(re.sub(r"\([^)]*\)", " ", title))
    if stripped != toks:
        toks = stripped
        steps.append("parenthetical gloss dropped")
        if len(pascal(flat(toks))) <= limit:
            return pascal(flat(toks)), steps
    compact = [t if "-" not in t else "".join(w[0].upper() for w in t.split("-")) for t in toks]
    if compact != toks:
        steps.append("hyphenated words reduced to initials")
        toks = compact
        if len(pascal(flat(toks))) <= limit:
            return pascal(flat(toks)), steps
    words = flat(toks)
    for long, short in ABBREVIATIONS:
        if len(pascal(words)) <= limit:
            break
        hit = [k for k, w in enumerate(words) if w.lower() == long]
        if hit:
            for k in hit:
                words[k] = short
            steps.append(f"'{long.capitalize()}' abbreviated to '{short.capitalize()}'")
    while len(words) > 1 and len(pascal(words)) > limit:
        steps.append(f"trailing word '{words[-1]}' dropped")
        words = words[:-1]
    return pascal(words)[:limit], steps


# Words abbreviated, in this order, until a property name fits. The order puts the
# long, low-information words first; each abbreviation is a standard finance short
# form. A phrase (basis_points) is matched as a whole.
ABBREVIATIONS = [
    ("basis_points", "bps"), ("percentage", "pct"), ("adjustment", "adj"),
    ("classification", "classif"), ("verification", "verif"), ("settlement", "settle"),
    ("redemption", "redeem"), ("creation", "create"), ("measurement", "measure"),
    ("arrangement", "arrgmt"), ("compliance", "compl"), ("recommended", "rec"),
    ("probability", "prob"), ("contractual", "contract"), ("commitment", "commit"),
    ("authorisation", "auth"), ("requirement", "req"), ("information", "info"),
    ("description", "desc"), ("quantity", "qty"), ("transaction", "txn"),
    ("calculation", "calc"), ("allocation", "alloc"), ("performance", "perf"),
    ("agreement", "agmt"), ("collateral", "coll"), ("management", "mgmt"),
    ("appointment", "appt"), ("distribution", "dist"), ("statement", "stmt"),
]


def snake_label(name: str) -> str:
    """A relationship label: lower snake_case, never shortened."""
    return re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")


def shorten_snake(name: str, limit: int = NAME_MAX) -> str:
    """A snake_case property name within `limit` characters, keeping its meaning:
    drop stop words, then abbreviate words from `ABBREVIATIONS` in table order
    until it fits, then (last resort) strip the vowels of the longest words and
    cut. A trailing `_id` is never dropped. Names already within the limit are
    returned unchanged."""
    name = _fix_charset(name)
    if len(name) <= limit:
        return name
    words = name.split("_")
    kept = [w for w in words if w.lower() not in _STOPWORDS] or words
    cand = "_".join(kept)
    for long, short in ABBREVIATIONS:
        if len(cand) <= limit:
            break
        cand = re.sub(rf"(?<![a-z0-9]){long}(?![a-z0-9])", short, cand)
    if len(cand) <= limit:
        return cand
    words = cand.split("_")
    while len(_join(words)) > limit:
        longest = max(range(len(words)), key=lambda i: (len(words[i]), -i))
        w = words[longest]
        stripped = w[0] + re.sub(r"[aeiou]", "", w[1:])
        if stripped == w or len(w) <= 3 or len(stripped) < 3:
            break
        words[longest] = stripped
    cand = _join(words)
    if len(cand) > limit:
        suffix = "_id" if cand.endswith("_id") else ""
        cand = cand[: limit - len(suffix)].rstrip("_-") + suffix
    return cand


def _join(words) -> str:
    return "_".join(words)


def _unique(base: str, used: set, limit: int = NAME_MAX, fold: bool = False) -> str:
    key = (lambda s: s.lower()) if fold else (lambda s: s)
    used_keys = {key(u) for u in used}
    if key(base) not in used_keys:
        return base
    n = 2
    while True:
        suffix = f"_{n}"
        candidate = base[: limit - len(suffix)].rstrip("_-") + suffix
        if key(candidate) not in used_keys:
            return candidate
        n += 1


def _n_props(n: int) -> str:
    return "property" if n == 1 else "properties"


def _code(iri) -> str:
    """The OpenIM code of a class IRI (`.../E-01` -> `E-01`)."""
    return str(iri).rsplit("/", 1)[-1]


def _fragment(iri) -> str:
    return str(iri).rsplit("#", 1)[-1]


def local_name(iri: str) -> str:
    """parser.ts:82-88 - the part after '#', else after the last '/'."""
    s = str(iri)
    if "#" in s:
        return s[s.rfind("#") + 1:]
    if "/" in s:
        return s[s.rfind("/") + 1:]
    return s


def playground_type(range_iri) -> str:
    """parser.ts:248-253 - a datatype range to a Playground property type."""
    return XSD_TO_TYPE.get(local_name(str(range_iri)), "string")


# --- the edit ledger ------------------------------------------------------------


class _Edit:
    """Applies rule-attributed changes to the output set and records them."""

    def __init__(self, source: set):
        self.out = set(source)
        self.ledger: list = []

    def remove(self, rule: str, triples) -> None:
        assert rule in RULES, rule
        for t in triples:
            if t not in self.out:
                raise AssertionError(f"rule {rule} removes a triple not present: {t}")
            self.out.discard(t)
            self.ledger.append((rule, "remove", t))

    def add(self, rule: str, triples) -> None:
        assert rule in RULES, rule
        for t in triples:
            if t in self.out:
                raise AssertionError(f"rule {rule} adds a triple already present: {t}")
            self.out.add(t)
            self.ledger.append((rule, "add", t))

    def replace(self, rule: str, old, new) -> None:
        self.remove(rule, old)
        self.add(rule, new)


# --- the transform ------------------------------------------------------------------


def transform(source_graph: Graph, provenance: Provenance) -> Result:
    src = flatten(source_graph)
    edit = _Edit(src)

    objects_seen = {t[2] for t in src}
    by_subject: dict = {}
    by_subject_predicate: dict = {}
    for t in src:
        by_subject.setdefault(t[0], []).append(t)
        by_subject_predicate.setdefault((t[0], t[1]), []).append(t[2])

    def objs(s, p):
        return sorted(by_subject_predicate.get((s, p), ()), key=str)

    def obj(s, p):
        v = objs(s, p)
        return v[0] if v else None

    def subjects_of_type(t):
        return sorted({s for (s, p, o) in src if p == RDF.type and o == t and isinstance(s, URIRef)}, key=str)

    classes = subjects_of_type(OWL.Class)
    object_props = subjects_of_type(OWL.ObjectProperty)
    datatype_props = subjects_of_type(OWL.DatatypeProperty)
    class_set = set(classes)
    rows: dict[str, MappingRow] = {}

    # ---- ontology header --------------------------------------------------
    header_old = set(by_subject.get(URIRef(SOURCE_ONTOLOGY_IRI), ()))
    release = provenance.release_version
    adaptation = URIRef(ADAPTATION_IRI)
    source_url = URIRef(provenance.source_url)
    header_new = {
        (adaptation, RDF.type, OWL.Ontology),
        (adaptation, RDFS.label, Literal("Open Investment Model (Playground adaptation)")),
        (adaptation, RDFS.comment, Literal(
            "An adaptation of the Open Investment Model (OpenIM) ontology for the "
            "Ontology Playground. It is derived mechanically from the released "
            "OpenIM ontology and is not the canonical model: entity names are "
            "shortened to the Playground's limits, every entity keeps its OpenIM "
            "code in its description, and relation verbs over several classes are "
            "drawn one relationship per class pair. The canonical model and the "
            "full ontology are at https://openinvestmentmodel.org/.")),
        (adaptation, OWL.versionInfo, Literal(release)),
        (adaptation, DCTERMS_SOURCE, source_url),
        (adaptation, PROV_WAS_DERIVED_FROM, source_url),
        (adaptation, DCTERMS_LICENSE, MIT_LICENSE_IRI),
        (source_url, RDF.type, PROV_ENTITY),
        (source_url, RDF.type, SCHEMA_MEDIA_OBJECT),
        (source_url, DCTERMS_FORMAT, Literal("application/rdf+xml")),
        (source_url, DCTERMS_HAS_VERSION, Literal(release)),
        (source_url, SCHEMA_SHA256, Literal(provenance.source_sha256)),
    }
    if header_old:
        edit.remove("ontology-header", header_old)
    edit.add("ontology-header", header_new)

    # ---- entities ------------------------------------------------------------
    entity_name: dict = {}
    entity_name_how: dict = {}
    entity_title_of: dict = {}
    used_names: set = set()
    for c in classes:
        code = _code(c)
        label = str(obj(c, RDFS.label) or code)
        title = entity_title(label, code)
        entity_title_of[c] = title
        base, how = entity_name_for(title)
        if not base:
            base = _fix_charset(code)
        name = _unique(base, used_names, fold=True)
        used_names.add(name)
        entity_name[c] = name
        entity_name_how[c] = how

    prop_by_class: dict = {c: [] for c in classes}
    for p in datatype_props:
        d = obj(p, RDFS.domain)
        if d in class_set:
            prop_by_class[d].append(p)

    # ---- datatype properties: names, types -----------------------------------------
    prop_name: dict = {}
    prop_type: dict = {}
    prop_rules: dict = {p: [] for p in datatype_props}
    name_rule: dict = {}
    for c in classes:
        used: set = set()
        for p in sorted(prop_by_class[c], key=str):
            source_name = str(obj(p, RDFS.label) or _fragment(p))
            short = shorten_snake(source_name)
            if short != source_name:
                prop_rules[p].append("property-name-shorten")
                name_rule[p] = "property-name-shorten"
            name = _unique(short, used)
            if name != short:
                prop_rules[p].append("property-name-unique")
                name_rule[p] = "property-name-unique"
            used.add(name)
            prop_name[p] = name
            r = obj(p, RDFS.range)
            prop_type[p] = playground_type(r) if r is not None else "string"

    # one type per name across the whole ontology (designerStore.ts:92-101)
    types_by_name: dict = {}
    for p, n in prop_name.items():
        types_by_name.setdefault(n, set()).add(prop_type[p])
    widened = {p for p, n in prop_name.items() if len(types_by_name[n]) > 1 and prop_type[p] != "string"}
    for p in widened:
        prop_type[p] = "string"
        prop_rules[p].append("property-type-widen")

    # ---- identifiers: the model's declared key, own or inherited -----------------------
    def own_keys(c):
        """The entity's own key columns as the model declares them, in key order:
        the string or integer datatype properties carrying keyPosition."""
        cands = []
        for p in prop_by_class[c]:
            pos = obj(p, KEY_POSITION)
            if pos is not None and prop_type[p] in IDENTIFIER_TYPES:
                cands.append((int(pos), str(p), p))
        return [p for _, _, p in sorted(cands)]

    def declared_key_size(c):
        """How many datatype columns the model declares in the entity's own key."""
        return sum(1 for p in prop_by_class[c] if obj(p, KEY_POSITION) is not None)

    identifier: dict = {}      # class -> {property: key position}
    inherited: dict = {}       # class -> (nearest ancestor with an own key, its key properties)
    own = {c: own_keys(c) for c in classes}
    for c in classes:
        if own[c]:
            identifier[c] = {p: n for n, p in enumerate(own[c], 1)}
            continue
        seen, frontier = {c}, [c]
        while frontier and c not in inherited:
            nxt = []
            for x in frontier:
                for parent in sorted((o for o in objs(x, RDFS.subClassOf) if o in class_set), key=str):
                    if parent in seen:
                        continue
                    seen.add(parent)
                    if own.get(parent):
                        inherited[c] = (parent, own[parent])
                        break
                    nxt.append(parent)
                if c in inherited:
                    break
            frontier = nxt
    inherited_props: dict = {}  # class -> [(added property, its name, ancestor key property, ancestor)]
    for c, (parent, key_props) in sorted(inherited.items(), key=lambda kv: str(kv[0])):
        used = {prop_name[p] for p in prop_by_class[c]}
        added = []
        for key_prop in key_props:
            name = _unique(prop_name[key_prop], used)
            used.add(name)
            added.append((URIRef(f"{PLAYGROUND_NS}key/{_code(c)}_{_fragment(key_prop)}"), name, key_prop, parent))
        inherited_props[c] = added

    # ---- apply entity edits ------------------------------------------------------------
    for c in classes:
        code = _code(c)
        title = entity_title_of[c]
        old_label = obj(c, RDFS.label)
        old_comment = obj(c, RDFS.comment)
        name = entity_name[c]
        row = MappingRow(source_iri=str(c), kind="class", openim_code=code,
                         target_iri=str(c), target_name=name, shown="yes", objects=1)
        new_comment = f"{code} {title}" + (f": {old_comment}" if old_comment else "")
        if old_label is not None:
            edit.replace("entity-name", [(c, RDFS.label, old_label)], [(c, RDFS.label, Literal(name))])
        else:
            edit.add("entity-name", [(c, RDFS.label, Literal(name))])
        if old_comment is not None:
            edit.replace("entity-description", [(c, RDFS.comment, old_comment)], [(c, RDFS.comment, Literal(new_comment))])
        else:
            edit.add("entity-description", [(c, RDFS.comment, Literal(new_comment))])
        row.rules += ["entity-name", "entity-description"]
        how = entity_name_how[c]
        if how:
            row.reason = f"title '{title}' written as '{name}' (26-character limit: {'; '.join(how)})"
        elif name != re.sub(r"[^A-Za-z0-9]", "", title):
            row.reason = f"title '{title}' written as '{name}'"
        if c in inherited_props:
            added = inherited_props[c]
            for new_prop, pname, key_prop, parent in added:
                ptype = XSD.integer if prop_type[key_prop] == "integer" else XSD.string
                edit.add("identifier-inherited", [
                    (new_prop, RDF.type, OWL.DatatypeProperty),
                    (new_prop, RDFS.label, Literal(pname)),
                    (new_prop, RDFS.comment, Literal(
                        f"Inherited key: the key of {_code(parent)} {entity_title_of[parent]} "
                        f"(its column {prop_name[key_prop]}). In the model this entity's key is "
                        f"the foreign key to {_code(parent)}, drawn as a relationship.")),
                    (new_prop, RDFS.domain, c),
                    (new_prop, RDFS.range, ptype),
                    (new_prop, ONT_IS_IDENTIFIER, Literal("true", datatype=XSD.boolean)),
                    # the position the column has in the ancestor's declared key, so the
                    # inherited columns are written in key order, not alphabetical order
                    (new_prop, KEY_POSITION, Literal(int(str(obj(key_prop, KEY_POSITION))))),
                ])
            parent = added[0][3]
            row.rules.append("identifier-inherited")
            row.target_iri = ";".join([str(c)] + [str(a[0]) for a in added])
            row.objects = 1 + len(added)
            names = ", ".join(f"'{a[1]}'" for a in added)
            extra = (f"identifier inherited from {_code(parent)}: {_n_props(len(added))} {names} added "
                     f"because the entity's own key is a foreign key, drawn as a relationship")
            row.reason = (row.reason + "; " if row.reason else "") + extra
        prefix = code.split("-", 1)[0]
        if prefix in PREFIX_COLOUR:
            edit.add("entity-colour", [(c, ONT_COLOR, Literal(PREFIX_COLOUR[prefix]))])
            row.rules.append("entity-colour")
        rows[str(c)] = row

    # ---- apply datatype property edits ------------------------------------------------------
    for p in datatype_props:
        d = obj(p, RDFS.domain)
        code = _code(d) if d is not None else ""
        src_name = str(obj(p, RDFS.label) or _fragment(p))
        row = MappingRow(source_iri=str(p), kind="datatype_property",
                         openim_code=f"{code}.{src_name}" if code else src_name)
        if d not in class_set:
            row.shown = "no"
            row.reason = "the property's domain is not a class of the ontology, so the Playground has no entity to attach it to"
            rows[str(p)] = row
            continue
        name = prop_name[p]
        old_label = obj(p, RDFS.label)
        old_comment = obj(p, RDFS.comment)
        old_range = obj(p, RDFS.range)
        reasons = []
        # label
        if old_label is None or str(old_label) != name:
            rule = name_rule.get(p, "property-name-shorten")
            if old_label is not None:
                edit.replace(rule, [(p, RDFS.label, old_label)], [(p, RDFS.label, Literal(name))])
            else:
                edit.add(rule, [(p, RDFS.label, Literal(name))])
            reasons.append(f"name '{src_name}' written as '{name}' (26-character limit)")
        # description keeps the source name when it changed
        comment_text = str(old_comment) if old_comment is not None else ""
        if name != src_name:
            rule = name_rule.get(p, "property-name-shorten")
            comment_text = (comment_text + " " if comment_text else "") + f"Source name: {src_name}."
            if old_comment is not None:
                edit.replace(rule, [(p, RDFS.comment, old_comment)], [(p, RDFS.comment, Literal(comment_text))])
            else:
                edit.add(rule, [(p, RDFS.comment, Literal(comment_text))])
        # type
        if p in widened:
            new_range = XSD.string
            if old_range is not None:
                edit.replace("property-type-widen", [(p, RDFS.range, old_range)], [(p, RDFS.range, new_range)])
            else:
                edit.add("property-type-widen", [(p, RDFS.range, new_range)])
            reasons.append(f"widened to string: the name '{name}' has different types in different entities and the Playground requires one (declared type kept in the description)")
        elif old_range is not None and local_name(str(old_range)) not in XSD_TO_TYPE:
            edit.add("property-type-literal", [(p, ONT_PROPERTY_TYPE, Literal("string"))])
            prop_rules[p].append("property-type-literal")
        # identifier
        assert d is not None            # a domain outside the ontology was handled above
        if p in identifier.get(d, {}):
            edit.add("identifier-key", [(p, ONT_IS_IDENTIFIER, Literal("true", datatype=XSD.boolean))])
            prop_rules[p].append("identifier-key")
            size = declared_key_size(d)
            if size > 1:
                names = ", ".join(prop_name[q] for q in own[d])
                reasons.append(
                    f"column {identifier[d][p]} of the entity's {size}-column declared key ({names}); every "
                    f"key column is marked identifier (the Playground accepts several identifier properties "
                    f"and its Fabric export uses the first, so key columns are written first, in key order)")
        row.target_iri = str(p)
        row.target_name = name
        row.shown = "yes"
        row.objects = 1
        row.rules = sorted(set(prop_rules[p]))
        row.reason = "; ".join(reasons)
        rows[str(p)] = row

    # ---- object properties --------------------------------------------------------------------
    verbs = [p for p in object_props if "#" not in str(p)]
    columns = [p for p in object_props if "#" in str(p)]
    verb_set = set(verbs)

    def comment_of(p):
        return str(obj(p, RDFS.comment) or "")

    fwd_re = re.compile(r"^OpenIM relation verb\W+(?P<kind>[^,]+), (?P<card>[^.]+)\. Inverse: (?P<inv>.+)\.$")
    inv_re = re.compile(r"^Inverse of openim:(?P<fwd>\S+) \((?P<kind>[^,]+), (?P<card>[^)]+)\)\.$")
    role: dict = {}
    forward_card: dict = {}
    for v in verbs:
        text = comment_of(v)
        m = fwd_re.match(text)
        if m:
            role[v] = "forward"
            forward_card[v] = CARDINALITY.get(m.group("card"))
            continue
        m = inv_re.match(text)
        if m:
            role[v] = "inverse"
            continue
        role[v] = "unknown"
    verb_card: dict = {}
    for v in verbs:
        if role[v] == "forward":
            verb_card[v] = forward_card[v]
        elif role[v] == "inverse":
            partner = obj(v, OWL.inverseOf)
            fc = forward_card.get(partner)
            verb_card[v] = _FLIP[fc] if fc else None
        else:
            verb_card[v] = None

    subclass_pairs = {(s, o) for (s, p_, o) in src if p_ == RDFS.subClassOf and s in class_set and o in class_set}

    def members_of(term) -> list:
        if term is None:
            return []
        if is_union_marker(term):
            return [URIRef(m) for m in term.members]
        return [term]

    # pairs per verb
    verb_pairs: dict = {}
    verb_note: dict = {}
    for v in verbs:
        dom_t, rng_t = obj(v, RDFS.domain), obj(v, RDFS.range)
        dom, rng = members_of(dom_t), members_of(rng_t)
        if not dom or not rng:
            verb_pairs[v] = []
            verb_note[v] = "the verb has no domain or range in the source"
            continue
        cross = [(a, b) for a in sorted(dom, key=str) for b in sorted(rng, key=str)]
        if len(cross) == 1:
            verb_pairs[v] = cross
        elif len(dom) == 1 or len(rng) == 1:
            verb_pairs[v] = cross
        else:
            verb_pairs[v] = None   # decided after all single-sided verbs, from evidence
    for v in verbs:
        if verb_pairs[v] is not None:
            continue
        dom, rng = members_of(obj(v, RDFS.domain)), members_of(obj(v, RDFS.range))
        cross = {(a, b) for a in dom for b in rng}
        if role[v] == "forward":
            pairs = sorted(cross & subclass_pairs, key=lambda x: (str(x[0]), str(x[1])))
        elif role[v] == "inverse":
            partner = obj(v, OWL.inverseOf)
            fdom, frng = members_of(obj(partner, RDFS.domain)), members_of(obj(partner, RDFS.range))
            fcross = {(a, b) for a in fdom for b in frng}
            pairs = sorted(((b, a) for (a, b) in (fcross & subclass_pairs)), key=lambda x: (str(x[0]), str(x[1])))
            pairs = [pr for pr in pairs if pr in cross]
        else:
            pairs = []
        verb_pairs[v] = pairs
        if not pairs:
            verb_note[v] = "its domain and range are both unions of classes and the source states no pair of them"

    def child_iri(v, a, b) -> URIRef:
        return URIRef(f"{PLAYGROUND_NS}{local_name(v)}_{_code(a)}_{_code(b)}")

    shown_children: dict = {}
    for v in verbs:
        pairs = verb_pairs[v]
        dom_t, rng_t = obj(v, RDFS.domain), obj(v, RDFS.range)
        label_old = obj(v, RDFS.label)
        src_label = str(label_old) if label_old is not None else local_name(v)
        label = snake_label(src_label)
        label_rule_reason = []
        if label != src_label:
            label_rule_reason.append(f"label '{src_label}' written as '{label}'")
        card = verb_card[v]
        card_triple_value = Literal(card) if card else None
        row = MappingRow(source_iri=str(v), kind="object_property", openim_code=src_label)
        simple = pairs and len(pairs) == 1 and not (is_union_marker(dom_t) or is_union_marker(rng_t))
        if simple:
            (a, b), = pairs
            if a not in class_set or b not in class_set:
                row.shown = "no"
                row.reason = "its domain or range is not a class of the ontology"
                rows[str(v)] = row
                continue
            if label_old is not None:
                edit.replace("relationship-label", [(v, RDFS.label, label_old)], [(v, RDFS.label, Literal(label))])
            else:
                edit.add("relationship-label", [(v, RDFS.label, Literal(label))])
            row.rules.append("relationship-label")
            if card_triple_value is not None:
                edit.add("relationship-cardinality", [(v, ONT_CARDINALITY, card_triple_value)])
                row.rules.append("relationship-cardinality")
            row.target_iri, row.target_name = str(v), label
            row.shown, row.objects = "yes", 1
            row.reason = "; ".join(label_rule_reason)
            shown_children[v] = {(a, b): v}
            rows[str(v)] = row
            continue
        # a union (or unevidenced) verb: the parent is not drawn
        union_old = [t for t in by_subject.get(v, ()) if t[1] in (RDFS.domain, RDFS.range) and is_union_marker(t[2])]
        pairs = [pr for pr in (pairs or []) if pr[0] in class_set and pr[1] in class_set]
        if not pairs:
            if union_old:
                edit.remove("union-drop", union_old)
                row.rules.append("union-drop")
            row.shown = "no"
            row.reason = verb_note.get(v, "no member pair is a class of the ontology") + "; the Playground draws no relationship for it"
            rows[str(v)] = row
            continue
        both_unions = is_union_marker(dom_t) and is_union_marker(rng_t)
        rule = "union-pairs-from-subclass" if both_unions else "union-expand"
        edit.remove(rule, union_old)
        children = {}
        parent_comment = obj(v, RDFS.comment)
        for a, b in pairs:
            ch = child_iri(v, a, b)
            children[(a, b)] = ch
            new = [
                (ch, RDF.type, OWL.ObjectProperty),
                (ch, RDFS.label, Literal(label)),
                (ch, RDFS.domain, a),
                (ch, RDFS.range, b),
                (ch, RDFS.subPropertyOf, v),
            ]
            if parent_comment is not None:
                new.append((ch, RDFS.comment, parent_comment))
            edit.add(rule, new)
            if card_triple_value is not None:
                edit.add("relationship-cardinality", [(ch, ONT_CARDINALITY, card_triple_value)])
        shown_children[v] = children
        row.rules += [rule, "relationship-label"]
        if card_triple_value is not None:
            row.rules.append("relationship-cardinality")
        row.target_iri = ";".join(sorted(str(c_) for c_ in children.values()))
        row.target_name = label
        row.shown, row.objects = "expanded", len(children)
        how = ("one relationship per pair the source states as rdfs:subClassOf"
               if both_unions else "one relationship per member class pair")
        row.reason = (f"the Playground reads one class as domain and one as range; "
                      f"drawn as {len(children)} relationships, {how}; the verb itself is not drawn")
        rows[str(v)] = row
    # inverse pairing between children
    for v in verbs:
        partner = obj(v, OWL.inverseOf)
        if partner is None or v not in shown_children or partner not in shown_children:
            continue
        mine, theirs = shown_children[v], shown_children[partner]
        if all(mine[k] == v for k in mine) and all(theirs[k] == partner for k in theirs):
            continue   # both simple verbs: the source inverseOf triple already pairs them
        for (a, b), ch in sorted(mine.items(), key=lambda kv: str(kv[1])):
            other = theirs.get((b, a))
            if other is None or (ch, OWL.inverseOf, other) in edit.out:
                continue
            edit.add("inverse-pairing", [(ch, OWL.inverseOf, other)])
            if ch != v and "inverse-pairing" not in rows[str(v)].rules:
                rows[str(v)].rules.append("inverse-pairing")

    # foreign-key columns
    for p in columns:
        d, r = obj(p, RDFS.domain), obj(p, RDFS.range)
        src_label = str(obj(p, RDFS.label) or _fragment(p))
        code = _code(d) if d is not None else ""
        row = MappingRow(source_iri=str(p), kind="object_property",
                         openim_code=f"{code}.{src_label}" if code else src_label)
        if d not in class_set or r not in class_set:
            row.shown = "no"
            row.reason = "its domain or range is not a class of the ontology"
            rows[str(p)] = row
            continue
        verb = obj(p, RDFS.subPropertyOf)
        twin = shown_children.get(verb, {}).get((d, r)) if verb in verb_set else None
        if twin is not None:
            # the relation verb already draws this pair of classes
            assert verb is not None     # a twin exists only through the column's verb
            edit.remove("relationship-duplicate-dropped", [(p, RDFS.domain, d), (p, RDFS.range, r)])
            row.rules = ["relationship-duplicate-dropped"]
            row.shown = "no"
            row.reason = (f"duplicates the relation verb '{snake_label(str(obj(verb, RDFS.label) or local_name(verb)))}' "
                          f"({verb}), which already draws {_code(d)} to {_code(r)} as {twin}; "
                          f"the column keeps its canonical IRI without a domain or range")
            rows[str(p)] = row
            continue
        new_iri = URIRef(f"{PLAYGROUND_NS}{code}_{_fragment(p)}")
        card = verb_card.get(verb) if verb in verb_set else None
        label = snake_label(src_label)
        old = set(by_subject.get(p, ()))
        new = {(new_iri, p_, Literal(label) if p_ == RDFS.label else o_) for (_, p_, o_) in old}
        if p in objects_seen:
            raise AssertionError(f"a triple has the column property {p} as its object")
        edit.remove("relationship-iri-qualify", old)
        edit.add("relationship-iri-qualify", new)
        edit.add("relationship-cardinality", [(new_iri, ONT_CARDINALITY, Literal(card or "many-to-one"))])
        row.rules = ["relationship-iri-qualify", "relationship-cardinality"]
        reasons = ["no relation verb draws this pair of classes; identifier qualified by the owner's code in the adaptation namespace (relationship identifiers must be unique)"]
        if label != src_label:
            row.rules.append("relationship-label")
            reasons.append(f"label '{src_label}' written as '{label}'")
        row.target_iri, row.target_name = str(new_iri), label
        row.shown, row.objects = "yes", 1
        row.reason = "; ".join(reasons)
        rows[str(p)] = row

    # ---- anything the rules left unexplained is a defect ---------------------------------------------
    leftover = [t for t in edit.out if is_union_marker(t[2])]
    if leftover:
        raise AssertionError(f"union markers left in the output: {leftover[:3]}")

    drawn = ({t[0] for t in edit.out if t[1] == RDF.type and t[2] == OWL.ObjectProperty}
             & {t[0] for t in edit.out if t[1] == RDFS.domain and t[2] in class_set}
             & {t[0] for t in edit.out if t[1] == RDFS.range and t[2] in class_set})
    with_inverse = sum(1 for t in edit.out if t[1] == OWL.inverseOf and t[0] in drawn and t[2] in drawn)

    all_rows = sorted(rows.values(), key=lambda r: (KIND_ORDER[r.kind], r.source_iri))
    stats = {
        "entities": sum(1 for r in all_rows if r.kind == "class" and r.shown == "yes"),
        "properties": sum(r.objects for r in all_rows if r.kind == "datatype_property")
                      + sum(r.objects - 1 for r in all_rows if r.kind == "class"),
        "relationships": sum(r.objects for r in all_rows if r.kind == "object_property"),
        "relationships_with_inverse": with_inverse,
        "source_classes": len(classes),
        "source_object_properties": len(object_props),
        "source_datatype_properties": len(datatype_props),
    }
    return Result(triples=edit.out, source_triples=src, ledger=edit.ledger,
                  rows=all_rows, provenance=provenance, stats=stats)
