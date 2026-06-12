"""Graphviz layout helpers.

Uses the `graphviz` Python binding to invoke `dot` / `sfdp` via the
system PATH. The binding is a thin shell around the CLI; the binary
must be installed (Graphviz 12.x verified). The CI workflow installs
it via `apt-get install graphviz`.
"""
from __future__ import annotations

import subprocess
import shutil
from pathlib import Path


class LayoutError(RuntimeError):
    pass


def check_graphviz() -> None:
    """Raise LayoutError if `dot` / `sfdp` are not on PATH."""
    for binary in ("dot", "sfdp"):
        if shutil.which(binary) is None:
            raise LayoutError(
                f"Graphviz binary '{binary}' not found on PATH. "
                f"Install Graphviz 12.x (apt-get install graphviz / "
                f"https://gitlab.com/graphviz/graphviz/-/releases)."
            )


def render_svg(dot_source: str, engine: str = "dot", timeout: int = 90) -> str:
    """Run Graphviz `engine` over the DOT source and return SVG output.

    Pipes the DOT to stdin so we don't write the intermediate to disk.
    Raises `LayoutError` with stderr on non-zero exit.
    """
    if engine not in {"dot", "sfdp", "neato", "fdp", "circo", "twopi"}:
        raise LayoutError(f"unknown Graphviz engine {engine!r}")
    try:
        proc = subprocess.run(
            [engine, "-Tsvg"],
            input=dot_source.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise LayoutError(f"Graphviz {engine} not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise LayoutError(
            f"Graphviz {engine} timed out after {timeout}s — graph may "
            f"exceed layout-engine budget; consider per-BD baking only"
        ) from exc
    if proc.returncode != 0:
        raise LayoutError(
            f"Graphviz {engine} failed (exit {proc.returncode}): "
            f"{proc.stderr.decode('utf-8', errors='replace')[:1000]}"
        )
    return proc.stdout.decode("utf-8")
