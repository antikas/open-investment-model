/**
 * Deterministic canonical JSON — the reproducibility floor under the audit hash chain.
 *
 * The hash chain (`hash-chain.ts`) folds each audit record into a SHA-256 digest. For the
 * chain to be REPRODUCIBLE — the same records always produce the same chain tip, on any run,
 * on any machine — the bytes hashed for a record must be a deterministic function of the
 * record's VALUE, not of the (insertion-order-dependent) way a particular `JSON.stringify`
 * happened to serialise it. `JSON.stringify` preserves object key INSERTION ORDER, so two
 * structurally-equal records built by different code paths can stringify differently and break
 * the chain. This module removes that non-determinism.
 *
 * `canonicalJSON(value)` produces a STABLE string for a JSON value:
 *  - object keys are emitted in ascending Unicode code-point order (`Array.prototype.sort`'s
 *    default), recursively, at every depth — so key order never depends on construction order;
 *  - arrays keep their order (array order is semantically significant — it is the data);
 *  - `undefined`, functions and symbols are dropped from objects (as `JSON.stringify` does) and
 *    rendered as `null` inside arrays (again matching `JSON.stringify`, so an array slot is never
 *    silently removed — that would shift indices);
 *  - numbers render via the JSON number grammar (`JSON.stringify(n)`); a non-finite number
 *    (`NaN`/`±Infinity`) is a hard error rather than a silent `null`, because a fiduciary audit
 *    record must never carry a non-finite numeric and silently degrade it (the audit records here
 *    carry money as decimal STRINGS, never float, so a non-finite is a defect, not data);
 *  - strings, booleans and `null` render as standard JSON.
 *
 * The output is valid JSON: `JSON.parse(canonicalJSON(v))` deep-equals `v` (modulo dropped
 * `undefined`/function keys, exactly as `JSON.parse(JSON.stringify(v))` would). It is NOT
 * whitespace-pretty — it is the compact, no-incidental-whitespace form, so whitespace can never
 * perturb the hash.
 *
 * This is a SMALL, dependency-free, in-repo util (no `json-stable-stringify` dependency): the
 * surface is exactly what the chain needs, and it is unit-pinned (`canonical-json.test.ts`) for
 * the determinism properties the chain relies on (key-order invariance, nesting, the round-trip).
 */

/** A JSON-serialisable value (the shape an audit record canonicalises over). */
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

/**
 * Render a value as canonical JSON — a deterministic string with stable (sorted) object key
 * order at every depth, compact whitespace, and array order preserved. The reproducibility
 * contract the hash chain hashes over.
 *
 * @throws on a non-finite number (NaN / ±Infinity) — a fiduciary audit record must not carry one.
 */
export function canonicalJSON(value: unknown): string {
  return render(value);
}

function render(value: unknown): string {
  if (value === null) return 'null';

  const t = typeof value;

  if (t === 'string') return JSON.stringify(value);
  if (t === 'boolean') return value ? 'true' : 'false';
  if (t === 'number') {
    if (!Number.isFinite(value as number)) {
      throw new Error(
        `canonicalJSON: refusing to serialise a non-finite number (${String(value)}) — a fiduciary ` +
          `audit record must not carry NaN/Infinity (money is carried as decimal strings, not float).`,
      );
    }
    // The JSON number grammar — JSON.stringify renders the shortest round-tripping form.
    return JSON.stringify(value);
  }
  // bigint / function / symbol / undefined at the TOP level are not valid JSON roots; inside
  // containers they are handled below (dropped from objects, null in arrays). A bare one here is
  // a programming error — surface it rather than emit malformed output.
  if (t === 'bigint') {
    throw new Error('canonicalJSON: bigint is not JSON-serialisable — convert to a string first.');
  }

  if (Array.isArray(value)) {
    // Array ORDER is significant data — preserve it. Each element is rendered; an element that is
    // undefined/function/symbol becomes `null` (exactly as JSON.stringify does — never drop a slot,
    // which would shift indices).
    const parts = value.map((el) => {
      const tt = typeof el;
      if (el === undefined || tt === 'function' || tt === 'symbol') return 'null';
      return render(el);
    });
    return `[${parts.join(',')}]`;
  }

  if (t === 'object') {
    const obj = value as Record<string, unknown>;
    // Stable key order — ascending Unicode code-point (default sort). Keys whose values are
    // undefined/function/symbol are DROPPED (as JSON.stringify does), so they cannot perturb the
    // hash by their presence-or-absence-ordering.
    const keys = Object.keys(obj)
      .filter((k) => {
        const v = obj[k];
        const vt = typeof v;
        return v !== undefined && vt !== 'function' && vt !== 'symbol';
      })
      .sort();
    const parts = keys.map((k) => `${JSON.stringify(k)}:${render(obj[k])}`);
    return `{${parts.join(',')}}`;
  }

  // undefined / function / symbol at the root — not valid JSON.
  throw new Error(`canonicalJSON: value of type ${t} is not JSON-serialisable.`);
}
