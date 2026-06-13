/**
 * Unit proof of the GATHER network branch — the two best-effort
 * NETWORK calls (`enumerateOperationKeys` over the admin `/query`, `readOperationState` over the
 * ingress `status`) and the `gatherAuditRecords` end-to-end fold, alongside the pure
 * `extractAuditRecords`.
 *
 * These tests MOCK `globalThis.fetch` (restored after each — no global leak) and route by URL so the
 * parse path and EVERY best-effort-degrade path is pinned WITHOUT a live server:
 *  - a well-formed response → the parsed keys / state;
 *  - a non-200, a thrown fetch, and a malformed body → `[]` / `null` (honest degrade, never a throw,
 *    never a fabricated record).
 * The end-to-end gather enumerates → reads each → extracts → returns the records in DETERMINISTIC
 * chain order; an unreachable admin yields an EMPTY gather (no throw).
 *
 * No live `:9070`/`:8080` — the mocked fetch is the only network surface.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  enumerateOperationKeys,
  readOperationState,
  gatherAuditRecords,
  type GatherEndpoints,
} from './gather.js';

const ENDPOINTS: GatherEndpoints = {
  adminUrl: 'http://admin.test',
  ingressUrl: 'http://ingress.test',
};

const REAL_FETCH = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = REAL_FETCH; // restore — no global leak
  vi.restoreAllMocks();
});

/** A minimal Response-like stand-in: ok flag + a json() that returns (or rejects with) a body. */
function jsonResponse(ok: boolean, body: unknown): Response {
  return {
    ok,
    json: async () => body,
  } as unknown as Response;
}

/** A Response whose json() rejects (a malformed body that is not valid JSON). */
function malformedJsonResponse(): Response {
  return {
    ok: true,
    json: async () => {
      throw new SyntaxError('Unexpected token in JSON');
    },
  } as unknown as Response;
}

/** Stub globalThis.fetch with a routed implementation. */
function stubFetch(impl: (url: string) => Response | Promise<Response>): void {
  globalThis.fetch = vi.fn((input: RequestInfo | URL) =>
    Promise.resolve().then(() => impl(String(input))),
  ) as unknown as typeof fetch;
}

// ---- enumerateOperationKeys -------------------------------------------------------------------

describe('enumerateOperationKeys — admin /query parse + best-effort degrade', () => {
  it('parses a well-formed admin /query response into distinct {operationId, kind} keys', async () => {
    stubFetch(() =>
      jsonResponse(true, {
        rows: [
          { target_service_name: 'investmentOperation', target_service_key: 'op-attr-1' },
          { target_service_name: 'navCalculation', target_service_key: 'nav-PF0003-1' },
          // a duplicate key (de-duped via the Map), and a null key (skipped), and an unknown svc.
          { target_service_name: 'investmentOperation', target_service_key: 'op-attr-1' },
          { target_service_name: 'investmentOperation', target_service_key: null },
          { target_service_name: 'somethingElse', target_service_key: 'x' },
        ],
      }),
    );
    const keys = await enumerateOperationKeys(ENDPOINTS);
    expect(keys).toEqual([
      { operationId: 'op-attr-1', kind: 'investmentOperation' },
      { operationId: 'nav-PF0003-1', kind: 'navCalculation' },
    ]);
  });

  it('returns [] on a non-200 (best-effort, no throw)', async () => {
    stubFetch(() => jsonResponse(false, { rows: [] }));
    await expect(enumerateOperationKeys(ENDPOINTS)).resolves.toEqual([]);
  });

  it('returns [] when fetch THROWS (an unreachable admin — no throw past the gather)', async () => {
    stubFetch(() => {
      throw new TypeError('fetch failed');
    });
    await expect(enumerateOperationKeys(ENDPOINTS)).resolves.toEqual([]);
  });

  it('returns [] on a malformed body (json() rejects)', async () => {
    stubFetch(() => malformedJsonResponse());
    await expect(enumerateOperationKeys(ENDPOINTS)).resolves.toEqual([]);
  });

  it('returns [] when the body has no rows (a shape with rows absent)', async () => {
    stubFetch(() => jsonResponse(true, {}));
    await expect(enumerateOperationKeys(ENDPOINTS)).resolves.toEqual([]);
  });
});

// ---- readOperationState -----------------------------------------------------------------------

