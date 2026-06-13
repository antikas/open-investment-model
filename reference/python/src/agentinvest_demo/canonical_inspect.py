"""The canonical-layer **inspector** read — list the canonical tables + sample one, READ-ONLY.

This is the data end the Operator UI's Canonical-data inspector reads. It exposes a *thin,
fixed* read over the dbt-built canonical store (the same duckdb file the NAV-strike marts read
from): the published **marts** (``mart_fund_nav``, ``mart_portfolio_holdings``,
``mart_performance_appraisal``) and the realised **staging entities** (``stg_eNN_*``), each with
its row count; and a **capped sample** of one selected table's rows. It is a viewer, NOT a query
console.

WHY A SEPARATE READER (not ``nav_marts_read.py`` / ``marts.py``). Those readers are NAV-specific
— they derive the §A1 NAV components / a windowed return for ONE fund. The inspector is a generic
*shape* read (which tables exist, how many rows, a sample) over the whole canonical layer. It
reuses their store-resolution + connect + unavailable-store contract (the SSOT for "where is the
canonical store" and "the data layer is not provisioned"), so there is one store convention, not
two — but the read itself is distinct, so it lives here rather than overloading the NAV reader.

READ-ONLY + NO INJECTION SURFACE (the load-bearing safety property). The inspector never writes
and never runs free-form SQL from a caller. The discipline:

- The set of inspectable tables is **derived from the store itself** — ``information_schema``
  filtered to the published marts (``main_marts.mart_*``) and the realised staging entities
  (``main_staging.stg_*``). The caller selects a table by its **fully-qualified name from that
  derived set**; a name not in the set is REFUSED (``UnknownTableError``) — it is never
  interpolated into SQL. So the allowlist is the real, current table set (no fabricated names,
  no drift), and an unknown / crafted name cannot reach the engine.
- A defensive identifier guard (``schema.table``, each part ``[a-z_][a-z0-9_]*``) is applied
  before the membership check as belt-and-braces — a name that is not a plain identifier pair is
  rejected outright, so even a bug that admitted an off-list name could not smuggle SQL.
- The sample is ``select * from <validated-fq-name> limit <capped>`` where ``<capped>`` is an
  ``int`` clamped to ``[1, SAMPLE_LIMIT_MAX]`` (never a string, never caller-controlled SQL) and
  ``<validated-fq-name>`` is a member of the derived set. There is no other caller-supplied SQL.

The connection is opened ``read_only=True`` (``marts._connect``), so even a defect could not
mutate the store. SYNTHETIC DATA: the canonical layer is the synthetic seed, not production data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Reuse marts.py's store-path resolution + connect + the unavailable-store contract — the SSOT
# for "where is the canonical store" and "the data layer is not provisioned". One convention.
from agentinvest_demo.marts import (
    MartsUnavailableError,
    _connect,  # the read-only connect helper (lazy duckdb import → catchable error)
    resolve_duckdb_path,
)

# The capped sample ceiling — the inspector shows a *sample*, never a full table dump. A caller
# may ask for fewer; a request above this (or non-positive) is clamped to this range, so the
# row count returned is bounded regardless of what the caller passes.
SAMPLE_LIMIT_MAX = 25
SAMPLE_LIMIT_DEFAULT = 25

# The inspectable schemas + table-name prefixes — the canonical "reader-facing" layer: the
# realised canonical entity model, the bi-temporal as-of layer, the computed marts, and the
# comparator/oracle feeds. The set of concrete tables is derived from the store within these
# (never hard-coded), so the allowlist is the live table set.
_MART_SCHEMA = "main_marts"
_MART_PREFIX = "mart_"
_STAGING_SCHEMA = "main_staging"
_STAGING_PREFIX = "stg_"
_INTERMEDIATE_SCHEMA = "main_intermediate"
_INTERMEDIATE_PREFIX = "int_"

# Within the staging schema, the realised canonical ENTITY model is the ``stg_eNN_*`` views
# (E-01..E-20 — the OpenIM canonical model made data); the remaining ``stg_*`` are the
# comparator/oracle/sample feeds. We split them so the inspector surfaces the canonical entity
# model as its own layer rather than burying the headline differentiator under "staging".
_ENTITY_RE = re.compile(r"^stg_e\d{2}_")

# A plain SQL identifier (lower snake, no quoting, no spaces, no punctuation). Applied to BOTH
# the schema and the table part before any membership check — a name that is not a plain
# identifier pair is rejected outright (defence in depth; the membership check is the primary gate).
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


class UnknownTableError(MartsUnavailableError):
    """The requested table is not an inspectable canonical table (not in the derived allowlist).

    A subclass of ``MartsUnavailableError`` so a caller can treat "store not provisioned" and
    "unknown/forbidden table" with one ``except`` if it wishes, while the handler distinguishes
    them (a 422 for an unprovisioned store; a 404 for an unknown table) — and so neither an
    unknown nor a crafted/injection name is ever interpolated into SQL.
    """


@dataclass(frozen=True)
class CanonicalTable:
    """One inspectable canonical table: its fully-qualified name, layer, and row count."""

    name: str  # the fully-qualified "schema.table" — the handle the sampler validates against
    schema: str
    table: str
    layer: str  # "canonical" | "bitemporal" | "mart" | "staging" — for the UI's grouping
    row_count: int


@dataclass(frozen=True)
class TableSample:
    """A capped sample of one canonical table: column headers + up to ``SAMPLE_LIMIT_MAX`` rows."""

    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str | None, ...], ...]  # cell values stringified for a stable wire shape
    row_count: int  # the table's TOTAL row count (the sample may be smaller)
    sampled: int  # how many rows this sample actually carries (≤ the requested cap)
    limit: int  # the effective cap applied


def _is_plain_identifier_pair(fq_name: str) -> bool:
    """True iff ``fq_name`` is ``schema.table`` with each part a plain lower-snake identifier."""
    parts = fq_name.split(".")
    if len(parts) != 2:
        return False
    return all(_IDENT.match(p) is not None for p in parts)


def _inspectable_layer(schema: str, table: str) -> str | None:
    """Return the inspector layer iff this schema+table is inspectable, else None.

    Layers: ``"canonical"`` (the realised E-NN entity model, ``stg_eNN_*``), ``"bitemporal"``
    (the as-of intermediate layer, ``int_*``), ``"mart"`` (the computed marts), and ``"staging"``
    (the comparator/oracle/sample feeds — the remaining ``stg_*``).
    """
    if schema == _MART_SCHEMA and table.startswith(_MART_PREFIX):
        return "mart"
    if schema == _STAGING_SCHEMA and table.startswith(_STAGING_PREFIX):
        return "canonical" if _ENTITY_RE.match(table) else "staging"
    if schema == _INTERMEDIATE_SCHEMA and table.startswith(_INTERMEDIATE_PREFIX):
        return "bitemporal"
    return None


def list_canonical_tables(duckdb_path: Path | None = None) -> list[CanonicalTable]:
    """List the inspectable canonical tables (marts + realised staging entities) with row counts.

    The set is DERIVED from the store's ``information_schema`` (filtered to the published marts and
    the realised staging entities), so it is the real, current table set — never a hard-coded list
    that could drift from the built store. Each table's row count is read with a parameter-free
    ``count(*)`` over a name that came from the store's own catalogue (not from any caller input),
    so this read carries no injection surface. Ordered marts-first, then staging, by name.
    """
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        cat = con.execute(
            """
            select table_schema, table_name
            from information_schema.tables
            where (table_schema = ? and table_name like ?)
               or (table_schema = ? and table_name like ?)
               or (table_schema = ? and table_name like ?)
            order by table_schema, table_name
            """,
            [
                _MART_SCHEMA, _MART_PREFIX + "%",
                _STAGING_SCHEMA, _STAGING_PREFIX + "%",
                _INTERMEDIATE_SCHEMA, _INTERMEDIATE_PREFIX + "%",
            ],
        ).fetchall()

        out: list[CanonicalTable] = []
        for schema, table in cat:
            schema_s = str(schema)
            table_s = str(table)
            layer = _inspectable_layer(schema_s, table_s)
            if layer is None:
                continue
            # The name came from the store's own catalogue and matches the inspectable filter;
            # the count read interpolates only that catalogue-derived, identifier-validated name.
            fq = f"{schema_s}.{table_s}"
            if not _is_plain_identifier_pair(fq):  # pragma: no cover - catalogue names are plain
                continue
            n = con.execute(f"select count(*) from {fq}").fetchone()
            row_count = int(n[0]) if n is not None else 0
            out.append(
                CanonicalTable(
                    name=fq,
                    schema=schema_s,
                    table=table_s,
                    layer=layer,
                    row_count=row_count,
                )
            )
    finally:
        con.close()

    # Group order for the inspector: the canonical entity model first (the headline differentiator),
    # then the bi-temporal as-of layer, the computed marts, and the comparator/oracle feeds last;
    # each group already name-ordered.
    _layer_order = {"canonical": 0, "bitemporal": 1, "mart": 2, "staging": 3}
    out.sort(key=lambda t: (_layer_order.get(t.layer, 9), t.name))
    return out


def _resolve_allowlisted_table(name: str, duckdb_path: Path | None = None) -> CanonicalTable:
    """Validate ``name`` against the store-derived inspectable set, or raise ``UnknownTableError``.

    THE injection gate. A name is accepted ONLY if (a) it is a plain ``schema.table`` identifier
    pair AND (b) it is a member of the live inspectable set (derived from the store). An unknown
    or crafted name (a quoted string, a sub-select, a different schema, a ``stg_``/``mart_`` name
    that does not actually exist) is REFUSED here and never interpolated into the sample SQL.
    """
    if not _is_plain_identifier_pair(name):
        raise UnknownTableError(
            f"'{name}' is not an inspectable canonical table — the table must be named as "
            f"'schema.table' (a published mart or a realised staging entity)."
        )
    for t in list_canonical_tables(duckdb_path):
        if t.name == name:
            return t
    raise UnknownTableError(
        f"'{name}' is not an inspectable canonical table — choose one of the listed marts or "
        f"realised staging entities. (Free-form table names / SQL are not accepted; this is a "
        f"read-only inspector, not a query console.)"
    )


def sample_canonical_table(
    name: str,
    *,
    limit: int = SAMPLE_LIMIT_DEFAULT,
    duckdb_path: Path | None = None,
) -> TableSample:
    """Read a CAPPED sample of one allowlisted canonical table — column headers + ≤ cap rows.

    The table ``name`` is validated against the store-derived allowlist FIRST (an unknown / crafted
    name is a clean ``UnknownTableError`` before any sample SQL). The sample is then
    ``select * from <allowlisted-fq-name> limit <clamped-int>`` — the only interpolated token is the
    validated, identifier-checked table name; the limit is an ``int`` clamped to
    ``[1, SAMPLE_LIMIT_MAX]`` (never a string, never caller SQL). There is no other caller-supplied
    SQL, so there is no injection surface. Cell values are stringified for a stable wire shape (no
    float drift; ``None`` preserved as ``None``).
    """
    table = _resolve_allowlisted_table(name, duckdb_path)
    capped = max(1, min(int(limit), SAMPLE_LIMIT_MAX))

    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        # `table.name` is a member of the store-derived allowlist (validated above) and is a plain
        # identifier pair — never caller-controlled SQL. The cap is an int. No injection surface.
        cur = con.execute(f"select * from {table.name} limit {capped}")
        columns = tuple(str(d[0]) for d in cur.description)
        raw_rows = cur.fetchall()
    finally:
        con.close()

    rows = tuple(
        tuple(None if cell is None else str(cell) for cell in row) for row in raw_rows
    )
    return TableSample(
        name=table.name,
        columns=columns,
        rows=rows,
        row_count=table.row_count,
        sampled=len(rows),
        limit=capped,
    )
