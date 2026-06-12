/**
 * The VERIFIER — recompute the audit hash chain and DETECT tampering (OIM-151 part 4).
 *
 * Reads a JSON-L export (one `ChainEntry` per line) + optionally its manifest, recomputes the chain
 * from each line's `record` using the SAME fold the chainer used (`recomputeChain`, one hash SSOT),
 * and detects every in-place tamper class:
 *
 *   - MODIFIED FIELD — an edit to any field of any record changes its canonicalJSON → the recomputed
 *     `chainHash` no longer matches the stored `chainHash`. Detected at that seq.
 *   - INSERTED LINE — an extra record splices the chain: from the insertion point on, the stored
 *     `prevHash`/`chainHash` no longer match the recompute. Detected at the inserted seq (the seq
 *     numbering itself also breaks contiguity, caught first).
 *   - DELETED LINE — a removed record: the remaining entries' stored hashes no longer chain; the seq
 *     numbering is non-contiguous (a gap). Detected at the gap.
 *   - REORDERED PAIR — two records swapped: their canonicalJSON feeds the fold in the wrong order →
 *     the recomputed hashes diverge from the stored ones at the first swapped position.
 *   - BROKEN LINK — an entry whose stored `prevHash` ≠ the prior entry's stored `chainHash` (the
 *     link was edited directly). Detected by the explicit link check.
 *   - FORGED / MISMATCHED TIP — the manifest's `chainTip` ≠ the recomputed final `chainHash`, or the
 *     final stored `chainHash` ≠ the recompute. Detected by the tip check.
 *
 * MASK-IMMUNE EXIT. The CLI derives its exit code from the verification RESULT (`ok` → 0; tampered →
 * 1) — it never hard-codes success. The verifier returns the first-broken `seq` + a human `reason`.
 *
 * REVERT-SENSITIVE. The recompute is the FULL fold over canonicalJSON; the checks compare stored vs
 * recomputed at EVERY entry, plus the explicit prevHash-link and tip checks. Loosening any of them
 * (e.g. skipping the per-entry chainHash compare, or trusting the stored hash) makes a tamper test go
 * GREEN that should be RED — the tests pin that.
 *
 * THREAT-MODEL HONESTY (v0.1). The verifier catches an EDIT to a stored record (a tamper that does
 * NOT re-run the whole chain). A holder of the file who RE-CHAINS a forged record set from the public
 * genesis seed produces a SELF-CONSISTENT chain that verifies green — the chain is tamper-EVIDENCE
 * for in-place edits, NOT forgery-prevention. Preventing a re-chained forgery (and deletion) is the
 * S3 object-lock immutability of v0.2 (an external append-only store). The verifier reports this
 * boundary in its `--help`; it does not claim to detect a fully re-chained forgery.
 */
import { readFile } from 'node:fs/promises';
import { recomputeChain, type ChainEntry } from './hash-chain.js';
import type { ExportManifest } from './jsonl-export.js';

/**
 * The no-manifest warning text — the honest v0.1 limit. Without a manifest the TIP-ANCHOR check
 * cannot run, so a record APPENDED or TRUNCATED at the END of the chain (the chain still
 * self-recomputes) is undetectable. In-chain tampers (a modified/inserted/deleted/reordered record,
 * a broken link) are STILL verified — the manifest only adds the tip anchor. Exported so the CLI and
 * the tests reference the SAME string (one SSOT) and the warn is revert-sensitive.
 */
export const NO_MANIFEST_WARNING =
  'no manifest supplied — the tip-anchor check is skipped; a tip-append or tip-truncation cannot be ' +
  'detected (in-chain tampers are still verified).';

/** The verification verdict. `ok` true iff a clean chain; otherwise `firstBrokenSeq` + `reason`. */
export interface VerificationResult {
  ok: boolean;
  /** The number of entries read. */
  entryCount: number;
  /** The first seq at which tampering was detected (null on a clean chain). */
  firstBrokenSeq: number | null;
  /** The tamper class detected (null on a clean chain). */
  tamperClass:
    | 'modified-field'
    | 'inserted-or-deleted-line'
    | 'reordered'
    | 'broken-link'
    | 'forged-tip'
    | 'malformed-line'
    | 'non-contiguous-seq'
    | null;
  /** A human reason naming what broke + where (null on a clean chain). */
  reason: string | null;
  /** The recomputed chain tip (the SHA-256 fold of the records as read). */
  recomputedTip: string | null;
  /** The manifest's claimed tip, when a manifest was supplied (null otherwise). */
  manifestTip: string | null;
  /**
   * Whether a manifest (the tip anchor) was supplied. False means the tip-anchor check did NOT run —
   * a tip-append/truncation is undetectable (see `warnings`).
   */
  manifestPresent: boolean;
  /**
   * Non-fatal advisories that do NOT flip `ok` but mean the result is NOT a fully-clean pass. The
   * standing one is the no-manifest warning (`NO_MANIFEST_WARNING`): an intact in-chain still reads
   * `ok:true`, but the tip-anchor class went unchecked.
   */
  warnings: string[];
}