describe('readOperationState — ingress status parse + best-effort degrade', () => {
  it('parses a well-formed ingress status response into the recorded state', async () => {
    const state = { auditRecord: { kind: 'operation-closed', operationId: 'op-attr-1' } };
    stubFetch(() => jsonResponse(true, state));
    await expect(readOperationState('investmentOperation', 'op-attr-1', ENDPOINTS)).resolves.toEqual(
      state,
    );
  });

  it('returns null on a non-200', async () => {
    stubFetch(() => jsonResponse(false, {}));
    await expect(
      readOperationState('navCalculation', 'nav-1', ENDPOINTS),
    ).resolves.toBeNull();
  });

  it('returns null when fetch THROWS (an unreachable ingress)', async () => {
    stubFetch(() => {
      throw new TypeError('fetch failed');
    });
    await expect(
      readOperationState('investmentOperation', 'op-attr-1', ENDPOINTS),
    ).resolves.toBeNull();
  });

  it('returns null on a malformed body (json() rejects)', async () => {
    stubFetch(() => malformedJsonResponse());
    await expect(
      readOperationState('investmentOperation', 'op-attr-1', ENDPOINTS),
    ).resolves.toBeNull();
  });
});

// ---- gatherAuditRecords (end-to-end over the mock) --------------------------------------------

describe('gatherAuditRecords — enumerate → read → extract → ordered records', () => {
  it('gathers the real records end-to-end in deterministic chain order', async () => {
    // The enumerate sees two ops; each ingress read returns a state carrying one audit record.
    const states: Record<string, Record<string, unknown>> = {
      'investmentOperation/op-attr-1': {
        auditRecord: { kind: 'operation-closed', operationId: 'op-attr-1', status: 'completed' },
      },
      'navCalculation/nav-PF0003-1': {
        publishRecord: {
          kind: 'nav-published',
          workflowId: 'nav-PF0003-1',
          struckAt: '2026-06-01T10:00:00.000Z',
        },
      },
    };
    stubFetch((url) => {
      if (url.startsWith(ENDPOINTS.adminUrl)) {
        return jsonResponse(true, {
          rows: [
            { target_service_name: 'investmentOperation', target_service_key: 'op-attr-1' },
            { target_service_name: 'navCalculation', target_service_key: 'nav-PF0003-1' },
          ],
        });
      }
      // ingress: /<kind>/<id>/status — match the kind/id segment.
      for (const [seg, state] of Object.entries(states)) {
        if (url.includes(`/${seg}/status`)) return jsonResponse(true, state);
      }
      return jsonResponse(false, {});
    });

    const result = await gatherAuditRecords(ENDPOINTS);
    expect(result.keysSeen).toBe(2);
    expect(result.statesRead).toBe(2);
    expect(result.records).toHaveLength(2);
    // Deterministic chain order: the timestamped nav-published sorts before the null-occurredAt
    // operation-closed (occurredAt non-null first).
    expect(result.records.map((r) => r.recordType)).toEqual([
      'nav-published',
      'operation-closed',
    ]);
    expect(result.records.map((r) => r.operationId)).toEqual(['nav-PF0003-1', 'op-attr-1']);
  });

  it('an unreachable admin → an EMPTY gather (honest, not a throw)', async () => {
    stubFetch((url) => {
      if (url.startsWith(ENDPOINTS.adminUrl)) {
        throw new TypeError('fetch failed'); // admin unreachable
      }
      return jsonResponse(false, {});
    });
    const result = await gatherAuditRecords(ENDPOINTS);
    expect(result.keysSeen).toBe(0);
    expect(result.statesRead).toBe(0);
    expect(result.records).toEqual([]);
  });

  it('keys enumerate but the ingress reads all fail → keys seen, zero states read, no records', async () => {
    stubFetch((url) => {
      if (url.startsWith(ENDPOINTS.adminUrl)) {
        return jsonResponse(true, {
          rows: [{ target_service_name: 'investmentOperation', target_service_key: 'op-1' }],
        });
      }
      return jsonResponse(false, {}); // every ingress read is a non-200
    });
    const result = await gatherAuditRecords(ENDPOINTS);
    expect(result.keysSeen).toBe(1);
    expect(result.statesRead).toBe(0);
    expect(result.records).toEqual([]);
  });

  it('a state with neither audit field yields no fabricated record', async () => {
    stubFetch((url) => {
      if (url.startsWith(ENDPOINTS.adminUrl)) {
        return jsonResponse(true, {
          rows: [{ target_service_name: 'investmentOperation', target_service_key: 'op-inflight' }],
        });
      }
      return jsonResponse(true, { someOtherField: 1 }); // a readable but non-audit state
    });
    const result = await gatherAuditRecords(ENDPOINTS);
    expect(result.keysSeen).toBe(1);
    expect(result.statesRead).toBe(1); // the state read succeeded ...
    expect(result.records).toEqual([]); // ... but carried no audit record (never fabricated)
  });
});
