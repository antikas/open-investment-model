# Entity resolution

Entity resolution is how agentINVEST decides, for an inbound record from one source, which entity in the master it refers to — an existing golden record, a genuinely new entity, or a case a human must adjudicate. It is the capability that turns a stream of records arriving under many names, from many systems, into a single trustworthy party master.

It is OpenIM's signature differentiator made runnable. The model layer names the three-tier resolution cascade in the Legal Entity master ([`E-01`](../../../model/entities/core/E-01-legal-entity.md) `## Resolution`); this is that cascade implemented, with a golden-record store, a steward review queue, and a labelled evaluation that holds the one guarantee that matters: zero mis-merges.

## The no-universal-identifier reality

Listed instruments and regulated firms largely carry standard identifiers — an ISIN, a CUSIP, an LEI. Private companies, private funds and the vehicles between them largely do not. There is no shared key you can join on. The same entity arrives from a custodian feed, an administrator statement and an internal onboarding capture under three different names, none of them canonical, and nothing in the records themselves tells you they are the same thing.

That is the reality the buy-side master-data layer is built for. OpenIM keys every master on an internal golden key precisely because external identifiers are unstable, incomplete in private markets and non-interoperable across vendors ([`E-14`](../../../model/entities/core/E-14-external-identifier.md)). Resolution is the process that earns that internal key: it takes the observable evidence on an inbound record — a name, maybe an identifier, a domicile, a parent hint — and decides, deterministically and explainably, which golden record it belongs to.

## The three-tier cascade

The cascade tries the strongest evidence first and falls through to the weaker tiers only when the strong evidence is absent. Every decision is explainable: it carries the tier that fired and the signal that matched.

### Tier 1 — exact external-identifier match

If the inbound record carries an external identifier — an LEI, a registry number, a private CUSIP — and that identifier exactly matches a master's LEI or one of its External Identifier records ([`E-14`](../../../model/entities/core/E-14-external-identifier.md)), the record resolves to that master with high confidence. This is the easy case, and for regulated counterparties, issuers and managers it resolves the large majority of records. An inbound identifier that matches no master is treated as net-new: its identifier is authoritative and unmatched, so it cannot be silently name-matched to a different master.

### Tier 2 — alias and deterministic name normalisation

When there is no usable identifier — the no-universal-identifier case — the cascade falls to a name match. It does not fuzzy-match. It runs the inbound name through a deterministic normaliser and matches the result, exactly, against the normalised canonical name and the normalised aliases of every master.

The normaliser is rule-based and total: case-folding, whitespace collapse, diacritic stripping, punctuation collapse, and cross-jurisdiction legal-suffix stripping. The suffix list spans the common Anglo forms (Ltd, Inc, Corporation, LLC, LLP, PLC) and a set of international private-company forms — Estonian OÜ, Finnish Oy, Norwegian/Danish AS, French SARL, Italian/Spanish S.r.l. — so that the legal wrapper a name happens to arrive in does not defeat the match. The result is an exact, reproducible key: two names match at this tier if and only if their normalised forms are byte-equal.

The aliases the normaliser matches against are the accumulated institutional knowledge of the firm. Every alias is a name the platform has previously learned maps to a golden key ([`E-13`](../../../model/entities/core/E-13-entity-alias.md)). A private company with no identifier accumulates many aliases over time; a steward confirming an unresolved record under a new name writes that name back as an alias, and the next resolution run matches it automatically. This is the tier that resolves the no-universal-identifier reality — not by guessing, but by remembering.

Name agreement is necessary but not sufficient. Metadata is a corroboration gate, not a fuzzy score. A name-key match whose declared domicile conflicts with the master's does not auto-merge — it falls through to Tier 3. The same name under a different jurisdiction may be a different entity, and resolving it on name alone would be the one error that must never happen. A null on either side is not a conflict — absence of evidence is not evidence of difference.

### Tier 3 — the steward review queue

Everything the deterministic tiers cannot resolve to exactly one master lands in a steward review queue: a name that matches no master (net-new), or a name-key that collides across two masters, or a name match under a conflicting domicile. These records are never auto-merged. They are quarantined as immutable `in_review` events for a human to adjudicate.

A quarantine is a correct outcome, not a failure. Forcing a merge on insufficient evidence is the single error that silently corrupts the master — two distinct entities collapsed under one golden key, with no signal that anything is wrong. The review queue is where that pressure is released honestly: the cascade declines to decide rather than decide wrongly.

## The deterministic spine

