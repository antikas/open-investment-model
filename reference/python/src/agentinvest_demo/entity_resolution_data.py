"""The entity-resolution data-access reader — the E-01 masters + the inbound feed, READ-ONLY.

The read seam the deterministic resolution cascade runs over. Two reads from the dbt-built canonical
store:

- the **standing reference data** — the E-01 legal-entity masters, each enriched with its resolution
  surfaces: the UNION of E-13 Entity Alias names (entity-side partition) + the E-01
  ``known_aliases``
  read-cache, and the UNION of the E-01 ``lei`` attribute + every E-14 External Identifier value
  (entity-side partition). This is the standing knowledge the cascade resolves an inbound record
  against (``read_master_entities``);
- the **inbound feed** — the ``stg_entity_resolution_feed`` records the cascade resolves
  (``read_resolution_feed``).

NOT THE ORACLE. This reader reads the FEED + the MASTERS the cascade resolves from — it deliberately
does **not** read ``entity_resolution_labels.{csv,json}`` (the labelled oracle). That manifest is
the
EVAL's ground truth (the score key), never an engine input — the cascade resolves from the feed's
observable evidence only (the oracle-integrity discipline; the answer-key never leaks into
the resolver). The eval (``test_entity_resolution_eval``) reads the oracle and scores the cascade's
decisions against it; the of-record path never sees it.

READ-ONLY. The connection is opened ``read_only=True`` (via ``marts._connect``); this module never
writes, never mutates. All queries are parameterless static reads over allowlisted staging models —
no free-form SQL, no injection surface. It REUSES ``marts.py``'s store-path resolution +
``_connect``
+ the ``MartsUnavailableError`` contract (one store convention).

SYNTHETIC, NOT PRODUCTION. The masters + feed are the synthetic resolution oracle; a green
read proves the typed reference-data + feed read, NOT a read against a live master-data platform.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from agentinvest_demo.marts import (
    MartsUnavailableError,
    _connect,
    resolve_duckdb_path,
)
from agentinvest_tools.entity_resolution import FeedRecord, MasterEntity

__all__ = [
    "MartsUnavailableError",
    "read_master_entities",
    "read_resolution_feed",
]


def _split_known_aliases(text: str | None) -> tuple[str, ...]:
    """Parse the E-01 ``known_aliases`` ``;``-joined read-cache into a tuple of names. Empty ->
    ()."""
    if not text:
        return ()
    return tuple(a.strip() for a in text.split(";") if a.strip())


def _parse_external_ids_map(text: str | None) -> tuple[str, ...]:
    """Parse the E-01 ``external_ids`` JSON map into the tuple of id VALUES. Malformed/empty ->
    ()."""
    if not text:
        return ()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return ()
    if not isinstance(parsed, dict):
        return ()
    return tuple(str(v) for v in parsed.values() if v is not None and str(v).strip())


def read_master_entities(duckdb_path: Path | None = None) -> tuple[MasterEntity, ...]:
    """Read the E-01 masters enriched with their E-13 alias + E-14 external-id surfaces — READ-ONLY.

    For each E-01 master, the alias set is the UNION of the E-13 Entity Alias names (entity-side
    partition: ``subject_type = 'legal_entity'``) + the E-01 ``known_aliases`` read-cache; the
    external-id set is the UNION of the E-01 ``lei`` attribute + every E-14 External Identifier
    value
    (entity-side partition). The model declares E-13 / E-14 canonical and the in-record arrays a
    derivable read-cache; reading the union means an alias / id present in EITHER surface resolves
    (the seed populates them asymmetrically — some only in the array, one only in E-13/E-14).
    """
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        master_rows = con.execute(
            """
            select entity_id, entity_name, lei, domicile, parent_entity_id,
                known_aliases, external_ids
            from main_staging.stg_e01_legal_entity
            order by entity_id
            """
        ).fetchall()
        alias_rows = con.execute(
            """
            select subject_id, alias_name
            from main_staging.stg_e13_entity_alias
            where subject_type = 'legal_entity'
            order by subject_id
            """
        ).fetchall()
        extid_rows = con.execute(
            """
            select subject_id, external_id
            from main_staging.stg_e14_external_identifier
            where subject_type = 'legal_entity'
            order by subject_id
            """
        ).fetchall()
    finally:
        con.close()

    e13_by_id: dict[str, list[str]] = {}
    for sid, alias_name in alias_rows:
        e13_by_id.setdefault(str(sid), []).append(str(alias_name))
    e14_by_id: dict[str, list[str]] = {}
    for sid, ext in extid_rows:
        e14_by_id.setdefault(str(sid), []).append(str(ext))

    masters: list[MasterEntity] = []
    for r in master_rows:
        entity_id = str(r[0])
        lei = None if r[2] is None or str(r[2]).strip() == "" else str(r[2])
        domicile = None if r[3] is None or str(r[3]).strip() == "" else str(r[3])
        parent = None if r[4] is None or str(r[4]).strip() == "" else str(r[4])
        aliases = {
            *_split_known_aliases(None if r[5] is None else str(r[5])),
            *e13_by_id.get(entity_id, []),
        }
        external_ids = {
            *_parse_external_ids_map(None if r[6] is None else str(r[6])),
            *e14_by_id.get(entity_id, []),
        }
        masters.append(
            MasterEntity(
                entity_id=entity_id,
                entity_name=str(r[1]),
                lei=lei,
                domicile=domicile,
                parent_entity_id=parent,
                aliases=tuple(sorted(aliases)),
                external_ids=tuple(sorted(external_ids)),
            )
        )
    return tuple(masters)


def read_resolution_feed(duckdb_path: Path | None = None) -> tuple[FeedRecord, ...]:
    """Read the inbound entity-resolution feed records the cascade resolves — READ-ONLY.

    The observable evidence only (name / lei / domicile / parent hint / external id / source /
    received_at) — no label, by construction (the label lives in the oracle, never read here).
    """
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        rows = con.execute(
            """
            select source_record_id, source_system, raw_name, raw_lei, raw_domicile,
                raw_parent_hint, raw_external_id, raw_id_type, received_at
            from main_staging.stg_entity_resolution_feed
            order by source_record_id
            """
        ).fetchall()
    finally:
        con.close()

    def _opt(value: object) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s or None

    feed: list[FeedRecord] = []
    for r in rows:
        received = r[8]
        feed.append(
            FeedRecord(
                source_record_id=str(r[0]),
                source_system=str(r[1]),
                raw_name=str(r[2]),
                raw_lei=_opt(r[3]),
                raw_domicile=_opt(r[4]),
                raw_parent_hint=_opt(r[5]),
                raw_external_id=_opt(r[6]),
                raw_id_type=_opt(r[7]),
                received_at=received if isinstance(received, date) else
                date.fromisoformat(str(received)),
            )
        )
    return tuple(feed)
