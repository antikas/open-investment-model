#!/usr/bin/env python3
"""Assemble the Ontology Playground catalogue entry from the released OpenIM files.

    python tools/playground/entry.py --out <folder>

First refuses unless `exports/openim.rdf` is byte for byte the file published at the
release named in `CITATION.cff` (its SHA-256 is compared with the file at git tag
`v<version>`, or with a `--published-copy` downloaded from the release): an entry must never cite
a release whose published file is not the one it was generated from.

Then runs the adaptation (`generate.py`) from `exports/openim.rdf` and writes the
four files of a catalogue entry into `<folder>`:

    ontology.rdf   a byte copy of exports/openim-playground.rdf
    LICENSE        a byte copy of the public MIT licence
    README.md      what the entry is, its source release and file digests, the
                   command that regenerates it, and the transformation rules
    metadata.json  name, description, category, icon, tags, author

No figure in the README or the metadata is typed by hand: every count comes from
the mapping the transform just produced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[1]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from playground import generate, transform  # noqa: E402
from release_version import read_citation_field  # noqa: E402

AUTHOR = "antikas"
CATEGORY = "finance"
ICON = "\U0001F4C8"
TAGS = ["investment", "asset-management", "fibo", "knowledge-graph"]
METADATA_KEYS = ["name", "description", "category", "icon", "tags", "author"]
NAME = "Open Investment Model (OpenIM), Playground adaptation"
# What a build identifier looks like: none may reach a reader-facing file.
_BUILD_ID = re.compile(r"OIM[-]\d|ADR[-]\d|cycle[-]\d|\baudit\b", re.IGNORECASE)
_MIT_MARKER = "Permission is hereby granted, free of charge"


class EntryError(Exception):
    pass


_RELEASE_TAG = re.compile(r"^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _same_repository(url_a: str, url_b: str) -> bool:
    def norm(url: str) -> str:
        url = url.strip().lower().rstrip("/")
        url = re.sub(r"^git@([^:]+):", r"https://\1/", url)
        url = re.sub(r"^(?:https?|ssh|git)://(?:[^@/]+@)?", "https://", url)
        return url[:-4] if url.endswith(".git") else url
    return norm(url_a) == norm(url_b)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True)


def published_digest(root: Path, source: Path, version: str, published_copy: Path | None,
                     published_ref: str | None) -> tuple[str, str]:
    """(SHA-256, where it came from) of `exports/openim.rdf` as PUBLISHED at the
    release `version`. The reference can never be the file under test:

    - a `--published-copy` must be a different file from the source, outside the
      tree being checked (a downloaded copy of the release's file);
    - a git ref must be the release tag `v<version>` named in CITATION.cff, a real
      tag of this repository whose `origin` is the public repository CITATION.cff
      names (a repository with no origin is refused). A branch, HEAD or a commit is
      refused.
    """
    if published_copy is not None:
        copy = Path(published_copy)
        if not copy.is_file():
            raise EntryError(f"the published copy {copy} does not exist")
        if copy.resolve() == source.resolve() or (copy.exists() and source.exists() and copy.samefile(source)):
            raise EntryError(f"the published copy {copy} is the source file itself; it cannot confirm itself")
        try:
            copy.resolve().relative_to(root.resolve())
        except ValueError:
            pass
        else:
            raise EntryError(f"the published copy {copy} lies inside the tree being checked ({root}); "
                             f"give the file downloaded from the release, from outside the tree")
        return transform.file_sha256(copy), f"the supplied published copy {copy}"
    ref = published_ref or f"v{version}"
    if not _RELEASE_TAG.match(ref):
        raise EntryError(f"--published-ref {ref!r} is not a release tag (v<major>.<minor>.<patch>); "
                         f"a branch, HEAD or a commit can be the file under test")
    if ref != f"v{version}":
        raise EntryError(f"--published-ref {ref!r} is not the release CITATION.cff names (v{version})")
    if _git(root, "rev-parse", "-q", "--verify", f"refs/tags/{ref}^{{commit}}").returncode != 0:
        raise EntryError(
            f"cannot confirm the source is the published file: there is no tag {ref!r} in {root}. An entry may "
            f"only be assembled from a file that is already published at its release: run this from a clone "
            f"of the release tag, or give --published-copy <the file downloaded from the release>.")
    origin = _git(root, "remote", "get-url", "origin")
    public_url = read_citation_field(root, "repository-code")
    if origin.returncode != 0:
        raise EntryError(f"tag {ref!r} is in a repository with no origin; a tag only confirms a release when the "
                         f"repository's origin is the public repository ({public_url}). Clone the release tag "
                         f"from there, or give --published-copy <the file downloaded from the release>.")
    if not _same_repository(origin.stdout.decode("utf-8", "replace"), public_url):
        raise EntryError(f"tag {ref!r} is in a repository whose origin is not the public repository "
                         f"({public_url}); it is not a published release")
    blob = _git(root, "show", f"{ref}:exports/openim.rdf")
    if blob.returncode != 0:
        raise EntryError(
            f"cannot confirm the source is the published file: tag {ref!r} has no exports/openim.rdf "
            f"({blob.stderr.decode('utf-8', 'replace').strip()}). The release does not publish the file.")
    where = f"git tag {ref} of {public_url}"
    return hashlib.sha256(blob.stdout.replace(b"\r\n", b"\n")).hexdigest(), where


def require_published_source(root: Path, source: Path, version: str,
                             published_copy: Path | None = None, published_ref: str | None = None) -> str:
    """Refuse unless the SHA-256 of `source` equals that of the file published at
    release `version`. Returns a one-line statement of what it was checked against."""
    published, where = published_digest(root, source, version, published_copy, published_ref)
    actual = transform.file_sha256(source)
    if actual != published:
        raise EntryError(
            f"the source file {source} (SHA-256 {actual}) is not the file published at release v{version} "
            f"(SHA-256 {published}, from {where}); an entry would cite bytes the release does not contain. "
            f"Publish the release that carries this file, then assemble the entry from that release.")
    return f"source SHA-256 {actual} equals the file published at v{version} ({where})"


def find_licence(root: Path, explicit: Path | None) -> Path:
    """The public MIT licence: the pinned copy when this is the private source
    (whose root licence is not MIT), else the repository root licence."""
    candidates = [explicit] if explicit else [root / "ops" / "public-licence" / "LICENSE", root / "LICENSE"]
    for path in candidates:
        if path and path.is_file():
            text = path.read_text(encoding="utf-8")
            if text.lstrip().startswith("MIT License") and _MIT_MARKER in text:
                return path
            if explicit:
                raise EntryError(f"{path} is not the MIT licence")
    raise EntryError("the public MIT licence was not found (looked for ops/public-licence/LICENSE and LICENSE)")


def _counts(rows) -> dict:
    ops = [r for r in rows if r.kind == "object_property"]
    rule_items = Counter()
    for r in rows:
        for rule in set(r.rules):
            rule_items[rule] += 1
    return {
        "entities": sum(1 for r in rows if r.kind == "class" and r.shown == "yes"),
        "properties": sum(r.objects for r in rows if r.kind == "datatype_property")
                      + sum(r.objects - 1 for r in rows if r.kind == "class"),
        "relationships": sum(r.objects for r in ops),
        "from_columns": sum(r.objects for r in ops if "relationship-iri-qualify" in r.rules),
        "from_verbs_single": sum(r.objects for r in ops if r.shown == "yes" and "relationship-iri-qualify" not in r.rules),
        "from_verbs_expanded": sum(r.objects for r in ops if r.shown == "expanded"),
        "columns_dropped": sum(1 for r in ops if "relationship-duplicate-dropped" in r.rules),
        "key_entities": len({r.openim_code.split(".")[0] for r in rows
                             if r.kind == "datatype_property" and "identifier-key" in r.rules}),
        "composite_entities": sorted({r.openim_code.split(".")[0] for r in rows
                                      if r.kind == "datatype_property" and "identifier-key" in r.rules
                                      and "-column declared key" in r.reason}),
        "verbs_expanded": sum(1 for r in ops if r.shown == "expanded"),
        "rule_items": rule_items,
        "source_classes": sum(1 for r in rows if r.kind == "class"),
        "source_object_properties": len(ops),
        "source_datatype_properties": sum(1 for r in rows if r.kind == "datatype_property"),
        "not_drawn": sum(1 for r in rows if r.shown == "no"),
    }


def _n(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def inverse_clause(total: int, with_inverse: int) -> str:
    """How the entry says how many relationships have a declared inverse: literally."""
    if with_inverse == total:
        return "each with a declared inverse"
    return f"{with_inverse} of them in declared inverse pairs"


def metadata_text(version: str, c: dict, with_inverse: int) -> str:
    description = (
        f"A Playground adaptation of the Open Investment Model (OpenIM) ontology for institutional "
        f"investment management: {c['entities']} entity types, {c['properties']} properties and "
        f"{c['relationships']} named, directed relationships, {inverse_clause(c['relationships'], with_inverse)}. "
        f"FIBO-aligned. "
        f"Derived from OpenIM v{version} (MIT); not the canonical model, which is at "
        f"https://openinvestmentmodel.org/."
    )
    meta = {"name": NAME, "description": description, "category": CATEGORY, "icon": ICON,
            "tags": TAGS, "author": AUTHOR}
    assert list(meta) == METADATA_KEYS
    return json.dumps(meta, indent=2, ensure_ascii=False) + "\n"


def readme_text(info: dict, c: dict, repo_url: str, with_inverse: int) -> str:
    v = info["release_version"]
    limit = transform.NAME_MAX
    n = c["rule_items"]
    mapping_url = f"{repo_url}/raw/v{v}/exports/openim-playground-mapping.csv"
    not_drawn = ("all of them are drawn." if c["not_drawn"] == 0 else
                 f"{c['not_drawn']} of them are not drawn, each with its reason in the mapping.")
    adaptation_url = f"{repo_url}/raw/v{v}/exports/openim-playground.rdf"
    total = c["relationships"]
    parts = []
    if c["from_columns"]:
        parts.append(f"{_n(c['from_columns'], 'foreign-key column', 'foreign-key columns')} with no relation verb")
    parts.append(f"{_n(c['from_verbs_single'], 'relation verb', 'relation verbs')} between one pair of classes")
    parts.append(f"{_n(c['from_verbs_expanded'], 'relationship', 'relationships')} that stand for "
                 f"{_n(c['verbs_expanded'], 'relation verb', 'relation verbs')} over several classes")
    composition = ", ".join(parts[:-1]) + ", and " + parts[-1] if len(parts) > 1 else parts[0]
    composite_sentence = (
        "A composite key marks every one of its columns as identifier (the Playground accepts several identifier "
        "properties; its Fabric export uses the first), and the key columns are written first, in key order: "
        + ", ".join(c["composite_entities"]) + "."
        if c["composite_entities"] else "")
    fk_drawn = (f"A foreign-key column with no such verb is drawn ({_n(c['from_columns'], 'column', 'columns')})"
                if c["from_columns"] else "A foreign-key column with no such verb would be drawn (there is none in this release)")
    inverse_sentence = (f"every one of the {total} relationships is in a declared inverse pair." if with_inverse == total else
                        f"{with_inverse} of the {total} relationships are in declared inverse pairs, and the other "
                        f"{total - with_inverse} have no declared inverse.")
    lines = f"""\
# Open Investment Model (OpenIM): Playground adaptation

This entry is an adaptation of the Open Investment Model ontology for the Ontology Playground. It is not the canonical model.

The Open Investment Model (OpenIM) is an open, MIT-licensed, vendor-neutral reference model for institutional investment management: a decomposition of the buy-side firm into service domains and a canonical entity model. It aligns its entities to FIBO where the meaning matches and complements other standards such as ISDA CDM, ILPA, GIPS and ISO 20022. The canonical model is at https://openinvestmentmodel.org/ and the source repository is {repo_url}.

## Source

| | |
|---|---|
| OpenIM release | v{v} |
| Source file | {info['source_url']} |
| Source file SHA-256 | `{info['source_sha256']}` |
| `ontology.rdf` SHA-256 | `{info['rdf_sha256']}` |
| Mapping (one row per source class, object property and datatype property) | {mapping_url} |
| Same ontology file in the OpenIM repository | {adaptation_url} |

`ontology.rdf` is a byte copy of `exports/openim-playground.rdf`. The SHA-256 of the source file is of its published bytes with LF line endings.

## What is in the entry

{c['entities']} entity types, {c['properties']} properties and {c['relationships']} relationships, drawn from {c['source_classes']} classes, {c['source_datatype_properties']} datatype properties and {c['source_object_properties']} object properties of the source ontology (plus {_n(c['rule_items']['identifier-inherited'], 'inherited identifier property', 'inherited identifier properties')}, rule 2). Every source class, object property and datatype property has one row in the mapping; {not_drawn}

The relationships are {composition} (see rule 5). A relation verb and its inverse are separate relationships; {inverse_sentence}

## Regenerate

From a clone of the OpenIM repository at the release tag:

```
git clone --branch v{v} {repo_url}
cd open-investment-model
python -m pip install -r tools/playground/requirements.txt
python tools/playground/entry.py --out <folder>
```

The command reads `exports/openim.rdf`, `CITATION.cff` and the MIT licence, and refuses unless `exports/openim.rdf` is byte for byte the file published at the release tag (it compares SHA-256 digests with the file at git tag `v{v}`). It checks its own output before writing this folder. Running it twice gives identical files.

## What the adaptation changes

The Ontology Playground reads an ontology more narrowly than OWL allows, and limits names. The adaptation applies these rules, and only these; the mapping names the rules applied to each source item.

1. **Entity names.** An entity is named by its title in PascalCase, at most {limit} letters and digits and unique. A longer title loses its parenthetical gloss, then hyphenated words shrink to their initials, then words are abbreviated from a fixed table (for example `Agreement` to `Agmt`), so the name keeps the title's meaning; `ETF Authorised-Participant Agreement` becomes `ETFAPAgreement`, still the agreement. Only if a title still does not fit are trailing words dropped and, as the final step, the name cut at {limit} characters. The mapping records each shortened name with its full title and every step used. Each entity's description starts with its OpenIM code and title, so the canonical identifier is always in view. Entities are coloured by the prefix of their OpenIM code.
2. **Identifiers.** The Playground needs at least one identifier property per entity. The entity's own key, as the model declares it (the ontology marks each key column with `openim:keyPosition`), is marked as identifier ({_n(c['key_entities'], 'entity', 'entities')}). {composite_sentence} A specialisation's key is its parent's key, carried by a foreign key that is drawn as a relationship, so for the {_n(n['identifier-inherited'], 'entity', 'entities')} whose key is only a foreign key a property named and typed like the nearest ancestor's declared key is added to the entity and marked as identifier; these are the only properties in the entry that are not source datatype properties.
3. **Property names.** A property name over {limit} characters drops stop words, then abbreviates words from a fixed table (for example `basis_points` to `bps`, `percentage` to `pct`, `settlement` to `settle`) until it fits ({_n(n['property-name-shorten'], 'property', 'properties')}); an identifier keeps its `_id`, and the source name stays in the description and in the mapping. A name that clashes within its entity gets a numeric suffix ({_n(n['property-name-unique'], 'property', 'properties')}).
4. **Property types.** The Playground allows one type per property name across the ontology, so a name used with different types is widened to string ({_n(n['property-type-widen'], 'property', 'properties')}); the declared type stays in the description. A property whose range is `rdfs:Literal` (document, map or array) is typed string explicitly ({_n(n['property-type-literal'], 'property', 'properties')}).
5. **Relation verbs over several classes.** The Playground reads one class as a relationship's domain and one as its range, so a relation verb whose domain or range is a union of classes is drawn as one relationship per class pair, each a sub-property of the verb ({_n(n['union-expand'], 'verb', 'verbs')}). The identifiers of these relationships, and of the added identifier properties, are minted in the adaptation's own namespace, `{transform.PLAYGROUND_NS}`, never in the canonical OpenIM namespace. A verb whose domain and range are both unions is drawn for the pairs the source states as `rdfs:subClassOf`, which is how specialisation is shown ({_n(n['union-pairs-from-subclass'], 'verb', 'verbs')}). Declared inverses are kept pair by pair.
6. **Foreign keys, identifiers and labels.** A foreign-key column whose relation verb already draws the same two classes is not drawn a second time ({_n(c['columns_dropped'], 'column', 'columns')}; the mapping gives each one's reason and the verb it duplicates, and the column keeps its canonical IRI without a domain or range). {fk_drawn} under an identifier in the adaptation namespace qualified by its owner's OpenIM code, because the Playground identifies a relationship by the last part of its IRI and column names repeat. Relationship labels are lower snake_case at their full length. Each relationship carries its cardinality, taken from its relation verb (flipped for the inverse) and many-to-one for a foreign-key column without a verb.

Everything else in the source is kept as it is, including the FIBO alignment statements (`owl:equivalentClass` and `skos:closeMatch`), `rdfs:subClassOf` and `owl:inverseOf`. The ontology header names this file's source release, file and digest with `prov:wasDerivedFrom`, `dcterms:source` and `owl:versionInfo`.

## Licence

OpenIM is released under the MIT licence. The licence is in `LICENSE` in this folder and applies to this entry: Copyright (c) 2026 Georgios Antikatzidis.
"""
    return lines


def assemble(root: Path, out_dir: Path, licence: Path | None = None,
             published_copy: Path | None = None, published_ref: str | None = None) -> dict:
    root, out_dir = Path(root), Path(out_dir)
    licence_path = find_licence(root, licence)
    source = root / generate.SOURCE_PATH_IN_REPOSITORY
    if not source.is_file():
        raise EntryError(f"{source} not found: the released OpenIM ontology is the only input")
    from release_version import read_release_version
    pinned = require_published_source(root, source, read_release_version(root), published_copy, published_ref)
    info = generate.run(root)
    info["pinned"] = pinned
    # re-read the mapping the generator just wrote, so the README counts come from the file a reader can open
    import csv
    rows = []
    with open(info["out_mapping"], encoding="utf-8", newline="") as fh:
        for rec in csv.DictReader(fh):
            rows.append(transform.MappingRow(
                source_iri=rec["source_iri"], kind=rec["kind"], openim_code=rec["openim_code"],
                target_iri=rec["target_iri"], target_name=rec["target_name"], shown=rec["playground_shows"],
                objects=int(rec["playground_objects"]),
                rules=[x for x in rec["rules"].split(";") if x], reason=rec["reason"]))
    counts = _counts(rows)
    if counts["entities"] != info["stats"]["entities"] or counts["relationships"] != info["stats"]["relationships"]:
        raise EntryError("the mapping and the transform disagree on the counts")
    repo_url = read_citation_field(root, "repository-code").rstrip("/")
    with_inverse = info["stats"]["relationships_with_inverse"]
    readme = readme_text(info, counts, repo_url, with_inverse)
    metadata = metadata_text(info["release_version"], counts, with_inverse)
    for name, text in (("README.md", readme), ("metadata.json", metadata)):
        hit = _BUILD_ID.search(text)
        if hit:
            raise EntryError(f"{name} contains a build identifier: {hit.group(0)!r}")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ontology.rdf").write_bytes(Path(info["out_rdf"]).read_bytes())
    (out_dir / "LICENSE").write_bytes(licence_path.read_bytes())
    (out_dir / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    (out_dir / "metadata.json").write_text(metadata, encoding="utf-8", newline="\n")
    info["counts"] = counts
    info["entry_dir"] = out_dir
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--out", required=True, type=Path, help="the entry folder to write")
    ap.add_argument("--root", type=Path, default=_TOOLS.parent,
                    help="repository root (default: this repository)")
    ap.add_argument("--licence", type=Path, default=None,
                    help="the MIT licence to copy (default: ops/public-licence/LICENSE, else LICENSE)")
    ap.add_argument("--published-copy", type=Path, default=None,
                    help="the exports/openim.rdf as published at the release (a downloaded copy); "
                         "the source must be byte-identical to it")
    ap.add_argument("--published-ref", default=None,
                    help="the release tag v<version> named in CITATION.cff (the default); any other ref, "
                         "a branch or HEAD is refused")
    args = ap.parse_args(argv)
    try:
        info = assemble(args.root, args.out, args.licence, args.published_copy, args.published_ref)
    except (EntryError, generate.GenerationError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    c = info["counts"]
    print(f"entry for OpenIM v{info['release_version']}: {c['entities']} entities, "
          f"{c['properties']} properties, {c['relationships']} relationships -> {info['entry_dir']}")
    print(f"  {info['pinned']}")
    print(f"  ontology.rdf sha256 {info['rdf_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
