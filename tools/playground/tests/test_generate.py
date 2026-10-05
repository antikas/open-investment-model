"""The commands: byte-identical output across processes, the failure exit, and
the catalogue entry folder."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import URIRef

from playground import entry, generate, transform

_TOOLS = Path(__file__).resolve().parents[2]
GENERATE = _TOOLS / "playground" / "generate.py"
ENTRY = _TOOLS / "playground" / "entry.py"


def run_generate(root: Path, out_dir: Path, hash_seed: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    return subprocess.run(
        [sys.executable, str(GENERATE), "--root", str(root),
         "--out-rdf", str(out_dir / "o.rdf"), "--out-mapping", str(out_dir / "m.csv")],
        capture_output=True, text=True, env=env)


def test_two_runs_in_separate_processes_are_byte_identical(repo_root, built, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    pa, pb = run_generate(repo_root, a, "1"), run_generate(repo_root, b, "12345")
    assert pa.returncode == 0, pa.stderr
    assert pb.returncode == 0, pb.stderr
    assert (a / "o.rdf").read_bytes() == (b / "o.rdf").read_bytes()
    assert (a / "m.csv").read_bytes() == (b / "m.csv").read_bytes()
    # and the same bytes as the in-process build
    assert (a / "o.rdf").read_bytes() == built[1].encode("utf-8")
    assert (a / "m.csv").read_bytes() == built[2].encode("utf-8")
    assert b"\r" not in (a / "o.rdf").read_bytes() + (a / "m.csv").read_bytes()


def test_the_command_fails_without_the_released_ontology(tmp_path):
    (tmp_path / "CITATION.cff").write_text('version: "1.0.0"\nrepository-code: "https://example.org/x"\n', encoding="utf-8")
    p = subprocess.run([sys.executable, str(GENERATE), "--root", str(tmp_path)], capture_output=True, text=True)
    assert p.returncode == 1 and "not found" in p.stderr


def test_the_command_exits_non_zero_and_writes_nothing_when_a_check_fails(repo_root, tmp_path, monkeypatch):
    from playground import verify
    monkeypatch.setattr(verify, "verify_all", lambda *a, **k: ["planted defect"])
    out_rdf, out_csv = tmp_path / "o.rdf", tmp_path / "m.csv"
    with pytest.raises(generate.GenerationError, match="planted defect"):
        generate.run(repo_root, out_rdf=out_rdf, out_mapping=out_csv)
    assert not out_rdf.exists() and not out_csv.exists()


def test_the_mapping_csv_has_a_header_and_one_row_per_source_construct(built):
    rows = list(csv.reader(built[2].splitlines()))
    assert rows[0] == transform.MAPPING_HEADER
    assert len(rows) - 1 == len(built[0].rows)
    assert all(len(r) == len(transform.MAPPING_HEADER) for r in rows)


# --- the catalogue entry folder --------------------------------------------------------------

@pytest.fixture(scope="session")
def published_copy(repo_root, tmp_path_factory):
    """The release's published file, as downloaded to a place outside the tree."""
    f = tmp_path_factory.mktemp("published") / "openim.rdf"
    f.write_bytes((repo_root / "exports" / "openim.rdf").read_bytes())
    return f


@pytest.fixture(scope="module")
def entry_dir(repo_root, published_copy, tmp_path_factory):
    out = tmp_path_factory.mktemp("entry")
    info = entry.assemble(repo_root, out, published_copy=published_copy)
    return out, info


def test_the_entry_has_exactly_the_four_files(entry_dir):
    out, _ = entry_dir
    assert sorted(p.name for p in out.iterdir()) == ["LICENSE", "README.md", "metadata.json", "ontology.rdf"]


def test_the_entry_licence_is_a_byte_copy(entry_dir, repo_root):
    out, _ = entry_dir
    assert (out / "LICENSE").read_bytes() == (repo_root / "LICENSE").read_bytes()


def test_the_entry_ontology_is_a_byte_copy_of_the_export(entry_dir, repo_root, built):
    out, _ = entry_dir
    exported = (repo_root / "exports" / "openim-playground.rdf").read_bytes()
    assert (out / "ontology.rdf").read_bytes() == exported == built[1].encode("utf-8")


def test_the_metadata_has_only_the_schema_fields_and_counts_from_the_mapping(entry_dir, built):
    out, _ = entry_dir
    out_dir = out
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    assert list(meta) == ["name", "description", "category", "icon", "tags", "author"]
    assert meta["category"] == "finance" and meta["author"] == "antikas"
    rows = list(csv.DictReader(built[2].splitlines()))
    entities = sum(1 for r in rows if r["kind"] == "class" and r["playground_shows"] == "yes")
    props = (sum(int(r["playground_objects"]) for r in rows if r["kind"] == "datatype_property")
             + sum(int(r["playground_objects"]) - 1 for r in rows if r["kind"] == "class"))
    rels = sum(int(r["playground_objects"]) for r in rows if r["kind"] == "object_property")
    assert f"{entities} entity types, {props} properties and {rels} named" in meta["description"]
    # every qualifier in the claim is literally true of the written ontology
    from rdflib import Graph
    from rdflib.namespace import OWL
    from playground import verify
    out = Graph()
    out.parse(str(out_dir / "ontology.rdf"), format="xml")
    drawn = verify.playground_view(out)["relationships"]
    paired = sum(1 for r in drawn if list(out.objects(URIRef(r["iri"]), OWL.inverseOf)))
    assert len(drawn) == rels and 0 < paired < len(drawn)     # the mini ontology has a foreign key with no verb
    assert f"{rels} named, directed relationships, {paired} of them in declared inverse pairs." in meta["description"]
    assert "with declared inverses" not in meta["description"]


