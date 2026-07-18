-- OpenIM property graph — Snowflake loader.
-- Generated from model/relations.md + the OpenIM entity model. Do not edit by hand.
--
-- VERIFIED (not assumed): Snowflake has no native ISO/IEC 9075-16 (SQL/PGQ)
-- support as of current Snowflake documentation (docs.snowflake.com, checked
-- 2026-07-18) -- no CREATE PROPERTY GRAPH, no GRAPH_TABLE anywhere in the SQL
-- reference or the 2026 SQL-improvements release notes. Graph capability on
-- Snowflake today is native-app / partner-integration (e.g. Neo4j Graph
-- Analytics for Snowflake, RelationalAI) or hand-built over relational tables --
-- never a first-party SQL/PGQ surface. This file is tables + COPY INTO + an
-- ordinary join / recursive-CTE traversal example -- no GRAPH_TABLE claim.

-- --- node + edge tables (columns exactly the property-graph CSV headers) ---

CREATE OR REPLACE TABLE openim_nodes (
  id VARCHAR NOT NULL,
  name VARCHAR,
  pack VARCHAR,
  owning_service_domain VARCHAR,
  fibo_class VARCHAR,
  specialises VARCHAR,
  PRIMARY KEY (id)
);

CREATE OR REPLACE TABLE openim_edges (
  edge_id VARCHAR NOT NULL,
  src VARCHAR NOT NULL,
  dst VARCHAR NOT NULL,
  rel_type VARCHAR,
  cardinality VARCHAR,
  kind VARCHAR,
  inverse VARCHAR,
  source_column VARCHAR,
  discriminator VARCHAR,
  discriminator_value VARCHAR,
  PRIMARY KEY (edge_id),
  FOREIGN KEY (src) REFERENCES openim_nodes (id),
  FOREIGN KEY (dst) REFERENCES openim_nodes (id)
);

-- --- load: file format + stage + COPY INTO from the sibling node/edge CSVs ---
-- Stage the two CSVs first, e.g.:
--   PUT file://openim-nodes.csv @openim_stage AUTO_COMPRESS=FALSE;
--   PUT file://openim-edges.csv @openim_stage AUTO_COMPRESS=FALSE;
-- (or stage them via an external stage / Snowsight upload -- any Snowflake
-- stage works; only the file names below need to match.)

CREATE OR REPLACE FILE FORMAT openim_csv_format
  TYPE = CSV
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  SKIP_HEADER = 1
  EMPTY_FIELD_AS_NULL = FALSE;

CREATE STAGE IF NOT EXISTS openim_stage
  FILE_FORMAT = openim_csv_format;

COPY INTO openim_nodes (id, name, pack, owning_service_domain, fibo_class, specialises)
  FROM @openim_stage/openim-nodes.csv
  FILE_FORMAT = (FORMAT_NAME = openim_csv_format)
  ON_ERROR = ABORT_STATEMENT;

COPY INTO openim_edges (edge_id, src, dst, rel_type, cardinality, kind, inverse, source_column, discriminator, discriminator_value)
  FROM @openim_stage/openim-edges.csv
  FILE_FORMAT = (FORMAT_NAME = openim_csv_format)
  ON_ERROR = ABORT_STATEMENT;

-- --- documented traversal query example (join + recursive CTE; no GRAPH_TABLE) ---

-- one-hop: every Holding/Position and the Instrument/Asset it POSITION_IN's.
SELECT
    src_node.id   AS src_id,   src_node.name   AS src_name,
    dst_node.id   AS dst_id,   dst_node.name   AS dst_name,
    e.rel_type, e.cardinality, e.inverse
FROM openim_edges e
JOIN openim_nodes src_node ON src_node.id = e.src
JOIN openim_nodes dst_node ON dst_node.id = e.dst
WHERE e.rel_type = 'POSITION_IN';

-- multi-hop: walk every self-referential SUBSIDIARY_OF chain up to its
-- ultimate parent (a recursive CTE -- Snowflake's stand-in for a GRAPH_TABLE
-- multi-hop MATCH, since no such construct exists on this engine).
WITH RECURSIVE subsidiary_chain (start_id, id, parent_id, depth) AS (
  SELECT id, id, NULL, 0
  FROM openim_nodes
  WHERE id NOT IN (SELECT src FROM openim_edges WHERE rel_type = 'SUBSIDIARY_OF')
  UNION ALL
  SELECT c.start_id, e.src, e.dst, c.depth + 1
  FROM openim_edges e
  JOIN subsidiary_chain c ON e.dst = c.id
  WHERE e.rel_type = 'SUBSIDIARY_OF'
)
SELECT * FROM subsidiary_chain ORDER BY start_id, depth;
