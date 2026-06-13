/**
 * Unit proof of the VERIFIER — the tamper detector. The load-bearing audit-gate test.
 *
 * Pins: the verifier PASSES a clean chain, and DETECTS every tamper class — modified field, inserted
 * line, deleted line, reordered pair, broken link, forged tip — each naming the first-broken seq,
 * with `ok:false`. REVERT-SENSITIVE: these tests are written so that loosening the recompute (e.g.
 * trusting the stored chainHash instead of recomputing, or dropping the prevHash-link check, or
 * skipping the tip check) turns a RED tamper assertion GREEN — the suite catches the regression.
 */
import { describe, expect, it } from 'vitest';
import { chainRecords, computeChainHash, chainTip, type ChainEntry } from './hash-chain.js';
import { verifyChain, NO_MANIFEST_WARNING } from './verifier.js';
import type { ExportManifest } from './jsonl-export.js';

function records() {
  return [
    { operationId: 'op-1', recordType: 'operation-closed', nav: '100.00' },
    { operationId: 'op-2', recordType: 'nav-published', nav: '200.00' },
    { operationId: 'op-3', recordType: 'operation-closed', nav: '300.00' },
    { operationId: 'op-4', recordType: 'nav-published', nav: '400.00' },
  ];
}

/** A clean chain as the verifier sees it (the parsed JSON-L lines = ChainEntry objects). */
function cleanChain(): ChainEntry[] {
  return chainRecords(records());
}

function manifestFor(chain: ChainEntry[]): ExportManifest {
  return {
    auditKind: 'agentinvest-audit-export-manifest',
    version: 'v0.1',
    chainTip: chainTip(chain),
    genesisSeed: chain[0]?.prevHash ?? 'agentinvest-audit-journal/v0.1/genesis',
    recordCount: chain.length,
    exportedAt: '2026-06-03T00:00:00.000Z',
    dataFile: 'audit-journal.jsonl',
  };
}

describe('verifyChain — clean', () => {
  it('PASSES a clean chain (ok, no broken seq)', () => {
    const chain = cleanChain();
    const r = verifyChain(chain, manifestFor(chain));
    expect(r.ok).toBe(true);
    expect(r.firstBrokenSeq).toBeNull();
    expect(r.tamperClass).toBeNull();
    expect(r.recomputedTip).toBe(chainTip(chain));
    expect(r.manifestTip).toBe(chainTip(chain));
  });

  it('PASSES a clean empty chain', () => {
    const r = verifyChain([]);
    expect(r.ok).toBe(true);
  });
});

