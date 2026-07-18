# OpenIM as the Agent-Navigation Map (reference instance)

> **This is the OpenIM realisation of a first-class agentic-architecture concept.** The concept — *the ontology as the map an agent navigates to retrieve and correlate structured + unstructured data in one language, with the model kept out of the truth path* — is domain-agnostic; this file is how the **OpenIM investment model** instantiates it. This is one instantiation of a general pattern (the deterministic-spine discipline, the property-graph projection family, the Agent Contract interlock, and further unification phases) maintained separately. Below: the OpenIM specifics.

## OpenIM as the map

The OpenIM model *is* the map an agent navigates over an investment estate. The entities are the nodes, the relationships are the edges, the service domains say who owns what, and the FIBO alignment gives the terms their meaning. Two corpora, one language:

- **Structured** — the OpenIM entities (Instrument, Fund, Holding, Legal Entity, Deal, Capital Call, Distribution…). The warehouse marts are projections of these, so the structured side already speaks the ontology; the served query-map maps question → entity → table.
- **Unstructured** — documents, as first-class nodes in the same graph, joined to the structured entities by typed edges.

### The nodes

The 86 entities (38 core + 48 specialisation). Three metadata entities are the joins between the two corpora and are load-bearing for agent navigation:

- **E-15 Document Metadata** — the document node, linkable to the deal / fund / company it concerns (its 6-way `subject_id`). The structured→unstructured edge: resolve an entity, follow its `has-document` edges, fetch the files.
- **E-22 Metric Definition** — the governed statement of how a number is defined (the semantic layer; the model selects a metric by name, the definition computes). One metric, one definition.
- **E-23 Extraction Record** — the provenance of a figure parsed from a document, so a number read from a PDF traces to the parse and the source document.

### The edges (today implicit; made explicit by the plan)

The entity-to-entity relationships are today **implicit** — in FK-style fields (`issuer_entity_id → E-01`, `fund_id`), in prose, and in the ownership map. Making them an explicit, typed **relation vocabulary** (`model/relations.md` — direction, source/target type, cardinality, kind, inverse) is the highest-value step: it turns the entity model from a data dictionary into a navigable graph. Crucially the vocabulary includes the **structured↔unstructured boundary edges** — E-15's `HAS_SUBJECT` (document → its subject entity, 6-way) and E-23's document/figure edges — so a query correlates *structured entity ↔ its documents ↔ the figures extracted from them* in the one map.

### The two projections (of the one OpenIM ontology)

- **Served query-map (structured)** — a generalisation of the agentINVEST operational query guide: which entities/marts answer which questions, the join paths, entity-resolution conventions, worked patterns; grounds NL→structured-query with E-22 metric definitions; served whole by the brain, model out of the truth path.
- **Typed graph (unstructured + structural)** — the entities and documents as a typed property graph the agent traverses with navigation verbs (`get_neighbours`, `expand`, `follow_edge`, `get_graph_description`), executed deterministically. Vector recall widens; the typed graph connects.

## How it is built

The autobuild plan `docs/plans/2026-07-18-domain-relation-ontology/` builds this increment: the declared relation vocabulary (`model/relations.md`) projected into the full property-graph family (**OWL, TPG/ISO-GQL, SQL/PGQ, LPG/openCypher, node/edge CSV** — one vocabulary, every serialisation), with the self-referential and polymorphic FKs made parseable, and the **structured↔unstructured correlation** (E-15 Document node + `HAS_SUBJECT`/extraction edges) as a first-class, tested outcome. OpenIM is schema-first, so the native form is a Typed Property Graph.

## Concrete increments (OpenIM)

1. **Make the domain edge set explicit** — the declared typed relation vocabulary over the 86 entities. Executed by the autobuild plan above (projected to the whole graph family; the structured↔unstructured bridge first-class).
2. **Generalise the served query-map** — lift the agentINVEST operational query guide into the model-level map pattern any deployment registers against its conformed layer.
3. **Navigation verbs + `get_graph_description`** — the typed tool surface an agent uses to read and traverse the graph, deterministically.
4. **A rollup layer for global questions** — precomputed summaries over the type hierarchy ("exposure across the whole book" without a full scan).
5. **Temporal validity on `supersedes` / `contradicts` edges** — validity windows so an agent reasons over current state while history stays queryable.

Next phases (unify the OpenIM domain ontology with the wider knowledge-graph ontology; generalise the whole practice into a domain-agnostic ontology factory) are tracked separately as future work.

## Measurable success criteria (OpenIM)

- An agent answers a **multi-entity / look-through** question by traversing the typed graph, where a vector-only baseline fails.
- An agent answers a **structured** question by selecting a governed metric or a map-grounded query, figure computed by the store, honest no-data decline otherwise.
- An agent resolves a **document** by navigating from an entity to its linked files via a precomputed edge (E-15) — no cross-reference at query time.
- The domain edge set is **declared and typed**, not implicit — the graph is navigable without reading prose.

## References

- `docs/plans/2026-07-18-domain-relation-ontology/` — the autobuild plan that builds increment 1.
- `model/ownership-map.md` (the SSOT+pointer+validator house pattern), `model/fibo-alignment.md`, `model/entities/core/E-15`, `E-22`, `E-23`, `tools/exports/` (the emitters).
- The Agent Contract is the governed envelope this map is navigated under.
