import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Unit coverage for the mirrored-networking-aware deploy-URL resolution
 * (OIM-108). The load-bearing properties under test:
 *
 *  - NAT (the current dev reality) → the WSL2 gateway IP, UNCHANGED.
 *  - mirrored (forced via the env override) → http://127.0.0.1:port (the IPv4
 *    loopback pin — NOT dual-stack `localhost` — matching the 0.0.0.0 bind).
 *  - detection absent / errored / unexpected → the gateway-IP fallback
 *    (NEVER throws past the parse, NEVER a loopback URL under NAT).
 *
 * `execFileSync` is mocked so the WSL hops (distro discovery, wslinfo, the
 * default-route probe) are simulated deterministically on ANY host — the tests
 * do not require a Windows/WSL2 machine. `process.platform` is stubbed to
 * 'win32' for the Windows-reach branch (and to 'linux' for the off-Windows
 * branch) so the same logic is exercised regardless of where the suite runs.
 */

const GATEWAY_ROUTE = 'default via 172.27.48.1 dev eth0 proto kernel \n';
const PORT = 9090;

// Hoisted mock for node:child_process.execFileSync — vi.mock is hoisted, so the
// mock fn must be created inside a hoisted block to be referenceable.
const { execFileSyncMock } = vi.hoisted(() => ({ execFileSyncMock: vi.fn() }));
vi.mock('node:child_process', () => ({ execFileSync: execFileSyncMock }));

/**
 * Route the mocked execFileSync by the wsl sub-command:
 *  - `wsl -l -q`                            → the distro listing (distro discovery)
 *  - `wsl -d <distro> -- wslinfo …`         → the networking-mode string (or throw)
 *  - `wsl -d <distro> -- ip route show …`   → the default route
 */
function wireWsl(opts: {
  networkingMode?: string | (() => never);
}): void {
  execFileSyncMock.mockImplementation((_cmd: string, args: string[]) => {
    if (args.includes('-l')) return 'Ubuntu-24.04\n';
    if (args.includes('wslinfo')) {
      const m = opts.networkingMode;
      if (typeof m === 'function') return m(); // simulate wslinfo absent / non-zero
      if (m === undefined) throw new Error('wslinfo not stubbed'); // absent
      return `${m}\n`;
    }
    if (args.includes('route')) return GATEWAY_ROUTE;
    throw new Error(`unexpected wsl call: ${args.join(' ')}`);
  });
}

/** Force process.platform for the duration of a test. */
function stubPlatform(platform: NodeJS.Platform): void {
  Object.defineProperty(process, 'platform', { value: platform, configurable: true });
}
const REAL_PLATFORM = process.platform;

beforeEach(() => {
  delete process.env.AGENTINVEST_WSL_NETWORKING;
  delete process.env.AGENTINVEST_ENDPOINT_DEPLOY_URL;
  execFileSyncMock.mockReset();
});

afterEach(() => {
  Object.defineProperty(process, 'platform', { value: REAL_PLATFORM, configurable: true });
  vi.restoreAllMocks();
  delete process.env.AGENTINVEST_WSL_NETWORKING;
  delete process.env.AGENTINVEST_ENDPOINT_DEPLOY_URL;
});

describe('resolveWslNetworkingMode (OIM-108 detection)', () => {
  it('honours the AGENTINVEST_WSL_NETWORKING=mirrored override without probing', async () => {
    process.env.AGENTINVEST_WSL_NETWORKING = 'mirrored';
    const { resolveWslNetworkingMode } = await import('./restate-reach.js');
    expect(resolveWslNetworkingMode()).toBe('mirrored');
    expect(execFileSyncMock).not.toHaveBeenCalled(); // env wins, no wsl hop
  });

  it('honours the AGENTINVEST_WSL_NETWORKING=nat override (case-insensitive, trimmed)', async () => {
    process.env.AGENTINVEST_WSL_NETWORKING = '  NAT  ';
    const { resolveWslNetworkingMode } = await import('./restate-reach.js');
    expect(resolveWslNetworkingMode()).toBe('nat');
  });

  it('reads "nat" from wslinfo (the current host reality)', async () => {
    wireWsl({ networkingMode: 'nat' });
    const { resolveWslNetworkingMode } = await import('./restate-reach.js');
    expect(resolveWslNetworkingMode()).toBe('nat');
  });

  it('reads "mirrored" from wslinfo', async () => {
    wireWsl({ networkingMode: 'mirrored' });
    const { resolveWslNetworkingMode } = await import('./restate-reach.js');
    expect(resolveWslNetworkingMode()).toBe('mirrored');
  });

  it('returns "unknown" on an unexpected wslinfo string (a future/garbled mode)', async () => {
    wireWsl({ networkingMode: 'virtioproxy' });
    const { resolveWslNetworkingMode } = await import('./restate-reach.js');
    expect(resolveWslNetworkingMode()).toBe('unknown');
  });

  it('returns "unknown" when wslinfo is absent / errors (never throws)', async () => {
    wireWsl({
      networkingMode: () => {
        throw new Error('wslinfo: command not found');
      },
    });
    const { resolveWslNetworkingMode } = await import('./restate-reach.js');
    expect(resolveWslNetworkingMode()).toBe('unknown');
  });

  it('ignores a junk override value and falls through to the probe', async () => {
    process.env.AGENTINVEST_WSL_NETWORKING = 'banana';
    wireWsl({ networkingMode: 'nat' });
    const { resolveWslNetworkingMode } = await import('./restate-reach.js');
    expect(resolveWslNetworkingMode()).toBe('nat');
  });
});