def test_the_readme_names_the_release_the_digests_and_the_command(entry_dir, repo_root):
    out, info = entry_dir
    text = (out / "README.md").read_text(encoding="utf-8")
    src_sha = hashlib.sha256((repo_root / "exports" / "openim.rdf").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    rdf_sha = hashlib.sha256((out / "ontology.rdf").read_bytes()).hexdigest()
    assert src_sha in text and rdf_sha in text
    assert "v1.2.3" in text and info["source_url"] in text
    assert "python tools/playground/entry.py --out" in text
    assert "relationships are in declared inverse pairs" in text and "have no declared inverse" in text
    assert "reads `exports/openim.rdf`, `CITATION.cff` and the MIT licence" in text
    assert "MIT" in text and "not the canonical model" in text


def test_the_entry_text_has_no_build_identifiers(entry_dir):
    out, _ = entry_dir
    for name in ("README.md", "metadata.json", "ontology.rdf"):
        text = (out / name).read_text(encoding="utf-8")
        assert not re.search(r"OIM[-]\d|ADR[-]\d|cycle[-]\d", text), name


def test_a_licence_that_is_not_mit_is_refused(tmp_path):
    bad = tmp_path / "LICENSE"
    bad.write_text("All rights reserved.\n", encoding="utf-8")
    with pytest.raises(entry.EntryError):
        entry.find_licence(tmp_path, bad)


def test_the_entry_command_runs_from_the_command_line(repo_root, published_copy, tmp_path):
    published = published_copy
    p = subprocess.run([sys.executable, str(ENTRY), "--root", str(repo_root), "--out", str(tmp_path / "e"),
                        "--published-copy", str(published)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert (tmp_path / "e" / "ontology.rdf").is_file()
    assert "equals the file published at v1.2.3" in p.stdout


# --- the entry is only assembled from a file that is already published ---------------------------

def test_entry_refuses_when_nothing_confirms_the_source_is_published(repo_root, tmp_path):
    with pytest.raises(entry.EntryError, match="cannot confirm the source is the published file"):
        entry.assemble(repo_root, tmp_path / "e")
    p = subprocess.run([sys.executable, str(ENTRY), "--root", str(repo_root), "--out", str(tmp_path / "e2")],
                       capture_output=True, text=True)
    assert p.returncode == 1 and "published" in p.stderr
    assert not (tmp_path / "e").exists() and not (tmp_path / "e2").exists()


def test_a_published_file_that_differs_by_one_byte_is_refused(repo_root, tmp_path):
    other = tmp_path / "elsewhere" / "published.rdf"
    other.parent.mkdir()
    other.write_bytes((repo_root / "exports" / "openim.rdf").read_bytes() + b"<!-- changed -->\n")
    with pytest.raises(entry.EntryError, match="is not the file published at release v1.2.3"):
        entry.assemble(repo_root, tmp_path / "e", published_copy=other)
    assert not (tmp_path / "e").exists()


def test_a_published_copy_with_windows_line_endings_is_the_same_file(repo_root, tmp_path):
    crlf = tmp_path / "elsewhere" / "published.rdf"
    crlf.parent.mkdir()
    crlf.write_bytes((repo_root / "exports" / "openim.rdf").read_bytes().replace(b"\n", b"\r\n"))
    info = entry.assemble(repo_root, tmp_path / "e", published_copy=crlf)
    assert "equals the file published at v1.2.3" in info["pinned"]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), "-c", "user.email=a@example.org", "-c", "user.name=a", *args],
                   check=True, capture_output=True)


def _release_clone(repo_root: Path, dest: Path, tag: str = "v1.2.3",
                   origin: str | None = "https://github.com/example/openim.git") -> Path:
    import shutil
    (dest / "exports").mkdir(parents=True)
    for name in ("CITATION.cff", "LICENSE"):
        shutil.copyfile(repo_root / name, dest / name)
    shutil.copyfile(repo_root / "exports" / "openim.rdf", dest / "exports" / "openim.rdf")
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", "release")
    _git(dest, "tag", tag)
    if origin:
        _git(dest, "remote", "add", "origin", origin)
    return dest


def test_a_clone_at_the_release_tag_assembles_with_no_extra_argument(repo_root, tmp_path):
    clone = _release_clone(repo_root, tmp_path / "clone")
    info = entry.assemble(clone, tmp_path / "e")
    assert "git tag v1.2.3 of https://github.com/example/openim" in info["pinned"]


