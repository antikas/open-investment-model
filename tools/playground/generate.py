#!/usr/bin/env python3
"""Generate the Ontology Playground adaptation of the released OpenIM ontology.

    python tools/playground/generate.py

reads `exports/openim.rdf` (the released OpenIM ontology) and `CITATION.cff` (the
release version and the public repository address) and writes

    exports/openim-playground.rdf          the ontology in the form the Playground reads
    exports/openim-playground-mapping.csv  one row per source class, object property
                                           and datatype property, with the rules applied

The output is checked before it is written (see `verify.py`); a defect stops the
run with a non-zero exit and nothing is written. Running it twice, in separate
processes, gives byte-identical files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[1]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from playground import rdfxml, transform, verify  # noqa: E402
from release_version import read_citation_field, read_release_version  # noqa: E402

SOURCE_PATH_IN_REPOSITORY = "exports/openim.rdf"


class GenerationError(Exception):
    pass


def mapping_csv(rows) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(transform.MAPPING_HEADER)
    for r in rows:
        w.writerow(r.csv_fields())
    return buf.getvalue()


def source_url(root: Path, version: str) -> str:
    repo = read_citation_field(root, "repository-code").rstrip("/")
    return f"{repo}/raw/v{version}/{SOURCE_PATH_IN_REPOSITORY}"


def build(root: Path, source: Path):
    """Run the transform and its checks. Returns (result, rdf_text, csv_text)."""
    version = read_release_version(root)
    prov = transform.Provenance(
        release_version=version,
        source_url=source_url(root, version),
        source_sha256=transform.file_sha256(source),
    )
    src_graph = transform.load_graph(source)
    result = transform.transform(src_graph, prov)
    rdf_text = rdfxml.write(result.triples)

    from rdflib import Graph
    out_graph = Graph()
    out_graph.parse(data=rdf_text, format="xml")
    defects = verify.verify_all(src_graph, out_graph, result.rows)
    defects += verify.check_traceability(
        result.source_triples, transform.flatten(out_graph), result.ledger, transform.RULES)
    if defects:
        raise GenerationError("the adaptation failed its checks:\n  " + "\n  ".join(defects[:40]))
    return result, rdf_text, mapping_csv(result.rows)


def run(root: Path, source: Path | None = None, out_rdf: Path | None = None,
        out_mapping: Path | None = None) -> dict:
    root = Path(root)
    source = Path(source) if source else root / SOURCE_PATH_IN_REPOSITORY
    out_rdf = Path(out_rdf) if out_rdf else root / "exports" / "openim-playground.rdf"
    out_mapping = Path(out_mapping) if out_mapping else root / "exports" / "openim-playground-mapping.csv"
    if not source.is_file():
        raise GenerationError(f"{source} not found: the released OpenIM ontology is the only input")
    result, rdf_text, csv_text = build(root, source)
    for path, text in ((out_rdf, rdf_text), (out_mapping, csv_text)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return {
        "stats": result.stats,
        "release_version": result.provenance.release_version,
        "source_url": result.provenance.source_url,
        "source_sha256": result.provenance.source_sha256,
        "rdf_sha256": hashlib.sha256(rdf_text.encode("utf-8")).hexdigest(),
        "mapping_sha256": hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
        "out_rdf": out_rdf,
        "out_mapping": out_mapping,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=_TOOLS.parent,
                    help="repository root (holds exports/ and CITATION.cff); default: this repository")
    ap.add_argument("--source", type=Path, default=None,
                    help="the released ontology (default: <root>/exports/openim.rdf)")
    ap.add_argument("--out-rdf", type=Path, default=None)
    ap.add_argument("--out-mapping", type=Path, default=None)
    args = ap.parse_args(argv)
    try:
        info = run(args.root, args.source, args.out_rdf, args.out_mapping)
    except (GenerationError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    s = info["stats"]
    print(f"Playground adaptation of OpenIM v{info['release_version']}")
    print(f"  source: {info['source_url']}")
    print(f"  source sha256: {info['source_sha256']}")
    print(f"  {s['entities']} entities, {s['properties']} properties, {s['relationships']} relationships "
          f"(from {s['source_classes']} classes, {s['source_datatype_properties']} datatype properties, "
          f"{s['source_object_properties']} object properties)")
    print(f"  wrote {info['out_rdf']}  sha256 {info['rdf_sha256']}")
    print(f"  wrote {info['out_mapping']}  sha256 {info['mapping_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
