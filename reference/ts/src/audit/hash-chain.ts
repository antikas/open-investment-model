/**
 * The SHA-256 audit hash chain — the tamper-EVIDENCE heart of the audit-journal export (OIM-151).
 *
 * Given an ORDERED list of audit records, this produces a hash chain: each record becomes an entry
 * carrying its sequence number, the record, the PRIOR entry's hash, and this entry's hash, where
 *
 *     chainHash(i) = SHA-256( prevHash(i) || canonicalJSON(record(i)) )
 *
 * and `prevHash(0)` is a FIXED, DOCUMENTED genesis seed. The chain is a Merkle-style fold: the
 * final entry's `chainHash` (the chain TIP) is a digest of the WHOLE sequence in order, so ANY
 * change to ANY record — or to the order, or an insertion/deletion — changes the tip and every
 * downstream hash. The verifier (`verifier.ts`) recomputes this fold and detects the divergence.
 *
 * WHY canonical JSON. The hash must be a function of each record's VALUE, reproducibly. Plain
 * `JSON.stringify` is insertion-order-dependent, so the chain hashes over `canonicalJSON` (stable
 * sorted key order, compact) — see `canonical-json.ts`. Two runs over the same records produce the
 * SAME chain; the tip is stable. This is the reproducibility property the audit gate proves.
 *
 * PURE + DETERMINISTIC + NO I/O. `chainRecords` and `recomputeChain` are pure functions of their
 * input (the only external call is `node:crypto`'s SHA-256, itself deterministic). No clock, no
 * file, no network — fully unit-testable, and safe to call from anywhere (a CLI, a Restate handler).
 *
 * HONEST BOUNDARY (v0.1 — tamper-EVIDENCE, NOT tamper-PREVENTION). This chain makes tampering
 * DETECTABLE after the fact: an in-place edit to an exported record (without re-running the whole
 * chain) breaks the recompute, and the verifier names the first broken sequence. It does NOT make
 * the export IMMUTABLE: a holder of the JSON-L file can DELETE it, or RE-CHAIN a forged record set
 * from genesis to produce a self-consistent forgery (the genesis seed is public, the algorithm is
 * public). Preventing that is the S3 OBJECT-LOCK write-once-immutability of v0.2 (an external,
 * append-only, deletion-resistant store) — DEFERRED here. v0.1's threat model: it catches an EDIT
 * to a stored record; it does not stop a file holder re-chaining a forgery or deleting the file.
 * State that plainly; do not imply immutability.
 */
import { createHash } from 'node:crypto';
import { canonicalJSON } from './canonical-json.js';

/**
 * The FIXED, DOCUMENTED genesis seed — `prevHash` for the first entry (seq 0). A constant string
 * (not a hash of anything) so the chain is reproducible from the records alone. Domain-tagged +
 * versioned so a v0.2 chain (a different construction) is never confused with a v0.1 chain. This is
 * PUBLIC — the chain is tamper-EVIDENCE, not a secret-keyed MAC; its security property is "an
 * in-place edit is detectable", not "only a key-holder can forge" (that is the object-lock layer).
 */
export const GENESIS_SEED = 'agentinvest-audit-journal/v0.1/genesis';

/** One entry of the hash chain — what each exported JSON-L line carries. */
export interface ChainEntry<R = unknown> {
  /** The entry's sequence number — 0-based, contiguous, in chain order. */
  seq: number;
  /** The audit record this entry chains over (hashed via its canonical JSON). */
  record: R;
  /** The PRIOR entry's `chainHash` (the genesis seed for seq 0) — the link to the previous entry. */
  prevHash: string;
  /** SHA-256(prevHash || canonicalJSON(record)) — this entry's hash; the next entry's `prevHash`. */
  chainHash: string;
}

/**
 * Compute one entry's `chainHash`: SHA-256 of `prevHash` concatenated with the record's canonical
 * JSON. The `||` in the spec is byte concatenation; the canonical JSON is deterministic, so the
 * digest is a reproducible function of (prevHash, record value). Exported so the verifier recomputes
 * with the EXACT same function the chainer used (one SSOT for the hash, no drift).
 */
export function computeChainHash(prevHash: string, record: unknown): string {
  const h = createHash('sha256');
  h.update(prevHash, 'utf8');
  h.update(canonicalJSON(record), 'utf8');
  return h.digest('hex');
}

/**
 * Chain an ordered list of audit records into hash-linked entries (the EXPORT direction).
 *
 * Each record becomes a `ChainEntry` with its seq, the record, the prior hash, and the computed
 * chainHash. The records are taken IN THE GIVEN ORDER — the caller is responsible for a deterministic
 * order (the gather sorts by a stable key) so the chain is reproducible. Pure + deterministic.
 *
 * @param records the audit records, already in deterministic chain order.
 * @returns the hash-chained entries (empty in → empty out).
 */
export function chainRecords<R>(records: readonly R[]): ChainEntry<R>[] {
  const entries: ChainEntry<R>[] = [];
  let prevHash = GENESIS_SEED;
  for (let seq = 0; seq < records.length; seq++) {
    const record = records[seq];
    const chainHash = computeChainHash(prevHash, record);
    entries.push({ seq, record, prevHash, chainHash });
    prevHash = chainHash;
  }
  return entries;
}

/**
 * Recompute the chain hashes for a list of records (the VERIFY direction — the same fold as
 * `chainRecords`, but the caller compares the result against the entries read from a file). Returns
 * the recomputed `{ prevHash, chainHash }` per index, in order. The verifier uses this to compare
 * against the stored `prevHash`/`chainHash` and locate the first divergence.
 *
 * @param records the records read back from an export, in their file order.
 * @returns the recomputed link hashes, one per record, in order.
 */
export function recomputeChain(records: readonly unknown[]): { prevHash: string; chainHash: string }[] {
  const out: { prevHash: string; chainHash: string }[] = [];
  let prevHash = GENESIS_SEED;
  for (const record of records) {
    const chainHash = computeChainHash(prevHash, record);
    out.push({ prevHash, chainHash });
    prevHash = chainHash;
  }
  return out;
}

/** The chain TIP — the final entry's `chainHash` (the genesis seed for an empty chain). */
export function chainTip(entries: readonly ChainEntry[]): string {
  return entries.length === 0 ? GENESIS_SEED : entries[entries.length - 1].chainHash;
}
