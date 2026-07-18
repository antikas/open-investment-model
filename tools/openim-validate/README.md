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

Beyond the core set, the validator also reconciles prose counts and per-row tables against the model, enforces the entity-ownership contract declared in `model/ownership-map.md` (owner-side, producer-side, and consumer-side partition declarations), verifies that prose references name each Service Domain by its canonical H1, checks FIBO-curie resolvability (below), and — when a rendered diagram site exists under `dist/` — confirms full page and drill-down coverage.

## FIBO-curie resolvability

Every `fibo-*:Class` / `cmns-*:Class` curie asserted anywhere under `model/` must resolve against **`fibo_curie_reference.json`** (alongside the script) — the verified list of ontology-prefix → class-name pairs. A curie not in the list is a HARD defect, and so is a missing reference file (the gate cannot be silently disabled). This closes the fabricated-FIBO-citation class: a plausible-but-invented class name under a real FIBO prefix now fails CI instead of relying on a reviewer to catch it.

The validator never touches the network — it checks against the reference list only, staying deterministic and offline-runnable. Verification against the live ontology happens once, at reference-maintenance time.

**Maintaining the reference.** To cite a new FIBO or Commons class in `model/`:

1. Resolve it against the live published ontology first — fetch the module RDF from the [`edmcouncil/fibo`](https://github.com/edmcouncil/fibo) master branch (or [OMG Commons](https://www.omg.org/spec/Commons/) for `cmns-*`) and confirm the `owl:Class` declaration exists. The browsable spec is at [spec.edmcouncil.org/fibo](https://spec.edmcouncil.org/fibo/).
2. Add the class name under its prefix in `fibo_curie_reference.json` (add the prefix block — namespace and module path — if the prefix is new).
3. Re-run the validator.

Never add a class that has not been resolved against the live source: the file asserts *verification*, not intention. Prefix-only module mentions (e.g. `` `fibo-ind-ir-ir` `` with no `:Class`) and deliberately non-specific forms (e.g. `fibo-cae-...:CorporateAction`) assert a module or concept area, not a resolvable class curie, and are not checked.

## Distribution awareness

The private working tree carries a build trail (the `docs/` directory — decision records, backlog, build records — plus `CLAUDE.md`) that public distributions of the model do not ship. When `docs/` is absent, the checks that read those files (V7 and the `CLAUDE.md` leg of V8 among them) are skipped with a single informational line; every model-level check still runs, and the validator exits `0` when they pass.

## Where it sits

Run it after any structural change to the model — ideally as a pre-commit hook. A clean run is the entry criterion for any deeper, judgement-grade review of the model.