describe('resolveDeployUrl (OIM-108 mirrored-aware, backward-compatible)', () => {
  it('off-Windows (Mac/Linux): plain localhost, no WSL hop', async () => {
    stubPlatform('linux');
    const { resolveDeployUrl } = await import('./restate-reach.js');
    expect(resolveDeployUrl(PORT)).toBe(`http://localhost:${PORT}`);
    expect(execFileSyncMock).not.toHaveBeenCalled();
  });

  it('Windows + NAT (current behaviour) → the WSL2 gateway IP, UNCHANGED', async () => {
    stubPlatform('win32');
    wireWsl({ networkingMode: 'nat' });
    const { resolveDeployUrl } = await import('./restate-reach.js');
    expect(resolveDeployUrl(PORT)).toBe(`http://172.27.48.1:${PORT}`);
  });

  it('Windows + mirrored (env override) → http://127.0.0.1:port (IPv4 loopback pin, NOT the gateway IP)', async () => {
    stubPlatform('win32');
    process.env.AGENTINVEST_WSL_NETWORKING = 'mirrored';
    wireWsl({ networkingMode: 'mirrored' });
    const { resolveDeployUrl } = await import('./restate-reach.js');
    const url = resolveDeployUrl(PORT);
    expect(url).toBe(`http://127.0.0.1:${PORT}`);
    expect(url).not.toContain('172.27.48.1'); // mirrored is loopback, NOT the gateway IP
    expect(url).not.toContain('localhost'); // pinned to unambiguous IPv4, not dual-stack
  });

  it('Windows + mirrored detected via wslinfo → http://127.0.0.1:port (IPv4 loopback pin)', async () => {
    stubPlatform('win32');
    wireWsl({ networkingMode: 'mirrored' });
    const { resolveDeployUrl } = await import('./restate-reach.js');
    const url = resolveDeployUrl(PORT);
    expect(url).toBe(`http://127.0.0.1:${PORT}`);
    expect(url).not.toContain('172.27.48.1'); // mirrored is loopback, NOT the gateway IP
  });

  it('Windows + detection ABSENT/errored → the gateway-IP fallback (never localhost-under-NAT)', async () => {
    stubPlatform('win32');
    wireWsl({
      networkingMode: () => {
        throw new Error('wslinfo: command not found');
      },
    });
    const { resolveDeployUrl } = await import('./restate-reach.js');
    const url = resolveDeployUrl(PORT);
    expect(url).toBe(`http://172.27.48.1:${PORT}`);
    expect(url).not.toContain('localhost'); // the load-bearing safety property
  });

  it('Windows + unexpected wslinfo output → the gateway-IP fallback (safe default)', async () => {
    stubPlatform('win32');
    wireWsl({ networkingMode: 'virtioproxy' });
    const { resolveDeployUrl } = await import('./restate-reach.js');
    expect(resolveDeployUrl(PORT)).toBe(`http://172.27.48.1:${PORT}`);
  });

  it('an explicit AGENTINVEST_ENDPOINT_DEPLOY_URL bypasses detection entirely', async () => {
    stubPlatform('win32');
    process.env.AGENTINVEST_ENDPOINT_DEPLOY_URL = 'http://example.test:9999';
    const { resolveDeployUrl } = await import('./restate-reach.js');
    expect(resolveDeployUrl(PORT)).toBe('http://example.test:9999');
    expect(execFileSyncMock).not.toHaveBeenCalled();
  });

  it('Windows + NAT resolves the distro ONCE per call (the dedupe — no redundant wsl -l -q)', async () => {
    stubPlatform('win32');
    wireWsl({ networkingMode: 'nat' });
    const { resolveDeployUrl } = await import('./restate-reach.js');
    expect(resolveDeployUrl(PORT)).toBe(`http://172.27.48.1:${PORT}`);
    // The NAT path runs the mode probe (wslinfo) AND the gateway discovery (ip
    // route); pre-dedupe each re-ran `wsl -l -q`, so the distro listing was
    // spawned twice. After the dedupe the distro is discovered exactly once.
    const distroCalls = execFileSyncMock.mock.calls.filter((c) => (c[1] as string[]).includes('-l'));
    expect(distroCalls.length).toBe(1);
  });

  it('Windows + mirrored (env override) never spawns a distro lookup (lazy getter, behaviour preserved)', async () => {
    stubPlatform('win32');
    process.env.AGENTINVEST_WSL_NETWORKING = 'mirrored';
    wireWsl({ networkingMode: 'mirrored' });
    const { resolveDeployUrl } = await import('./restate-reach.js');
    expect(resolveDeployUrl(PORT)).toBe(`http://127.0.0.1:${PORT}`);
    // The override short-circuits the wslinfo probe AND the gateway branch is
    // never reached, so the memoized getter is never invoked — ZERO distro
    // spawns, exactly as before the dedupe.
    const distroCalls = execFileSyncMock.mock.calls.filter((c) => (c[1] as string[]).includes('-l'));
    expect(distroCalls.length).toBe(0);
  });
});
