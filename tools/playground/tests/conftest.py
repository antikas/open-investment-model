"""Shared fixtures: the mini source ontology, built in memory and written to a
throw-away repository layout (`exports/openim.rdf` + `CITATION.cff`)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[2]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from playground import generate, transform  # noqa: E402
from playground.tests.mini import build_mini  # noqa: E402

CITATION = (
    'cff-version: 1.2.0\n'
    'title: "Example"\n'
    'version: "1.2.3"\n'
    'repository-code: "https://github.com/example/openim"\n'
)
LICENCE = (
    "MIT License\n\nCopyright (c) 2026 Example\n\n"
    "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
)


@pytest.fixture(scope="session")
def repo_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    (root / "exports").mkdir()
    (root / "CITATION.cff").write_text(CITATION, encoding="utf-8", newline="\n")
    (root / "LICENSE").write_text(LICENCE, encoding="utf-8", newline="\n")
    build_mini().serialize(destination=str(root / "exports" / "openim.rdf"), format="xml")
    return root


@pytest.fixture(scope="session")
def source_graph(repo_root):
    return transform.load_graph(repo_root / "exports" / "openim.rdf")


@pytest.fixture(scope="session")
def provenance(repo_root):
    return transform.Provenance("1.2.3", generate.source_url(repo_root, "1.2.3"),
                                transform.file_sha256(repo_root / "exports" / "openim.rdf"))


@pytest.fixture(scope="session")
def result(source_graph, provenance):
    return transform.transform(source_graph, provenance)


@pytest.fixture(scope="session")
def built(repo_root):
    """(result, rdf_text, csv_text) from the same entry point the command uses."""
    return generate.build(repo_root, repo_root / "exports" / "openim.rdf")


@pytest.fixture()
def out_graph(built):
    from rdflib import Graph
    g = Graph()
    g.parse(data=built[1], format="xml")
    return g
