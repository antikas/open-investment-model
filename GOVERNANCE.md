# Governance

## Decision authority

OpenIM is maintainer led. [Georgios Antikatzidis](https://github.com/antikas) decides which model changes are accepted, how boundary disputes are resolved and when a release is prepared.

Contributions are reviewed for evidence, definition quality and consistency with the wider model. The [contribution guide](CONTRIBUTING.md) sets the information required for each proposal.

This structure gives the reference model one accountable editorial authority. A future change in stewardship would require an explicit update to this governance document.

## Decision record

Substantial proposals begin in a public issue. The linked pull request retains the evidence, review discussion and final model change. The commit history provides the permanent record of accepted changes.

The maintainer may close a proposal when it lacks grounding, duplicates an existing concept or creates an unresolved boundary conflict. The issue records the reason.

## Releases

A release is prepared when a coherent set of accepted changes warrants a new version. Releases follow the repository's documented release process and pass the structural validator.

Released source and generated exports identify the same model version. Consumers can pin that release or its commit when they need a stable reference.

## Scope of governance

This governance covers the OpenIM reference model, its machine-readable identity and its model-derived public exports.

Implementations remain under their owners' governance. Adoption is voluntary, and the MIT licence permits use of all or part of the model subject to its terms. OpenIM endorsement is granted only through an explicit project statement.
