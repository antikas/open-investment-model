/**
 * Unit proof of the deterministic canonical JSON — the reproducibility floor under the
 * hash chain. Pins: stable (sorted) key order at every depth; key-order INVARIANCE (two
 * differently-constructed equal objects canonicalise identically); array order preserved; the JSON
 * round-trip; the non-finite-number guard.
 */
import { describe, expect, it } from 'vitest';
import { canonicalJSON } from './canonical-json.js';

describe('canonicalJSON', () => {
  it('sorts object keys ascending at the top level', () => {
    expect(canonicalJSON({ b: 1, a: 2, c: 3 })).toBe('{"a":2,"b":1,"c":3}');
  });

  it('is INVARIANT to key insertion order (the determinism property the chain needs)', () => {
    const a = { z: 1, m: { y: 2, x: 3 }, a: [1, 2] };
    const b = { a: [1, 2], m: { x: 3, y: 2 }, z: 1 };
    // Two objects built in different key orders must canonicalise to the SAME string.
    expect(canonicalJSON(a)).toBe(canonicalJSON(b));
    expect(canonicalJSON(a)).toBe('{"a":[1,2],"m":{"x":3,"y":2},"z":1}');
  });

  it('sorts keys recursively at every depth', () => {
    expect(canonicalJSON({ outer: { d: 1, c: 2, nested: { b: 1, a: 2 } } })).toBe(
      '{"outer":{"c":2,"d":1,"nested":{"a":2,"b":1}}}',
    );
  });

  it('PRESERVES array order (array order is significant data)', () => {
    expect(canonicalJSON([3, 1, 2])).toBe('[3,1,2]');
    expect(canonicalJSON({ xs: ['b', 'a', 'c'] })).toBe('{"xs":["b","a","c"]}');
  });

  it('renders strings, booleans, null and numbers per JSON', () => {
    expect(canonicalJSON('hi')).toBe('"hi"');
    expect(canonicalJSON(true)).toBe('true');
    expect(canonicalJSON(false)).toBe('false');
    expect(canonicalJSON(null)).toBe('null');
    expect(canonicalJSON(42)).toBe('42');
    expect(canonicalJSON(-0.5)).toBe('-0.5');
  });

  it('drops undefined/function keys from objects (as JSON.stringify does)', () => {
    expect(canonicalJSON({ a: 1, b: undefined, c: () => 1 } as unknown)).toBe('{"a":1}');
  });

  it('renders undefined/function array slots as null (never drops a slot — indices must not shift)', () => {
    expect(canonicalJSON([1, undefined, 3] as unknown)).toBe('[1,null,3]');
  });

  it('round-trips: JSON.parse(canonicalJSON(v)) deep-equals v', () => {
    const v = { kind: 'nav-published', nav: '1234.56', positions: [{ id: 'A' }, { id: 'B' }], flag: true };
    expect(JSON.parse(canonicalJSON(v))).toEqual(v);
  });

  it('REFUSES a non-finite number (a fiduciary record must not carry NaN/Infinity)', () => {
    expect(() => canonicalJSON({ x: NaN })).toThrow(/non-finite/);
    expect(() => canonicalJSON(Infinity)).toThrow(/non-finite/);
  });

  it('escapes special characters in keys and string values', () => {
    expect(canonicalJSON({ 'a"b': 'x\ny' })).toBe('{"a\\"b":"x\\ny"}');
  });
});
