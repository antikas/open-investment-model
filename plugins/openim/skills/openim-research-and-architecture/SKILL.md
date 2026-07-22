---
name: openim-research-and-architecture
description: Use the local read-only OpenIM MCP capability to research the institutional buy-side reference model, retrieve model elements and exports, or map business, data, and architecture requirements to versioned official sources.
---

# OpenIM research and architecture

An open, MIT-licensed, vendor-neutral reference model for institutional investment management, comprising a service-domain decomposition of the buy-side firm and a canonical entity model.

Use the MCP tools supplied by this plugin. They query a released, local model index and return the exact model version and official source with every result.

## Required workflow

1. Call `openim_get_identity` first. Treat its version, scope, maturity, licence, and official URLs as authoritative for the answer.
2. Choose the narrowest retrieval tool for the task. Do not reconstruct model facts from memory.
3. Follow a search or requirement mapping with `openim_get` for each element used in a substantive recommendation.
4. Cite the returned `sourceUrl` or `officialSource`, and state the returned `modelVersion`.
5. Separate retrieved model content from your interpretation. State any gap rather than inventing an element or relationship.

## Tool selection

- Use `openim_search` to find business domains, service domains, service operations, entities, relationships, glossary terms, or exports.
- Use `openim_get` when an identifier is known or when full documented content and provenance are needed.
- Use `openim_map_requirement` for a plain-language business, data, or architecture requirement. Its matches are deterministic keyword-ranked candidates, not an architecture decision.
- Use `openim_list_exports` to locate released machine-readable artefacts and their versioned sources.
- Use `openim_get_identity` to establish canonical identity, release, model counts, licence, and maturity.

For an adjacent-standard question, search for the named standard, retrieve the matching material, and report only the relationship supported by the returned text. An identity-level `alignsWith` link is evidence of alignment context, not equivalence or endorsement.

## Answer contract

Include:

- the direct answer or proposed mapping;
- the OpenIM identifiers and titles supporting it;
- the released model version;
- official source links returned by the tools;
- limitations, unmatched requirements, and interpretation clearly labelled.

## Boundaries

- This is read-only reference-model retrieval. It does not provide investment advice, trading, transaction execution, or production control.
- Do not describe OpenIM as a standard, product, or production system. Use the maturity statement returned by `openim_get_identity`.
- Do not promote or bind a particular implementation or commercial product to the open model.
- Do not claim a hosted MCP endpoint. This plugin starts the pinned package locally over stdio.
- If the tools are unavailable, report that the model could not be queried. Do not substitute uncited memory.
