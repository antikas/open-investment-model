# Contributing to OpenIM

OpenIM accepts corrections, model changes and standards-alignment improvements. Contributions are reviewed for clear scope, evidence and consistency with the existing model.

## Start with an issue

Open an issue before drafting a substantial model change. Describe the problem, identify the current model location and include the evidence you expect the proposal to use.

Early discussion is especially useful when a capability may already have a home or an entity may already have an owner.

## Service Domain proposals

A Service Domain proposal adds, splits, merges or changes the scope of a business capability. Include:

- **Definition:** the capability in plain language and the business outcome it owns.
- **Boundary:** the activities in scope, the adjacent Service Domains and the relevant `Out of scope` statements.
- **Owned entities:** the entities the capability owns, with any required change to the [ownership map](model/ownership-map.md).
- **Applicability:** the markets and institution types that exercise the capability.
- **Grounding:** primary or authoritative sources showing that the capability exists as a distinct discipline.

A firm's local operating model is useful evidence. Broader grounding is required before that local pattern becomes part of a general reference model.

## Entity proposals

An entity proposal adds or changes a concept in the canonical entity model. Include:

- **Definition:** the real-world concept represented by the entity.
- **Reason for inclusion:** why the firm needs consistent identity and information for that concept.
- **Attributes:** the proposed schema and types.
- **Identity:** the internal key, aliases and external identifiers used to distinguish instances.
- **Ownership:** the owning Service Domain and the ownership pattern applied.
- **Relationships:** links to existing entities and the proposed core or specialisation-pack placement.

## Standards-alignment proposals

An alignment proposal corrects or extends a documented mapping to an external standard. Cite the exact published artefact, version and concept involved.

Examples include FIBO ontology terms, FINOS Common Domain Model concepts, ILPA templates, GIPS provisions and ISO 20022 messages.

## Quality requirements

- Definitions must let a reader decide whether an activity or concept falls within the stated boundary.
- Reader-facing model files contain the current definition. Decision history belongs in the issue, pull request and commit record.
- Links, identifiers, headings and required sections must remain structurally valid.
- A model change includes any necessary updates to indexes, ownership mappings and generated outputs.

Run the validator from the repository root:

```sh
python tools/openim-validate/validate.py
```

See the [validator guide](tools/openim-validate/README.md) for the checks it performs.

## Contribution process

1. Open an issue with the proposed change and its grounding.
2. Fork the repository and create a focused branch.
3. Make the change and run the validator.
4. Open a pull request that links to the issue and explains the model impact.
5. Address review comments and keep the evidence in the pull-request record.

The maintainer reviews proposals under [GOVERNANCE.md](GOVERNANCE.md).

By contributing, you agree that your contribution is licensed under the [MIT licence](LICENSE).