describe('verifyChain — tamper detection (each class, first-broken seq)', () => {
  it('detects a MODIFIED FIELD (edit a record in place; chainHash no longer recomputes)', () => {
    const chain = cleanChain();
    // Edit seq 2's record but LEAVE its stored chainHash unchanged (the naive in-place edit a
    // tamperer makes). A loosened verifier that trusted the stored chainHash would MISS this.
    (chain[2].record as Record<string, unknown>).nav = '999999.99';
    const r = verifyChain(chain, manifestFor(cleanChain()));
    expect(r.ok).toBe(false);
    expect(r.firstBrokenSeq).toBe(2);
    expect(r.tamperClass).toBe('modified-field');
  });

  it('detects a MODIFIED FIELD even when the tamperer ALSO updates that line\'s chainHash (the tip/link still break)', () => {
    const chain = cleanChain();
    const rec = chain[1].record as Record<string, unknown>;
    rec.nav = '777.77';
    // Recompute ONLY seq 1's chainHash from its (genuine) prevHash — a smarter tamperer. But the
    // downstream entries' prevHash no longer matches → broken link at seq 2.
    chain[1].chainHash = computeChainHash(chain[1].prevHash, chain[1].record);
    const r = verifyChain(chain, manifestFor(cleanChain()));
    expect(r.ok).toBe(false);
    // The break surfaces at seq 2 (its stored prevHash != the edited seq-1 chainHash).
    expect(r.firstBrokenSeq).toBe(2);
    expect(r.tamperClass).toBe('broken-link');
  });

  it('detects an INSERTED LINE (an extra record spliced into the chain)', () => {
    const chain = cleanChain();
    const injected: ChainEntry = {
      seq: 2,
      record: { operationId: 'op-FORGED', recordType: 'nav-published', nav: '0.01' },
      prevHash: chain[1].chainHash,
      chainHash: computeChainHash(chain[1].chainHash, {
        operationId: 'op-FORGED',
        recordType: 'nav-published',
        nav: '0.01',
      }),
    };
    // Splice it in at index 2 (seqs after it are now non-contiguous).
    chain.splice(2, 0, injected);
    const r = verifyChain(chain, manifestFor(cleanChain()));
    expect(r.ok).toBe(false);
    // The original entry now at index 3 carries seq 2 → non-contiguous at index 3.
    expect(r.firstBrokenSeq).toBe(3);
  });

  it('detects a DELETED LINE (a record removed; the seqs gap)', () => {
    const chain = cleanChain();
    chain.splice(2, 1); // remove seq 2; the entry now at index 2 carries seq 3.
    const r = verifyChain(chain, manifestFor(cleanChain()));
    expect(r.ok).toBe(false);
    expect(r.firstBrokenSeq).toBe(2);
    expect(r.tamperClass).toBe('non-contiguous-seq');
  });

  it('detects a REORDERED PAIR (two records swapped, seqs renumbered to look intact)', () => {
    const chain = cleanChain();
    // Swap the RECORDS of seq 1 and seq 2 but keep contiguous seq numbering + naive stored hashes —
    // the recompute over canonicalJSON in the swapped order diverges.
    const tmp = chain[1].record;
    chain[1].record = chain[2].record;
    chain[2].record = tmp;
    const r = verifyChain(chain, manifestFor(cleanChain()));
    expect(r.ok).toBe(false);
    expect(r.firstBrokenSeq).toBe(1);
    expect(['modified-field', 'reordered']).toContain(r.tamperClass);
  });

  it('detects a BROKEN LINK (a prevHash edited directly)', () => {
    const chain = cleanChain();
    chain[2].prevHash = 'deadbeef'.repeat(8); // 64 hex, but not the prior chainHash.
    const r = verifyChain(chain, manifestFor(cleanChain()));
    expect(r.ok).toBe(false);
    expect(r.firstBrokenSeq).toBe(2);
    expect(r.tamperClass).toBe('broken-link');
  });

  it('detects a FORGED / MISMATCHED TIP (manifest claims a tip the records do not produce)', () => {
    const chain = cleanChain(); // a fully self-consistent chain ...
    const forged = manifestFor(chain);
    forged.chainTip = 'f'.repeat(64); // ... but the manifest lies about the tip.
    const r = verifyChain(chain, forged);
    expect(r.ok).toBe(false);
    expect(r.tamperClass).toBe('forged-tip');
  });

  it('a malformed line is surfaced (not a silent pass)', () => {
    const chain: unknown[] = cleanChain();
    chain[1] = { seq: 1, prevHash: 'x' }; // missing chainHash + record.
    const r = verifyChain(chain);
    expect(r.ok).toBe(false);
    expect(r.tamperClass).toBe('malformed-line');
    expect(r.firstBrokenSeq).toBe(1);
  });
});

describe('verifyChain — revert-sensitivity anchors', () => {
  it('a clean chain with NO manifest still passes (tip check is skipped when no manifest)', () => {
    expect(verifyChain(cleanChain()).ok).toBe(true);
  });

  it('the per-entry recompute is what catches an edit — a stored chainHash alone is never trusted', () => {
    // This is the revert anchor for the core check: edit a record, leave stored hashes; a verifier
    // that returned ok by reading stored hashes would PASS — we require ok:false.
    const chain = cleanChain();
    (chain[0].record as Record<string, unknown>).nav = '0.00';
    expect(verifyChain(chain).ok).toBe(false);
  });
});