The resolve-of-record decision contains no model. Normalisation and matching are pure functions of the inbound record and the standing reference data — no LLM, no learned scorer, no fuzzy edit-distance threshold. The match bar is exactness after a declared, auditable normalisation, never a similarity score that could merge two genuinely distinct entities.

This is the deterministic spine applied to identity: the model is kept out of the truth path. A model may, in a later extension, propose a candidate match for a steward to review — but it never makes the of-record decision. The resolve path's transitive import closure is asserted to contain no model, proposer or LLM module, statically and through dynamic-import call sites, so a future change that wires a model into the of-record path fails loudly rather than quietly.

## The golden key by survivorship

For every cluster the cascade resolves, agentINVEST builds one canonical golden record. It is keyed by the internal `entity_id` — never by an external identifier. The LEI is a survived attribute, not the key ([`E-01`](../../../model/entities/core/E-01-legal-entity.md) `## The golden key`).

Each canonical field is decided by survivorship over a declared source-priority order, with the contributing source recorded per field as provenance. Where the cluster resolved to an existing master, the master's own values are the authoritative baseline and a source only fills a field the master leaves empty. The result is a single record per resolved entity that you can trace field by field back to the source that contributed it.

## The hard case, worked

Consider an inbound record reading **Bolt Technologies OÜ** — an Estonian-legal-form private company, no LEI, no internal key anywhere in the string. It resolves to the master `LE-0004`, and the way it gets there is the whole point of the capability:

1. The normaliser strips the `OÜ` legal suffix and the diacritic, producing the key `bolt technologies`.
2. The platform has previously learned the alias `Bolt Technologies` for that master, so the key matches.
3. The KY domicile and the parent hint corroborate the match rather than conflicting with it.

The answer — `LE-0004` — is nowhere in the inbound name. It is recoverable only from the learned alias plus the corroborating metadata, never from the name string itself. That is the no-universal-identifier reality, exercised honestly: the suffix strip is necessary (without it the key would not match), and the alias does real work (the firm had to have learned the name).

Now the mirror case. Two distinct private entities arrive under the name **Crestline Partners**, one declaring a KY domicile and one declaring SG, neither carrying an identifier. Both normalise to the same key. Neither matches an existing master, so on a naive net-new path they would be merged into one new golden key. The cascade refuses: it detects the within-batch name-key collision under conflicting jurisdictions and quarantines both records to the review queue. Where the evidence cannot distinguish two entities that may genuinely be different, the cascade declines to merge them. The same guard fires for the Meridian and Apex near-collisions in the evaluation set.

## Runnable and evaluated

The cascade, the golden-record survivorship, the append-only steward-review-queue and golden-record stores, and a labelled evaluation are implemented under [`reference/python`](../../python) — the `entity_resolution` package and its evaluation suite. The two stores are insert-only and immutable: a quarantine or a golden record, once written, is never mutated; a steward's later confirmation is a separate, human-gated step. The resolution run is exposed as a model-free `entityResolution` service so an agent reaches it the same way it reaches any other tool in the catalogue.

The evaluation scores the cascade against a labelled oracle that spans the four difficulty tiers — exact-identifier, alias, the no-universal-identifier name variant, and the genuinely-ambiguous. The labels are derived from the intent used to construct the feed, never read back from it, so the matcher cannot see the answer key. Over a 21-record inbound feed the run produces **14 resolved**, **1 net-new**, **6 quarantined to review**, and **8 distinct golden records** keyed by the internal `entity_id`.

The evaluation asserts the cardinal properties:

- **Zero mis-merges** — no record is resolved to an entity other than its true one. A mis-merge silently corrupts the golden master; this is the line that holds. Precision over the auto-resolved set is 1.0.
- **Zero missed-merges among the auto-resolved set** — every record the oracle marks resolvable is resolved to its true entity, including all seven no-universal-identifier private-company cases, each via the learned alias plus corroborating metadata rather than any embedded key. Recall over the resolvable set is 1.0.
- **Six honest quarantines** — every genuinely-ambiguous record (the Meridian, Apex and Crestline near-collisions) lands in the review queue, never force-merged.

## Honest boundary

The feed is synthetic and illustrative — richer than a clean seed, but not a benchmarked real-world entity distribution. The deterministic cascade is the floor the model's design names, and it is what is built and asserted here; the probabilistic stage in which a model proposes a candidate match for a steward to review is deliberately deferred to a later extension, with the of-record path kept deterministic. The normaliser's suffix list and transliteration map are a documented, extensible rule set, not a tuned production configuration. What is load-bearing is the seam — a pure, auditable normalise-and-match function the cascade keys on, with everything subtler quarantined to a human rather than force-merged.
