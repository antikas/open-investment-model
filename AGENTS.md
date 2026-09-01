# Open Investment Model - project context

## Context authority

This file owns runtime-neutral project context. Provider-specific files import it and contain mechanics only.

Start with `README.md`. Use `model/service-domains/INDEX.md`, `model/entities/INDEX.md`, and `metadata/openim.json` for canonical model identity and structure.

## Project boundary

OpenIM is a public, MIT-licensed reference model for institutional investment management. It connects business capabilities, service domains, operations, canonical entities, ownership, and machine-readable exports.

The model is vendor-neutral and does not prescribe a product, implementation, investment decision, or transaction.

## Model rules

- Edit canonical model source before changing a derived view or export.
- Keep identifiers, links, counts, and cross-model relationships structurally consistent.
- Treat generated exports as projections of model source.
- Treat the two BPMN files as hand-authored, non-normative illustrations.
- Record local extensions outside the canonical public model unless governance accepts them upstream.
- Use primary sources for prior-art corrections and cite them in the owning document.

## Public and consumer boundaries

Keep private implementations, organisation data, credentials, internal plans, and private operational state outside this repository.

`openinvestmentmodel.org` consumes a pinned public release for presentation. Fix model facts here and update consumers through an explicit version bump.

For model changes, run the structural validator documented in `README.md`. Instruction-only changes need import, project-scope, and public-safety checks.

## Publication relationship

The private `openim` repository is the complete source and release build home. This repository is its reviewed public projection.
