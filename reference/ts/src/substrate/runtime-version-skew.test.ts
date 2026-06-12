import { afterEach, describe, expect, it, vi } from 'vitest';
import { checkRuntimeVersionSkew, readRunningServerVersion } from './restate-reach.js';

/**
 * Unit coverage for the RUNTIME version-skew check the orchestrator's gate uses
 * (distinct from the launcher's start-time guard). We mock the admin /version
 * fetch so the skew classification is tested without a live server.
 */
function mockAdminVersion(body: string | null, ok = true): void {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url: string | URL | Request) => {
    const u = String(url);
    if (u.endsWith('/version') || u.endsWith('/health')) {
      if (body === null) {
        return new Response('', { status: ok ? 200 : 500 });
      }
      return new Response(body, { status: ok ? 200 : 500, headers: { 'content-type': 'application/json' } });
    }
    return new Response('', { status: 404 });
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('readRunningServerVersion', () => {
  it('parses the version from the admin /version JSON body', async () => {
    mockAdminVersion(JSON.stringify({ version: '1.6.2', max_admin_api_version: 3 }));
    expect(await readRunningServerVersion()).toBe('1.6.2');
  });

  it('returns null when the version cannot be determined', async () => {
    mockAdminVersion(null, false);
    expect(await readRunningServerVersion()).toBeNull();
  });
});

describe('checkRuntimeVersionSkew (block-new-ops classification)', () => {
  it('reports a match cleanly — no mismatch, not indeterminate (gate proceeds silently)', async () => {
    mockAdminVersion(JSON.stringify({ version: '1.6.2' }));
    const skew = await checkRuntimeVersionSkew('1.6.2');
    expect(skew).toEqual({ running: '1.6.2', pinned: '1.6.2', mismatch: false, indeterminate: false });
  });

  it('reports a definite mismatch — gate blocks new ops', async () => {
    mockAdminVersion(JSON.stringify({ version: '1.7.0' }));
    const skew = await checkRuntimeVersionSkew('1.6.2');
    expect(skew.mismatch).toBe(true);
    expect(skew.indeterminate).toBe(false);
    expect(skew.running).toBe('1.7.0');
  });

  it('reports indeterminate (unreadable) without flagging a mismatch — gate does NOT block', async () => {
    mockAdminVersion(null, false);
    const skew = await checkRuntimeVersionSkew('1.6.2');
    expect(skew.mismatch).toBe(false);
    expect(skew.indeterminate).toBe(true);
    expect(skew.running).toBeNull();
  });
});
