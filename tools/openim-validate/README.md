# openim-validate — structural-integrity validator

Deterministic, mechanical checks over the OpenIM model. No judgement — counts, identifiers, contiguity, link resolution, section presence, cross-file count agreement. It is the gate any judgement-grade review runs behind: there is no point reviewing a model with a dead link or a count that does not add up.

Mechanical checks belong in a script, not an agent — fast, exact, free, re-runnable on every commit. An LLM is never asked to count files.

## Run

```
python tools/openim-validate/validate.py
```

Exit `0` if clean, `1` if any **DEFECT** is found. **WARNING**s are surfaced but do not fail the run.

## What it checks

The mechanically-checkable subset of the model's quality criteria. The core checks:

| ID | Check |
|---|---|
| V1 | Every `BD-NN-*` directory has a `README.md`. |
| V2 | Service Domain files are named `SD-NN.M-slug.md` and numbered **contiguously** `1..M` within each Business Domain. |
| V3 | Every SD file's H1 title matches its identifier and carries an `**Applies:**` tag. |
| V4 | Every SD file has the required sections — Purpose, Service Operations, Entities, Standards (Inputs/outputs and Open extensions are warned, not failed). |
| V5 | `INDEX.md`'s summary line and per-Business-Domain table agree with the actual directory and file counts. |
| V6 | Every internal link in `INDEX.md` resolves; every SD file is linked from `INDEX.md`. |
| V7 | ADR files are uniquely numbered; a gap in the sequence is warned (OpenIM has one known intentional gap — no ADR-0003). |
| V8 | `README.md` and `model/README.md` (plus `CLAUDE.md`, where present) agree with the model on the Business-Domain and Service-Domain counts. |

Beyond the core set, the validator also reconciles prose counts and per-row tables against the model, enforces the entity-ownership contract declared in `model/ownership-map.md` (owner-side, producer-side, and consumer-side partition declarations), verifies that prose references name each Service Domain by its canonical H1, and — when a rendered diagram site exists under `dist/` — confirms full page and drill-down coverage.

## Distribution awareness

The private working tree carries a build trail (the `docs/` directory — decision records, backlog, build records — plus `CLAUDE.md`) that public distributions of the model do not ship. When `docs/` is absent, the checks that read those files (V7 and the `CLAUDE.md` leg of V8 among them) are skipped with a single informational line; every model-level check still runs, and the validator exits `0` when they pass.

## Where it sits

Run it after any structural change to the model — ideally as a pre-commit hook. A clean run is the entry criterion for any deeper, judgement-grade review of the model.