def test_a_file_changed_after_the_tag_is_refused(repo_root, tmp_path):
    clone = _release_clone(repo_root, tmp_path / "clone")
    rdf = clone / "exports" / "openim.rdf"
    rdf.write_bytes(rdf.read_bytes() + b"<!-- regenerated after the release -->\n")
    with pytest.raises(entry.EntryError, match="is not the file published at release v1.2.3"):
        entry.assemble(clone, tmp_path / "e")


def test_a_repository_without_the_release_tag_is_refused(repo_root, tmp_path):
    clone = _release_clone(repo_root, tmp_path / "clone", tag="v9.9.9")
    with pytest.raises(entry.EntryError, match="cannot confirm"):
        entry.assemble(clone, tmp_path / "e")


def test_the_inverse_wording_is_literally_true_both_ways():
    assert entry.inverse_clause(428, 428) == "each with a declared inverse"
    assert entry.inverse_clause(10, 8) == "8 of them in declared inverse pairs"


# --- the gate cannot be satisfied by the file under test -----------------------------------------

def test_a_published_copy_that_is_the_source_itself_is_refused(repo_root, tmp_path):
    with pytest.raises(entry.EntryError, match="is the source file itself"):
        entry.assemble(repo_root, tmp_path / "e", published_copy=repo_root / "exports" / "openim.rdf")
    assert not (tmp_path / "e").exists()


def test_a_published_copy_reached_by_another_path_to_the_source_is_refused(repo_root, tmp_path):
    detour = repo_root / "exports" / ".." / "exports" / "openim.rdf"
    with pytest.raises(entry.EntryError, match="is the source file itself"):
        entry.assemble(repo_root, tmp_path / "e", published_copy=detour)


def test_a_published_copy_inside_the_tree_is_refused_even_as_a_copy(repo_root, tmp_path):
    import shutil
    tree = tmp_path / "tree"                       # a scratch tree with its own CITATION.cff
    (tree / "exports").mkdir(parents=True)
    for name in ("CITATION.cff", "LICENSE"):
        shutil.copyfile(repo_root / name, tree / name)
    shutil.copyfile(repo_root / "exports" / "openim.rdf", tree / "exports" / "openim.rdf")
    inside = tree / "exports" / "copy-of-openim.rdf"
    inside.write_bytes((tree / "exports" / "openim.rdf").read_bytes())
    with pytest.raises(entry.EntryError, match="lies inside the tree being checked"):
        entry.assemble(tree, tmp_path / "e", published_copy=inside)
    # and nothing was written into the shared fixture tree
    assert sorted(p.name for p in (repo_root / "exports").iterdir() if p.name.startswith("copy-of")) == []


def test_a_tag_in_a_repository_with_no_origin_is_refused(repo_root, tmp_path):
    clone = _release_clone(repo_root, tmp_path / "clone", origin=None)
    with pytest.raises(entry.EntryError, match="no origin"):
        entry.assemble(clone, tmp_path / "e")
    assert not (tmp_path / "e").exists()


@pytest.mark.parametrize("ref", ["HEAD", "master", "main", "origin/main", "abc1234", "v1.2", "release-1.2.3"])
def test_a_ref_that_is_not_a_release_tag_is_refused(repo_root, tmp_path, ref):
    clone = _release_clone(repo_root, tmp_path / "clone")
    with pytest.raises(entry.EntryError, match="is not a release tag"):
        entry.assemble(clone, tmp_path / "e", published_ref=ref)


def test_a_release_tag_of_another_version_is_refused(repo_root, tmp_path):
    clone = _release_clone(repo_root, tmp_path / "clone")
    _git(clone, "tag", "v0.0.1")
    with pytest.raises(entry.EntryError, match="is not the release CITATION.cff names"):
        entry.assemble(clone, tmp_path / "e", published_ref="v0.0.1")


def test_a_branch_named_like_a_tag_is_not_a_tag(repo_root, tmp_path):
    clone = _release_clone(repo_root, tmp_path / "clone", tag="v9.9.9")
    _git(clone, "branch", "v1.2.3")                      # a branch, not a tag
    with pytest.raises(entry.EntryError, match="cannot confirm"):
        entry.assemble(clone, tmp_path / "e")


def test_a_tag_in_a_repository_that_is_not_the_public_one_is_refused(repo_root, tmp_path):
    clone = _release_clone(repo_root, tmp_path / "clone")
    _git(clone, "remote", "set-url", "origin", "https://example.org/someone-else/openim.git")
    with pytest.raises(entry.EntryError, match="origin is not the public repository"):
        entry.assemble(clone, tmp_path / "e")


def test_a_tag_in_a_clone_of_the_public_repository_is_accepted(repo_root, tmp_path):
    clone = _release_clone(repo_root, tmp_path / "clone")
    _git(clone, "remote", "set-url", "origin", "git@github.com:example/openim.git")      # CITATION.cff: github.com/example/openim
    info = entry.assemble(clone, tmp_path / "e")
    assert "git tag v1.2.3 of https://github.com/example/openim" in info["pinned"]