/** A line failed to parse as a chain entry. */
function malformed(
  seq: number,
  detail: string,
  entryCount: number,
  manifestPresent: boolean,
  warnings: string[],
): VerificationResult {
  return {
    ok: false,
    entryCount,
    firstBrokenSeq: seq,
    tamperClass: 'malformed-line',
    reason: `line ${seq}: not a well-formed chain entry — ${detail}`,
    recomputedTip: null,
    manifestTip: null,
    manifestPresent,
    warnings,
  };
}

/** Structural read of one parsed JSON-L line as a chain entry; null if it is not the right shape. */
function asChainEntry(v: unknown): ChainEntry | null {
  if (typeof v !== 'object' || v === null) return null;
  const o = v as Record<string, unknown>;
  if (typeof o.seq !== 'number') return null;
  if (typeof o.prevHash !== 'string') return null;
  if (typeof o.chainHash !== 'string') return null;
  if (!('record' in o)) return null;
  return { seq: o.seq, record: o.record, prevHash: o.prevHash, chainHash: o.chainHash };
}

/**
 * Verify a chain given the parsed JSON-L entries (in file order) + an optional manifest. Pure logic
 * (no I/O) so it is fully unit-testable; `verifyExportFile` wraps it with the file read.
 */
export function verifyChain(
  rawEntries: readonly unknown[],
  manifest?: ExportManifest | null,
): VerificationResult {
  const entryCount = rawEntries.length;
  const manifestTip = manifest?.chainTip ?? null;
  // The tip anchor only exists when a manifest is supplied. Without it, the tip-anchor check below
  // cannot run, so a tip-append/truncation is undetectable — warn honestly (does NOT flip `ok`).
  const manifestPresent = manifest != null;
  const warnings: string[] = manifestPresent ? [] : [NO_MANIFEST_WARNING];

  // Parse + structural-shape each line.
  const entries: ChainEntry[] = [];
  for (let i = 0; i < rawEntries.length; i++) {
    const entry = asChainEntry(rawEntries[i]);
    if (!entry)
      return malformed(i, 'missing seq/prevHash/chainHash/record', entryCount, manifestPresent, warnings);
    entries.push(entry);
  }

  // (a) SEQ CONTIGUITY — the seqs must be 0,1,2,… in file order. A gap (deleted line) or a dup
  // (inserted/duplicated) is caught here as the cheapest unambiguous signal.
  for (let i = 0; i < entries.length; i++) {
    if (entries[i].seq !== i) {
      return {
        ok: false,
        entryCount,
        firstBrokenSeq: i,
        tamperClass: 'non-contiguous-seq',
        reason:
          `line ${i}: seq is ${entries[i].seq}, expected ${i} — the sequence is non-contiguous ` +
          `(a line was inserted, deleted, or reordered).`,
        recomputedTip: null,
        manifestTip,
        manifestPresent,
        warnings,
      };
    }
  }

  // (b) RECOMPUTE the chain from the records (the full fold over canonicalJSON) and compare the
  // recomputed prevHash + chainHash against the STORED values at every entry. This is the core
  // tamper detector: a modified field, a reordered pair, or an inserted/deleted record all change
  // the recomputed hashes and diverge from what was stored.
  const recomputed = recomputeChain(entries.map((e) => e.record));
  for (let i = 0; i < entries.length; i++) {
    const stored = entries[i];
    const re = recomputed[i];

    // BROKEN LINK — the stored prevHash must equal the PRIOR stored chainHash (genesis for seq 0).
    // A direct edit to a prevHash field is caught here even if the recompute were (wrongly) trusting
    // it — an independent, explicit link check (defence in depth).
    const expectedPrev = i === 0 ? recomputed[0].prevHash : entries[i - 1].chainHash;
    if (stored.prevHash !== expectedPrev) {
      return {
        ok: false,
        entryCount,
        firstBrokenSeq: i,
        tamperClass: 'broken-link',
        reason:
          `seq ${i}: stored prevHash ${short(stored.prevHash)} != the prior entry's chainHash ` +
          `${short(expectedPrev)} — the chain link is broken (a prevHash was edited, or a line ` +
          `inserted/deleted/reordered).`,
        recomputedTip: null,
        manifestTip,
        manifestPresent,
        warnings,
      };
    }

    // MODIFIED FIELD / REORDERED / SPLICE — the recomputed chainHash (over the record's canonical
    // JSON, folded from the verified prevHash) must equal the stored chainHash. Any record edit, or
    // any order change, diverges here.
    if (re.chainHash !== stored.chainHash) {
      return {
        ok: false,
        entryCount,
        firstBrokenSeq: i,
        // A prevHash that matched the link check but a chainHash that doesn't recompute means the
        // RECORD (or its order) was tampered — classify as modified/reordered.
        tamperClass: re.prevHash !== stored.prevHash ? 'reordered' : 'modified-field',
        reason:
          `seq ${i}: recomputed chainHash ${short(re.chainHash)} != stored chainHash ` +
          `${short(stored.chainHash)} — the record was modified (a field edited), reordered, or ` +
          `a line inserted/deleted upstream. The recompute over the record's canonical JSON no ` +
          `longer matches the stored hash.`,
        recomputedTip: null,
        manifestTip,
        manifestPresent,
        warnings,
      };
    }
  }

  // (c) TIP — the recomputed final chainHash is the chain tip. A FORGED manifest tip (a tip claim
  // that disagrees with the records) is caught here even when every line self-recomputes.
  const recomputedTip = recomputed.length === 0 ? genesisOf(manifest) : recomputed[recomputed.length - 1].chainHash;
  if (manifestTip !== null && manifestTip !== recomputedTip) {
    return {
      ok: false,
      entryCount,
      firstBrokenSeq: recomputed.length === 0 ? 0 : recomputed.length - 1,
      tamperClass: 'forged-tip',
      reason:
        `the manifest's chainTip ${short(manifestTip)} != the recomputed chain tip ` +
        `${short(recomputedTip)} — the manifest claims a tip the records do not produce (a forged ` +
        `or stale tip).`,
      recomputedTip,
      manifestTip,
      manifestPresent,
      warnings,
    };
  }

  return {
    ok: true,
    entryCount,
    firstBrokenSeq: null,
    tamperClass: null,
    reason: null,
    recomputedTip,
    manifestTip,
    manifestPresent,
    warnings,
  };
}

