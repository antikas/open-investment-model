-- OpenIM property graph — SQL/PGQ (ISO/IEC 9075-16, SQL:2023 Part 16).
-- Self-contained: this file defines the node and edge tables it then
-- projects a property graph over — it references no table it does not
-- itself create. Data loads from the sibling node/edge CSV files.

CREATE TABLE openim_nodes (
  id VARCHAR PRIMARY KEY,
  name VARCHAR,
  pack VARCHAR,
  owning_service_domain VARCHAR,
  fibo_class VARCHAR,
  specialises VARCHAR
);

CREATE TABLE openim_edges (
  edge_id VARCHAR,
  src VARCHAR,
  dst VARCHAR,
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

COPY openim_nodes (id, name, pack, owning_service_domain, fibo_class, specialises) FROM 'openim-nodes.csv' WITH (FORMAT csv, HEADER true);
COPY openim_edges (edge_id, src, dst, rel_type, cardinality, kind, inverse, source_column, discriminator, discriminator_value) FROM 'openim-edges.csv' WITH (FORMAT csv, HEADER true);

CREATE PROPERTY GRAPH openim_graph
  NODE TABLES (
    openim_nodes
      KEY (id)
      LABEL Entity PROPERTIES (id, name, pack, owning_service_domain, fibo_class, specialises)
  )
  EDGE TABLES (
    openim_edges
      KEY (edge_id)
      SOURCE KEY (src) REFERENCES openim_nodes (id)
      DESTINATION KEY (dst) REFERENCES openim_nodes (id)
      LABEL Relationship PROPERTIES (edge_id, src, dst, rel_type, cardinality, kind, inverse, source_column, discriminator, discriminator_value)
  );
