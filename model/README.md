# OpenIM model

This directory contains the two connected parts of the OpenIM reference model. One describes the firm's business capabilities. The other describes the information those capabilities use.

## Business capabilities

[`service-domains/`](service-domains/INDEX.md) maps **17 Business Domains and 171 Service Domains**.

A Business Domain groups a broad area of work. A Service Domain defines a more specific capability, its boundary and its Service Operations.

Start with the [Business Domain index](service-domains/INDEX.md) when you need to describe firm scope or locate a capability.

## Canonical entities

[`entities/`](entities/INDEX.md) defines **86 canonical entities**.

A canonical entity is a reference concept for information that a firm needs to identify consistently. The catalogue has a generalised core of 38 entities and five specialisation packs.

Start with the [entity index](entities/INDEX.md) when you need to compare data concepts or follow the information used by a capability.

## How the two parts connect

The [ownership map](ownership-map.md) identifies the Service Domain that acts as the authoritative source for each entity. It also records cases where ownership is partitioned, faceted or shared.

[`relations.md`](relations.md) defines the named relationships between entities. Together, ownership and relations connect the capability map to the information model.

## Supporting references

- The [glossary](glossary.md) defines domain terms used across the model.
- The [diagram index](diagrams/INDEX.md) provides visual views of the capability and entity structures.
- The [FIBO alignment](fibo-alignment.md) records entity-level mappings to FIBO concepts.
- [Related standards and models](../PRIOR-ART.md) explains how OpenIM relates to BIAN, FIBO, FINOS CDM and buy-side prior art.

## Using the model

OpenIM supplies common categories and definitions for local design. Firms select the relevant subset, add local detail and retain responsibility for implementation choices.

The Markdown files are the model source. Generated views and exports are derived from them for each release. The two BPMN files are hand-authored, non-normative illustrations and may lag the model.
