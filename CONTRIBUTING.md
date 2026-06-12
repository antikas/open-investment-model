# Contributing to OpenIM

Thank you for considering a contribution. OpenIM is a reference model — its value is precision, non-overlap and honest grounding, so the contribution process is built around those qualities rather than volume.

## Before you start

Open an issue first. A model change discussed before it is drafted saves both sides time: the boundary questions (does this capability already have a home? which entity owns this data?) are cheaper to settle in an issue than in review comments on a finished PR.

## The three kinds of model change

### 1. A Service Domain change

Adding, splitting, merging or re-scoping a unit of business capability. A proposal must carry:

- **Definition** — what the capability is, in plain language, and the business outcome it owns.
- **Boundary** — what it explicitly does *not* cover, and which existing Service Domains border it. Non-overlap with the existing 171 is the hardest test and the most valuable part of the proposal.
- **Owned entities** — which data entities (if any) this capability owns, and how that squares with the [ownership map](model/ownership-map.md).
- **Applicability** — public markets, private markets, or both; and which institution archetypes (asset manager, pension fund, sovereign investor, insurer, wealth manager, hedge fund) exercise it.
- **Grounding** — the external sources that evidence the capability exists as a distinct discipline: regulatory frameworks, industry bodies (CFA, ILPA, AIMA, ISDA), academic or practitioner literature. "My firm does it this way" is a data point, not grounding.

### 2. An entity change

Adding or changing an entity in the canonical data model. A proposal must carry:

- **Definition** — what real-world thing the entity represents and why the firm must hold consistent, single-source data about it.
- **Attributes** — the attribute schema, with types and the identifier story (how instances are identified when no universal identifier exists).
- **Ownership** — the owning Service Domain, and which ownership pattern applies (single owner, key-partitioned, faceted or co-owned).
- **Relationships** — how it relates to existing entities; whether it belongs in the generalised core or a specialisation pack, and why.

### 3. A standards-alignment change

Corrections or extensions to the documented mappings against adjacent standards (FIBO, ISDA CDM, ILPA, GIPS, ISO 20022). These need citations to the specific published artefact (the FIBO ontology module, the CDM version, the template revision) — alignment claims are checkable claims.

## The quality bar

- Every PR must pass the validator: `python tools/openim-validate/validate.py` from the repo root. It checks counts, identifiers, links and section structure across the whole model.
- Definitions are measurable: a reader can decide whether a given activity falls inside or outside the capability.
- Reader-facing model files carry no process commentary — provenance and decision history live in the PR, not the artefact.

## Contributing to agentINVEST (the reference implementation)

Code contributions under `reference/` follow the existing structure: a pnpm workspace (TypeScript orchestrator, Python tools, dbt data layer). Match the patterns in place, keep the deterministic spine intact (the LLM never computes a figure of record), and include tests alongside behaviour changes. See [reference/README.md](reference/README.md) for the build and run story.

## Process

1. Open an issue describing the change and its grounding.
2. Fork, branch, make the change, run the validator.
3. Open a PR referencing the issue. The maintainer reviews against the criteria above — see [GOVERNANCE.md](GOVERNANCE.md) for how decisions are made.

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
