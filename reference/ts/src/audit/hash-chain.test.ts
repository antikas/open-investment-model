/**
 * Unit proof of the SHA-256 audit hash chain (OIM-151) — the tamper-evidence heart.
 *
 * Pins: well-formed chain (seq + prevHash + chainHash links); the genesis seed for seq 0; the chain
 * is DETERMINISTIC + REPRODUCIBLE (the same records → the same chain + tip across runs); a record
 * edit changes the tip; `recomputeChain` reproduces the chainer's hashes; key-order in a record does
 * NOT change the hash (canonical JSON); the chainHash formula is sha256(prevHash || canonicalJSON).
 */
import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import {
  chainRecords,
  recomputeChain,
  computeChainHash,
  chainTip,
  GENESIS_SEED,
} from './hash-chain.js';
import { canonicalJSON } from './canonical-json.js';

function records() {
  return [
    { operationId: 'op-1', recordType: 'operation-closed', value: 10 },
    { operationId: 'op-2', recordType: 'nav-published', value: 20 },
    { operationId: 'op-3', recordType: 'operation-closed', value: 30 },
  ];
}

describe('chainRecords', () => {
  it('produces a well-formed chain: contiguous seqs, genesis seed at seq 0, links chain', () => {
    const chain = chainRecords(records());
    expect(chain.map((e) => e.seq)).toEqual([0, 1, 2]);
    expect(chain[0].prevHash).toBe(GENESIS_SEED);
    // each entry's prevHash is the prior entry's chainHash.
    expect(chain[1].prevHash).toBe(chain[0].chainHash);
    expect(chain[2].prevHash).toBe(chain[1].chainHash);
    // every chainHash is a 64-hex SHA-256 digest.
    for (const e of chain) expect(e.chainHash).toMatch(/^[0-9a-f]{64}$/);
  });

  it('chainHash = sha256(prevHash || canonicalJSON(record)) — the documented formula', () => {
    const recs = records();
    const chain = chainRecords(recs);
    const expected0 = createHash('sha256')
      .update(GENESIS_SEED, 'utf8')
      .update(canonicalJSON(recs[0]), 'utf8')
      .digest('hex');
    expect(chain[0].chainHash).toBe(expected0);
    expect(computeChainHash(GENESIS_SEED, recs[0])).toBe(expected0);
  });

  it('is DETERMINISTIC + REPRODUCIBLE — the same records produce the same chain + tip every run', () => {
    const a = chainRecords(records());
    const b = chainRecords(records());
    expect(a).toEqual(b);
    expect(chainTip(a)).toBe(chainTip(b));
  });

  it('the tip is STABLE across runs (the reproducibility property the audit gate proves)', () => {
    const tip1 = chainTip(chainRecords(records()));
    const tip2 = chainTip(chainRecords(records()));
    expect(tip1).toBe(tip2);
    expect(tip1).toMatch(/^[0-9a-f]{64}$/);
  });

  it('key ORDER inside a record does NOT change the hash (canonical JSON folds it out)', () => {
    const r1 = [{ a: 1, b: 2, c: 3 }];
    const r2 = [{ c: 3, b: 2, a: 1 }];
    expect(chainTip(chainRecords(r1))).toBe(chainTip(chainRecords(r2)));
  });

  it('an edit to ANY record changes the tip (tamper evidence)', () => {
    const base = chainTip(chainRecords(records()));
    const edited = records();
    edited[1] = { ...edited[1], value: 999 };
    expect(chainTip(chainRecords(edited))).not.toBe(base);
  });

  it('REORDERING records changes the tip (order is part of the fold)', () => {
    const base = chainTip(chainRecords(records()));
    const recs = records();
    [recs[0], recs[1]] = [recs[1], recs[0]];
    expect(chainTip(chainRecords(recs))).not.toBe(base);
  });

  it('the empty chain has the genesis seed as its tip', () => {
    expect(chainTip(chainRecords([]))).toBe(GENESIS_SEED);
  });
});

describe('recomputeChain', () => {
  it('reproduces the chainer hashes exactly (one hash SSOT for chain + verify)', () => {
    const recs = records();
    const chain = chainRecords(recs);
    const re = recomputeChain(recs);
    expect(re.length).toBe(chain.length);
    for (let i = 0; i < chain.length; i++) {
      expect(re[i].prevHash).toBe(chain[i].prevHash);
      expect(re[i].chainHash).toBe(chain[i].chainHash);
    }
  });
});
