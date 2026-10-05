# OpenIM to Ontology Playground adaptation

A deterministic transform from the released OpenIM ontology to the form the
[Ontology Playground](https://github.com/microsoft/Ontology-Playground) reads, and
the command that assembles a Playground catalogue entry from it.

The Playground is a viewer. It reads an OWL ontology more narrowly than OWL allows
and limits names. The adaptation is the smallest set of rules that makes the whole
OpenIM ontology load, draw and validate there. It is an adaptation for that viewer,
not the canonical model: the canonical ontology is `exports/openim.rdf`.

## Commands

```
python -m pip install -r tools/playground/requirements.txt

python tools/playground/generate.py
python tools/playground/entry.py --out <folder>
```

`generate.py` reads `exports/openim.rdf` (the released ontology) and `CITATION.cff`
(the release version and the public repository address), and writes:

| File | Content |
|---|---|
| `exports/openim-playground.rdf` | the ontology in the form the Playground reads |
| `exports/openim-playground-mapping.csv` | one row per source class, object property and datatype property |

The ontology header names its source: the release version (`owl:versionInfo`, from
`CITATION.cff`), the source file's public address at that release tag
(`prov:wasDerivedFrom`, `dcterms:source`) and its SHA-256 (`schema:sha256`), with the
licence (`dcterms:license`). The digest is of the published file with LF line endings.

`entry.py` first refuses unless `exports/openim.rdf` is byte for byte the file published
at the release named in `CITATION.cff`: it compares SHA-256 digests with the file at git
tag `v<version>`, or with a `--published-copy` downloaded from the release. The reference can
never be the file under test: a copy that is the source file itself (by any path) or lies
inside the tree is refused, and a ref must be that release tag of a repository whose origin
is the public one (a branch, HEAD, a commit, or a repository with no origin is refused). An entry
must never cite a release whose published file is not the one it was generated from, so a
build from an unreleased tree is refused (`generate.py` itself still runs anywhere). Then it
runs `generate.py` and writes the four files of a catalogue entry into
`<folder>`: `ontology.rdf` (a byte copy of `exports/openim-playground.rdf`), `LICENSE`
(a byte copy of the MIT licence), `README.md` and `metadata.json`. Every count in
that README and metadata comes from the mapping.

Both commands check their own output before writing. A defect stops the run with a
non-zero exit and nothing is written. Running either twice, in separate processes,
gives byte-identical files.

## The model's declared key

The identifier is not guessed from column names. The released ontology marks the
model's declared keys:

- `openim:keyPosition` is on each column of an entity's own key, the key declared in
  the entity's first attribute table: its 1-based position in that key, so `1` is the
  first key column and a composite key such as E-04's `(position_id, book)` is `1`, `2`.
  A specialisation's key is its parent's, carried by a foreign-key column, so the
  annotation sits on that object property.
- `openim:partKeyPosition` is on the key of a further structure the entity describes (a
  later attribute table, such as the Credit Support Annex table of the master-agreement
  entity; PM-01's Fund Family key `fund_family_id`, a foreign key in the Fund table, is
  read from the later table too). It is a different structure's key, never part of the
  entity's key.

A column is a declared key when a sentence of its definition in the model opens with
"Primary key", "Golden key" or "Part of the primary key". A definition that merely
refers to another record's golden key ("The golden key of the master record") is not a
declaration. The transform reads `keyPosition` and nothing else to choose identifiers.

## Namespaces

The adaptation mints terms of its own (a relationship per class pair, a foreign-key
relationship under a unique identifier, an inherited identifier property) in
`https://w3id.org/openim/ontology/playground/`, never in the canonical
`https://w3id.org/openim/ontology/`. Every other IRI is the canonical one. Merging the
adaptation with the canonical ontology therefore adds no term the canonical model does
not define.

## The mapping

`openim-playground-mapping.csv` has one row for every named class, object property
and datatype property of the source ontology. No source construct is missing and
none appears twice.

| Column | Meaning |
|---|---|
| `source_iri` | the construct in the source ontology |
| `kind` | `class`, `object_property` or `datatype_property` |
| `openim_code` | `E-01` for a class; `E-01.column_name` for a property; the verb name for a relation verb |
| `target_iri` | what it becomes (several, separated by `;`, when one verb becomes several relationships, or a class also gets an inherited identifier property); empty when not drawn |
| `target_name` | the Playground name |
| `playground_shows` | `yes` (drawn one to one), `expanded` (drawn as several relationships) or `no` |
| `playground_objects` | how many entities, properties or relationships it yields (a class row yields 2 when the entity also gets an inherited identifier property) |
| `rules` | the rules applied, from the table below |
| `reason` | why, for anything not drawn one to one or changed |

## Rules

Every triple the output adds to, or removes from, the source ontology is made by
exactly one of these rules. The tests compute the difference between the two graphs
and fail on any triple the rules do not account for.

The Playground code each rule rests on is cited as `file:line` in
`microsoft/Ontology-Playground` at commit `42a5e5ec170c1e76343886b9d5ba7a55959cb112`.

| Rule | What it does | Playground code |
|---|---|---|
| `ontology-header` | replaces the source header with the adaptation's own: label, comment, release version, source address, digest, licence | `src/lib/rdf/parser.ts:161-166` reads the ontology label and comment |
| `entity-name` | name = title in PascalCase, 26 letters and digits at most, unique; a longer title loses its parenthetical gloss, then hyphenated words shrink to initials, then words are abbreviated from a fixed table (`ETF Authorised-Participant Agreement` to `ETFAPAgreement`, `Master Agreement & Collateral Terms` to `MasterAgmtCollateralTerms`); only if a title still does not fit are trailing words dropped and, last, the name cut at 26 characters; every step is recorded in the mapping, and the full title stays in the description | `src/store/designerStore.ts:23` and `:29-36` (name pattern and length), `:64` (applied to entity names); `src/lib/rdf/parser.ts:179` (the name is the label) |
| `entity-description` | description = OpenIM code, title, then the source description | `parser.ts:180` (the description is the comment) |
| `entity-colour` | colour by the prefix of the OpenIM code | `parser.ts:182` (otherwise every entity gets one default colour) |
| `identifier-key` | every column of the entity's own declared key (string or integer datatype properties with `openim:keyPosition`) is marked identifier; a composite key marks each column and the columns are written first, in key order | `designerStore.ts:69-75` (an entity needs an identifier; several are accepted); `:77-84` (each identifier must be string or integer); `parser.ts:213` (`isIdentifier` per property); `fabric.ts:174-176` (the Fabric export takes the first identifier, hence key order) |
| `identifier-inherited` | an entity whose only declared key is a foreign key (a specialisation) gets a property named and typed like each column of its nearest ancestor's declared key, marked identifier; the foreign key itself stays a relationship | `designerStore.ts:69-75` (an identifier is a property of the entity); `parser.ts:241` (a datatype property belongs to the entity named by its domain); `:213` |
| `property-name-shorten` | a property name over 26 characters drops stop words, then abbreviates words from a fixed table (`basis_points` to `bps`, `percentage` to `pct`, `settlement` to `settle`, ...) in table order until it fits; a trailing `_id` is never dropped; the source name stays in the description and the mapping | `designerStore.ts:88` (applied to property names) |
| `property-name-unique` | a clash within an entity gets a numeric suffix | `src/lib/fabric.ts:164` and `:176` key an entity's properties by name |
| `property-type-widen` | a name used with different types in different entities becomes string everywhere | `designerStore.ts:92-101` |
| `property-type-literal` | a property whose range is `rdfs:Literal` is typed string explicitly | `parser.ts:245-253` (a range it does not know falls back to string) |
| `relationship-iri-qualify` | a foreign-key column drawn as a relationship (no relation verb draws the same two classes) is identified as `<owner code>_<column>` in the adaptation namespace | `parser.ts:279` (the identifier is the last part of the IRI); `designerStore.ts:111-115` (identifiers must be unique) |
| `relationship-duplicate-dropped` | a foreign-key column whose relation verb already draws the same two classes is not drawn again; it keeps its canonical IRI, label and description without a domain or range, and the mapping names the verb it duplicates | `parser.ts:318-319` (a relationship without a resolved domain and range is not drawn) |
| `relationship-label` | labels are lower snake_case at their full length (no shortening) | `scripts/style-validator.ts:135-145` (relationship labels should prefer snake_case); `designerStore.ts:106-127` (relationships are checked for identifier and endpoints only, no name length); `fabric.ts:234-243` (names are sanitised to 128 characters on export) |
| `relationship-cardinality` | each relationship carries its cardinality | `parser.ts:117-122` and `:297-300` |
| `union-expand` | a verb whose domain or range is a union of classes is drawn once per member pair, each a sub-property of the verb | `parser.ts:285-295` (domain and range are read from a single `rdf:resource`); `:318-319` (a relationship without a resolved domain or range is skipped) |
| `union-pairs-from-subclass` | a verb whose domain and range are both unions is drawn for the pairs the source states as `rdfs:subClassOf` | as above |
| `union-drop` | a union with no pair-level evidence is not drawn | as above |
| `inverse-pairing` | the relationships drawn for a verb and its inverse are `owl:inverseOf` each other, pair by pair | |

How the Playground reads names, identifiers, types and relationships:
`src/lib/rdf/parser.ts:145-366` and `validateOntology` in
`src/store/designerStore.ts:38-125`. The style checks in `scripts/style-validator.ts`
read fields (`entities`, `dataProperties`, `objectProperties`) that the parser does not
produce, so at that commit they report nothing for any entry; the adaptation follows
them anyway (PascalCase entity names, snake_case property and relationship labels).

## How the output is checked

`verify.py` restates the Playground's rules and reads the written ontology back. It
reports a defect for:

- an entity or property name over 26 characters or with an unsafe character, and any
  entity name used twice (case-insensitive);
- an entity with no identifier, or an identifier that is not a string or integer;
- a property name with two types across the ontology;
- a relationship identifier used twice, a relationship to a class that does not exist,
  or a relationship without a valid cardinality;
- an entity description that does not start with its OpenIM code;
- a pair of inverse relationships whose domain and range are not swapped, whose cardinalities
  are not flips of each other, or an inverse pair that is not declared;
- a foreign-key column drawn next to the relation verb that already draws the same two
  classes, a column marked not drawn that no verb duplicates, or a relationship that is drawn
  but named by no mapping row;
- an identifier that is not the entity's declared key (or the nearest ancestor's), or an
  entity with no declared or inherited key;
- a mapping row missing, repeated, or for something that is not in the source;
- a mapping target that is not in the output, or drawn between other classes than the
  source states (so a dropped relationship is caught);
- any triple added or removed without a rule.

## Tests

```
python -m pytest tools/playground/tests/
```

The tests build a small source ontology with one example of every construct, run the
transform, then damage the output in one named way at a time (a name collision, an
over-length name, a missing identifier, a dropped relationship, ...) and require
`verify.py` to report exactly that. They also run the commands in separate processes
with different hash seeds and compare bytes. When a checkout has `exports/openim.rdf`
the release itself is checked too.