/** The genesis seed for an empty chain (from the manifest if present, else the chain's constant). */
function genesisOf(manifest?: ExportManifest | null): string {
  return manifest?.genesisSeed ?? 'agentinvest-audit-journal/v0.1/genesis';
}

/** Short-hash for human messages (first 12 hex chars; full strings pass through unchanged). */
function short(h: string): string {
  return /^[0-9a-f]{64}$/i.test(h) ? `${h.slice(0, 12)}…` : h;
}

/** Parse JSON-L text into an array of parsed values (blank lines skipped). Throws on a bad line. */
export function parseJsonl(text: string): { values: unknown[]; badLine: number | null } {
  const lines = text.split('\n');
  const values: unknown[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim().length === 0) continue;
    try {
      values.push(JSON.parse(line));
    } catch {
      return { values, badLine: values.length };
    }
  }
  return { values, badLine: null };
}

/**
 * Verify an export FILE: read the JSON-L, optionally read the manifest sidecar, and verify the chain.
 * The file-I/O wrapper around the pure `verifyChain`.
 *
 * @param dataPath     the JSON-L data file.
 * @param manifestPath the manifest sidecar (optional — when present, the tip is cross-checked).
 */
export async function verifyExportFile(
  dataPath: string,
  manifestPath?: string | null,
): Promise<VerificationResult> {
  const text = await readFile(dataPath, 'utf8');
  const { values, badLine } = parseJsonl(text);

  // Read the manifest sidecar FIRST so the malformed-data result also carries an accurate
  // manifestPresent + the no-manifest warning (a missing/unreadable manifest is not itself a tamper).
  let manifest: ExportManifest | null = null;
  if (manifestPath) {
    try {
      manifest = JSON.parse(await readFile(manifestPath, 'utf8')) as ExportManifest;
    } catch {
      manifest = null; // a missing/unreadable manifest is not itself a tamper — verify the data alone
    }
  }
  const manifestPresent = manifest != null;
  const warnings = manifestPresent ? [] : [NO_MANIFEST_WARNING];

  if (badLine !== null) {
    return malformed(badLine, 'invalid JSON on the line', values.length, manifestPresent, warnings);
  }

  return verifyChain(values, manifest);
}