/**
 * The no-manifest warning — the honest v0.1 limit. Without a manifest the tip-anchor
 * check cannot run, so a tip-append/truncation (the chain still self-recomputes) is undetectable. The
 * manifest-less verify still passes for in-chain tampers, but it must WARN that the tip class went
 * unchecked. REVERT-SENSITIVE: remove the warning push and the manifest-less assertions go RED.
 */
describe('verifyChain — no-manifest tip-anchor warning', () => {
  it('a manifest-less verify of an intact chain is ok BUT carries the tip-anchor warning', () => {
    const r = verifyChain(cleanChain()); // no manifest
    expect(r.ok).toBe(true); // in-chain intact → still ok
    expect(r.manifestPresent).toBe(false);
    expect(r.warnings).toContain(NO_MANIFEST_WARNING);
    // The warning is not empty and names the undetectable class.
    expect(r.warnings.some((w) => /tip-anchor/.test(w))).toBe(true);
  });

  it('a manifest-less verify of a TIP-APPENDED chain still reads ok in-chain — the warning is why that is honest', () => {
    // Append a fresh, correctly-chained record at the END (a tip-append). The chain still
    // self-recomputes (each link is valid), so the in-chain checks pass. WITHOUT the manifest tip
    // anchor this append is undetectable — exactly the class the warning names.
    const chain = cleanChain();
    const last = chain[chain.length - 1];
    const appendedRecord = { operationId: 'op-5', recordType: 'nav-published', nav: '500.00' };
    chain.push({
      seq: chain.length,
      record: appendedRecord,
      prevHash: last.chainHash,
      chainHash: computeChainHash(last.chainHash, appendedRecord),
    });
    const r = verifyChain(chain); // no manifest → no tip anchor
    expect(r.ok).toBe(true); // the appended chain self-recomputes → in-chain ok
    expect(r.warnings).toContain(NO_MANIFEST_WARNING); // ... but the operator is WARNED it is unchecked
    // PROOF that the manifest WOULD have caught it: the original (pre-append) manifest tip anchors it.
    const originalManifest = manifestFor(cleanChain());
    const withManifest = verifyChain(chain, originalManifest);
    expect(withManifest.ok).toBe(false);
    expect(withManifest.tamperClass).toBe('forged-tip');
  });

  it('a MANIFEST-PRESENT verify is UNCHANGED — clean pass, NO spurious warning', () => {
    const chain = cleanChain();
    const r = verifyChain(chain, manifestFor(chain));
    expect(r.ok).toBe(true);
    expect(r.manifestPresent).toBe(true);
    expect(r.warnings).toEqual([]); // no spurious warning when a manifest IS supplied
    expect(r.manifestTip).toBe(chainTip(chain));
  });

  it('a MANIFEST-PRESENT forged-tip is STILL detected, with no no-manifest warning', () => {
    const chain = cleanChain();
    const forged = manifestFor(chain);
    forged.chainTip = 'f'.repeat(64);
    const r = verifyChain(chain, forged);
    expect(r.ok).toBe(false);
    expect(r.tamperClass).toBe('forged-tip');
    expect(r.manifestPresent).toBe(true);
    expect(r.warnings).not.toContain(NO_MANIFEST_WARNING);
  });

  it('a manifest-less tamper still surfaces the in-chain break AND the tip-anchor warning', () => {
    const chain = cleanChain();
    (chain[1].record as Record<string, unknown>).nav = '999.99'; // an in-chain modify
    const r = verifyChain(chain); // no manifest
    expect(r.ok).toBe(false); // the in-chain tamper is caught regardless of the manifest
    expect(r.tamperClass).toBe('modified-field');
    expect(r.warnings).toContain(NO_MANIFEST_WARNING); // warning still present (tip unchecked)
  });
});
