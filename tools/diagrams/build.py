#!/usr/bin/env python3
"""Hybrid D — OpenIM static-site diagram generator.

Parses the OpenIM model markdown, builds the capability and entity graphs
in memory, lays them out via Graphviz, and emits a static HTML+SVG site
under `dist/`. Markdown is the only authoritative source — no `.c4`
middleman, no DSL.

Usage:
    python tools/diagrams/build.py --out dist/

Exit codes:
    0  — site built; every declared BD, SD, Service Operation and entity
         has a corresponding rendered page and substantive coverage holds
         (each SD page lists every declared Service Operation by name)
    1  — generator error (parser raised, Graphviz failure, coverage gap)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Make this script runnable directly from the repo root.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR.parent))

from diagrams.parser import (  # noqa: E402
    parse_service_domains, parse_entities, parse_ownership_map,
)
from diagrams.parser.service_domains import validate_cross_refs  # noqa: E402
from diagrams.parser.entities import (  # noqa: E402
    validate_entity_references, validate_entity_sd_references,
)
from diagrams.parser.errors import ParseError  # noqa: E402
from diagrams.graph import build_capability_graph  # noqa: E402
from diagrams.render import render_site, RenderError  # noqa: E402
from diagrams.render.layout import LayoutError  # noqa: E402


def _repo_root() -> Path:
    """The repo root — three levels up from this file: tools/diagrams/build.py."""
    return _THIS_DIR.parent.parent


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def _expected_files(sd_model, entity_model) -> set[str]:
    """The set of files the coverage assertion checks for in dist/."""
    expected: set[str] = {"index.html", "landscape.html", "erd.html"}
    for bd in sd_model.business_domains:
        expected.add(f"bd-{bd.num:02d}.html")
    for sd in sd_model.all_sds():
        expected.add(f"sd-{sd.id[3:]}.html")
    for e in entity_model.entities:
        expected.add(f"entity-{e.id}.html")
    return expected


def _expected_ids(sd_model, entity_model) -> dict[str, set[str]]:
    """Return the declared id sets (for missing-id reports)."""
    return {
        "BD": {bd.id for bd in sd_model.business_domains},
        "SD": {sd.id for sd in sd_model.all_sds()},
        "SO": {f"{sd.id}#{ix}" for sd in sd_model.all_sds()
               for ix in range(1, len(sd.operations) + 1)},
        "Entity": {e.id for e in entity_model.entities},
    }


def _substantive_coverage_gaps(
    out: Path, sd_model, entity_model
) -> list[str]:
    """Walk emitted pages and verify substantive content beyond filenames.

    Each check returns a defect line if a declared element is structurally
    absent from its expected page.

    The SO and link checks match structurally, not by substring. Substring
    matching could pass a typo'd SO name (the typo substring-matches itself)
    or an SO name appearing in unrelated prose while the operations list was
    empty. The structural check anchors to `<li>` elements inside the
    operations list (for SO names) and to `<a href=...>` attribute
    values (for FK / member-SD / BD-landing links) using stdlib
    `html.parser`.

    Checks:
      (i)   Each SD page contains every declared Service Operation as
            an `<li>` element.
      (ii)  Each entity page contains an `<a href=...>` to every FK target.
      (iii) Each BD page contains an `<a href=...>` to every member SD.
      (iv)  The landscape page contains an `<a href=...>` to every BD landing.
    """
    import html as _html
    gaps: list[str] = []

    def _read(name: str) -> str | None:
        p = out / name
        if not p.is_file():
            return None  # filename-coverage layer already reports this
        return p.read_text(encoding="utf-8")

    # (i) SD pages — every declared SO name must appear as an <li> on the
    # SD page. Structural match: a substring check could be fooled by a
    # typo'd SO that substring-matches itself, or by an SO name appearing
    # in unrelated prose while the operations list is empty / wrong.
    for sd in sd_model.all_sds():
        page = _read(f"sd-{sd.id[3:]}.html")
        if page is None:
            continue
        li_texts = _extract_li_texts(page)
        for op in sd.operations:
            escaped = _html.escape(op.name, quote=True)
            # Each <li> text begins with the SO name; some templates suffix
            # it with " — purpose" or ": purpose" so compare on prefix /
            # exact / contained-as-token-not-substring forms.
            if not _li_carries_so_name(li_texts, op.name, escaped):
                gaps.append(
                    f"sd-{sd.id[3:]}.html: missing Service Operation "
                    f"'{op.name}' from {sd.id} (declared in markdown — "
                    f"not present as an <li> element under the operations "
                    f"list)"
                )

    # (ii) Entity pages — each FK target must appear as an <a href=...>
    # whose value resolves to entity-{fk}.html. Structural match against
    # the parsed href attribute, not raw substring.
    for ent in entity_model.entities:
        page = _read(f"entity-{ent.id}.html")
        if page is None:
            continue
        hrefs = _extract_anchor_hrefs(page)
        for fk in ent.fk_targets:
            target = f"entity-{fk}.html"
            if not _hrefs_resolve_to(hrefs, target):
                gaps.append(
                    f"entity-{ent.id}.html: missing FK drill-down "
                    f"to {fk} (declared in attribute schema — no <a> "
                    f"href resolving to {target})"
                )

    # (iii) BD pages — each member SD must appear as an <a href=...>
    # whose value resolves to sd-NN.M.html.
    for bd in sd_model.business_domains:
        page = _read(f"bd-{bd.num:02d}.html")
        if page is None:
            continue
        hrefs = _extract_anchor_hrefs(page)
        for sd in bd.service_domains:
            target = f"sd-{sd.id[3:]}.html"
            if not _hrefs_resolve_to(hrefs, target):
                gaps.append(
                    f"bd-{bd.num:02d}.html: missing drill-down to "
                    f"member {sd.id} (no <a> href resolving to "
                    f"{target})"
                )

    # (iv) Landscape — each BD landing must appear as an <a href=...>
    # whose value resolves to bd-NN.html.
    landscape = _read("landscape.html")
    if landscape is not None:
        landscape_hrefs = _extract_anchor_hrefs(landscape)
        for bd in sd_model.business_domains:
            target = f"bd-{bd.num:02d}.html"
            if not _hrefs_resolve_to(landscape_hrefs, target):
                gaps.append(
                    f"landscape.html: missing link to {bd.id} "
                    f"(no <a> href resolving to {target})"
                )
    return gaps


def _extract_li_texts(page: str) -> list[str]:
    """Return the text content of every <li> element in `page`.

    Uses stdlib `html.parser`; tolerates malformed HTML by returning
    whatever the parser captured. Text inside nested tags (e.g.
    `<li><strong>name</strong> — purpose</li>`) is concatenated.
    """
    from html.parser import HTMLParser

    class _LIExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._depth = 0
            self._buf: list[str] = []
            self.items: list[str] = []

        def handle_starttag(self, tag, attrs) -> None:  # noqa: ARG002
            if tag == "li":
                if self._depth == 0:
                    self._buf = []
                self._depth += 1

        def handle_endtag(self, tag) -> None:
            if tag == "li" and self._depth > 0:
                self._depth -= 1
                if self._depth == 0:
                    self.items.append("".join(self._buf).strip())
                    self._buf = []

        def handle_data(self, data) -> None:
            if self._depth > 0:
                self._buf.append(data)

    parser = _LIExtractor()
    try:
        parser.feed(page)
        parser.close()
    except Exception:  # noqa: BLE001
        # On a malformed page, return what we collected; the caller will
        # report missing items naturally.
        pass
    return parser.items


def _li_carries_so_name(li_texts: list[str], name: str, escaped: str) -> bool:
    """Return True if any <li> text exactly carries the SO name.

    Templates render SOs as `<li>{name}</li>` or `<li>{name} — purpose</li>`
    or `<li>{name}: purpose</li>`. Accept any of these — but reject the
    case where the name appears only inside unrelated prose (the
    false-negative a plain substring check fails to catch).
    """
    for li in li_texts:
        stripped = li.strip()
        if stripped == name or stripped == escaped:
            return True
        # Tolerate a trailing separator: `name — purpose`, `name: purpose`,
        # `name - purpose`, `name. purpose`. The separator anchors the
        # name to the start of the <li>, ruling out the "name buried in
        # unrelated prose" false negative.
        for sep in (" — ", " – ", " - ", ": ", ". "):
            if stripped.startswith(name + sep) or stripped.startswith(escaped + sep):
                return True
    return False


def _extract_anchor_hrefs(page: str) -> set[str]:
    """Return every `href` (and SVG `xlink:href`) on every `<a>` element.

    Captures both HTML `<a href="...">` (in the page chrome) and SVG
    `<a xlink:href="...">` (Graphviz emits the SVG-namespace form for
    node drill-down links inside the embedded `<svg>`). Either suffices
    for substantive coverage.
    """
    from html.parser import HTMLParser

    class _AHrefExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.hrefs: set[str] = set()

        def handle_starttag(self, tag, attrs) -> None:
            if tag == "a":
                for k, v in attrs:
                    if v is None:
                        continue
                    if k == "href" or k.endswith(":href") or k == "xlink:href":
                        self.hrefs.add(v)

    parser = _AHrefExtractor()
    try:
        parser.feed(page)
        parser.close()
    except Exception:  # noqa: BLE001
        pass
    return parser.hrefs


def _hrefs_resolve_to(hrefs: set[str], target: str) -> bool:
    """Return True if any href in `hrefs` resolves to `target`.

    Accepts the common forms: `target`, `./target`, `/target`, and the
    same with a `#fragment` suffix. The href set is rooted at the
    rendered HTML's directory so cross-directory drill-downs (entities
    in a subdir) are not in current scope.
    """
    for h in hrefs:
        bare = h.split("#", 1)[0].split("?", 1)[0]
        if bare == target:
            return True
        if bare.endswith("/" + target):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the OpenIM Hybrid D diagram site.")
    ap.add_argument("--out", required=True, type=Path,
                    help="Output directory (typically dist/).")
    ap.add_argument("--no-fail-on-coverage", action="store_true",
                    help="Print coverage gaps but exit 0 (CI debugging only).")
    args = ap.parse_args(argv)

    root = _repo_root()
    out: Path = args.out

    start = time.perf_counter()
    print(f"OpenIM Hybrid D generator — repo: {root}")
    print(f"  parsing markdown...")

    try:
        sd_model = parse_service_domains(root)
        validate_cross_refs(sd_model)
        entity_model = parse_entities(root)
        validate_entity_references(entity_model)
        validate_entity_sd_references(entity_model, {sd.id for sd in sd_model.all_sds()})
        ownership = parse_ownership_map(root)
    except ParseError as exc:
        _err(f"parser error — {exc}")
        return 1

    print(f"    {len(sd_model.business_domains)} Business Domains")
    print(f"    {len(sd_model.all_sds())} Service Domains")
    print(f"    {len(sd_model.all_sos())} Service Operations")
    print(f"    {len(entity_model.entities)} Entities")
    print(f"    {len(ownership.records)} ownership records")

    bundle = build_capability_graph(sd_model, entity_model)
    print(f"  capability graph: {len(bundle.edges)} edges")
    print(f"    cross-BD edges: {len(bundle.cross_bd_edges())} "
          f"(over {len(bundle.cross_bd_pairs())} BD pairs)")

    print(f"  laying out + rendering to {out}/ ...")
    try:
        rendered = render_site(out, sd_model, entity_model, ownership, bundle)
    except (RenderError, LayoutError) as exc:
        _err(f"render error — {exc}")
        return 1

    # Coverage assertion — filename level (every declared BD / SD / entity
    # has a corresponding page in dist/).
    emitted = {p.name for p in out.iterdir() if p.is_file() and p.suffix == ".html"}
    expected = _expected_files(sd_model, entity_model)
    missing = expected - emitted
    if missing:
        _err(f"coverage assertion failed — {len(missing)} expected pages missing:")
        for name in sorted(missing):
            _err(f"    - {name}")
        if not args.no_fail_on_coverage:
            return 1
    extra = emitted - expected
    if extra:
        # Extra files are allowed (svg-pan-zoom.min.js etc.) but flag .html outliers.
        print(f"  note: {len(extra)} extra HTML files present (kept).")

    # Substantive coverage — every declared SO appears on its SD page; every
    # FK / member-SD / BD link resolves.
    gaps = _substantive_coverage_gaps(out, sd_model, entity_model)
    if gaps:
        _err(f"substantive coverage failed — {len(gaps)} gap(s):")
        for g in gaps:
            _err(f"    - {g}")
        if not args.no_fail_on_coverage:
            return 1

    elapsed = time.perf_counter() - start
    print(f"  done — {sum(len(v) for v in rendered.values())} pages, "
          f"{elapsed:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
