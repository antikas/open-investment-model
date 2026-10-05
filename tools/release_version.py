"""The release version, read from the one place it is declared.

`CITATION.cff` carries the release `version` (and the public `repository-code`
URL). Every tool that needs to state which release it describes reads it
through this module, so a release is declared once and nothing hard-codes it.

The file is YAML, but only its top-level scalar fields are needed here, so a
small line reader replaces a YAML dependency.
"""
from __future__ import annotations

import re
from pathlib import Path

_SCALAR_RE = re.compile(r'^(?P<key>[A-Za-z][A-Za-z0-9_-]*):\s*(?P<value>.*?)\s*$')
_VERSION_RE = re.compile(r'^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$')


def read_citation_field(root: Path, key: str) -> str:
    """Return the top-level scalar `key` of `<root>/CITATION.cff`, unquoted."""
    path = Path(root) / "CITATION.cff"
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _SCALAR_RE.match(line)
        if m and m.group("key") == key:
            value = m.group("value")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value:
                return value
    raise KeyError(f"{path}: no top-level `{key}` field")


def read_release_version(root: Path) -> str:
    """The release version (`CITATION.cff` `version`), validated as semver."""
    version = read_citation_field(root, "version")
    if not _VERSION_RE.match(version):
        raise ValueError(f"CITATION.cff version {version!r} is not a semantic version")
    return version
