"""Strict markdown parsers for the OpenIM model.

Public entry points:

- `parse_service_domains(repo_root)` — returns `ServiceDomainModel`
- `parse_entities(repo_root)` — returns `EntityModel`
- `parse_ownership_map(repo_root)` — returns `OwnershipMap`

Each parser raises `ParseError` (a subclass of `ValueError`) on any
structural surprise — unknown heading shapes (including unknown H2
section headings in an SD file), missing required fields, references
to non-existent SDs / entities, malformed ownership rows. Silent
skipping is not permitted.

Note on the d2 source: the attribute-level core ERD at
`model/diagrams/d2/core-erd.d2` is rendered directly by the D2 binary
in the CI workflow (`dist/entities/core/core-erd.svg`). The Hybrid D
generator does not parse the d2 source — the d2 binary is the renderer
of choice and the generator's ERD page links to its output. No Python
d2 reader is exported.
"""

from .errors import ParseError
from .service_domains import parse_service_domains, ServiceDomainModel, BusinessDomain, ServiceDomain
from .entities import parse_entities, EntityModel, Entity
from .ownership import parse_ownership_map, OwnershipMap, OwnershipRecord

__all__ = [
    "ParseError",
    "parse_service_domains",
    "ServiceDomainModel",
    "BusinessDomain",
    "ServiceDomain",
    "parse_entities",
    "EntityModel",
    "Entity",
    "parse_ownership_map",
    "OwnershipMap",
    "OwnershipRecord",
]
