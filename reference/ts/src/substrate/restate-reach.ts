/**
 * Shared-Restate reach for agentINVEST local dev.
 *
 * agentINVEST reuses the single self-hosted `restate-server` shared with a
 * sibling project sharing the dev substrate in local dev (one shared RUNNING
 * instance for both
 * projects; handlers are namespaced by service name so there is no collision).
 *
 * P-R1 (OIM-101): the substrate is now booted by OpenIM's OWN launcher
 * (`reference/scripts/run-restate-server.mjs`, `pnpm dev:restate` from
 * `reference/`), pinned by OpenIM's own `install-restate.mjs`. A fresh OpenIM
 * checkout no longer reads the sibling project's source files to bring its
 * substrate
 * up. The error messages below point at the OpenIM-owned launcher.
 *
 * Reach mechanism on this workstation:
 *  - `restate-server` runs INSIDE WSL2 (the Linux-musl binary) and exposes its
 *    admin API on `127.0.0.1:9070` and HTTP ingress on `127.0.0.1:8080`, both
 *    visible from the Windows host through WSL2's localhost-forwarding.
 *  - A handler endpoint running on the Windows host (the TS endpoint) is reached
 *    by Restate-in-WSL2 over a path that depends on the WSL2 NETWORKING MODE:
 *      · under default **NAT** networking, at the WSL2 default-gateway IP (the
 *        Windows host as seen from inside the VM), NOT `localhost`. We discover
 *        that gateway IP via the running distro (P-R4: discovered, with an
 *        explicit override, never a bare hardcode).
 *      · under **mirrored** networking, WSL2 shares the host loopback, so the
 *        Windows endpoint is reached at the host loopback `127.0.0.1` (OIM-108;
 *        pinned IPv4, not dual-stack `localhost`, to match the 0.0.0.0 bind).
 *    `resolveDeployUrl` detects the mode and picks the right form — defaulting
 *    SAFELY to the NAT/gateway-IP path on ANY detection uncertainty, so current
 *    NAT dev is unchanged and a loopback-under-NAT (which would break the
 *    registration) is never returned.
 *  - A handler endpoint running INSIDE WSL2 (the Python endpoint, OIM-101) is
 *    reached by Restate-in-WSL2 over `localhost` (same network namespace).
 *  - On Mac/Linux there is no WSL2 layer; `localhost` is correct throughout.
 *
 * Override env vars:
 *  - RESTATE_ADMIN_URL          (default http://localhost:9070)
 *  - RESTATE_INGRESS_URL        (default http://localhost:8080)
 *  - AGENTINVEST_ENDPOINT_PORT  (default 9090 — the TS endpoint; distinct from the sibling project's 9080)
 *  - AGENTINVEST_PY_ENDPOINT_PORT (default 9091 — the Python endpoint, OIM-101 P-R6)
 *  - AGENTINVEST_ENDPOINT_DEPLOY_URL  (explicit override; skips WSL2 discovery + mode detection)
 *  - AGENTINVEST_WSL_NETWORKING (mirrored|nat — force the networking mode; skips wslinfo detection)
 *  - RESTATE_WSL_DISTRO         (explicit distro override; Windows only)
 */
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

export const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://localhost:9070';
export const INGRESS_URL = process.env.RESTATE_INGRESS_URL ?? 'http://localhost:8080';

/**
 * The `reference/` workspace root, resolved DYNAMICALLY (OIM-107, F-2) from this
 * module's own location — never a hardcoded absolute checkout path, so the
 * hint is correct for ANY checkout location (a contributor clone, a CI runner, a
 * differently-lettered drive). Override with REFERENCE_ROOT.
 *
 * This file lives at reference/ts/src/substrate/restate-reach.ts, so the
 * workspace root is three directories up.
 */
export const REFERENCE_ROOT =
  process.env.REFERENCE_ROOT ??
  path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

/**
 * The TS handler endpoint port. Distinct from the sibling project's runtime
 * (9080) so both
 * projects' endpoints register against the one shared Restate without a clash.
 */
export const ENDPOINT_PORT = Number(process.env.AGENTINVEST_ENDPOINT_PORT ?? 9090);

/**
 * The Python handler endpoint port (OIM-101, P-R6). Distinct from the TS
 * endpoint (9090) so the TS and Python deployments are two separate
 * registrations against the same Restate, each on its own port.
 */
export const PY_ENDPOINT_PORT = Number(process.env.AGENTINVEST_PY_ENDPOINT_PORT ?? 9091);

/**
 * The OpenIM-owned launch command, for error messages (P-R1: OpenIM's own, not
 * a sibling's).
 * The path is resolved dynamically from REFERENCE_ROOT (OIM-107, F-2), so the
 * hint is correct for any checkout location, never a hardcoded absolute path.
 */
export const LAUNCH_HINT = `(cd ${REFERENCE_ROOT} && pnpm dev:restate)`;

/** True on a Windows host where Restate runs inside WSL2. */
export function isWindowsWsl2Host(): boolean {
  return process.platform === 'win32';
}

/**
 * Discover the WSL2 distro Restate runs in (P-R4: discovery + explicit
 * override, never a bare hardcode).
 *
 * Order: RESTATE_WSL_DISTRO override → the first distro `wsl -l -q` reports as
 * installed → throw a recoverable error. The historical code hardcoded
 * `Ubuntu-24.04`; this discovers the actual running default and only falls back
 * to the conventional name if discovery yields nothing.
 */
export function resolveWslDistro(): string {
  if (process.env.RESTATE_WSL_DISTRO) return process.env.RESTATE_WSL_DISTRO;
  try {
    // WSL_UTF8=1 forces UTF-8 output (the historical default is UTF-16LE, which
    // would mangle the parse into null-byte-interleaved garbage).
    const listing = execFileSync('wsl', ['-l', '-q'], {
      encoding: 'utf8',
      env: { ...process.env, WSL_UTF8: '1' },
    });
    const distros = listing
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (distros.length > 0) return distros[0];
  } catch {
    /* fall through to the conventional default */
  }
  return 'Ubuntu-24.04';
}

/**
 * The WSL2 networking mode, as it affects how Restate-in-WSL2 reaches a
 * Windows-host endpoint. `'mirrored'` and `'nat'` are the two modes WSL2 reports;
 * `'unknown'` is returned whenever the mode cannot be established UNAMBIGUOUSLY
 * (wslinfo absent, a non-zero exit, an unexpected string, or any error). The
 * caller treats `'unknown'` exactly like `'nat'` — the safe default — so a
 * detection failure NEVER yields a localhost-under-NAT URL.
 */
export type WslNetworkingMode = 'mirrored' | 'nat' | 'unknown';

/**
 * Detect the WSL2 networking mode (OIM-108). Order:
 *  1. The `AGENTINVEST_WSL_NETWORKING` env override (`mirrored`|`nat`) — the
 *     escape hatch + the test seam; any other value is ignored and we probe.
 *  2. `wslinfo --networking-mode` in the running distro. An EXACT `mirrored` or
 *     `nat` (case-insensitive, trimmed) is taken; anything else → `'unknown'`.
 *  3. On wslinfo being absent / non-zero / throwing → `'unknown'`.
 *
 * Never throws: every failure path collapses to `'unknown'` (the safe default).
 * Off a Windows host this is not consulted by `resolveDeployUrl` (localhost is
 * correct on Mac/Linux regardless), but the function itself is host-agnostic so
 * it is unit-testable via the env override on any platform.
 *
 * @param getDistro  optional lazy distro provider, so a caller can share a
 *   single `wsl -l -q` discovery between this mode probe and its gateway path.
 *   It is only invoked if the probe is actually needed — the env override
 *   short-circuits before any distro lookup, exactly as before. Defaults to
 *   `resolveWslDistro` so standalone callers are unaffected.
 */
export function resolveWslNetworkingMode(
  getDistro: () => string = resolveWslDistro,
): WslNetworkingMode {
  const override = process.env.AGENTINVEST_WSL_NETWORKING?.trim().toLowerCase();
  if (override === 'mirrored' || override === 'nat') return override;

  try {
    const out = execFileSync('wsl', ['-d', getDistro(), '--', 'wslinfo', '--networking-mode'], {
      encoding: 'utf8',
      env: { ...process.env, WSL_UTF8: '1' },
    });
    const mode = out.trim().toLowerCase();
    if (mode === 'mirrored') return 'mirrored';
    if (mode === 'nat') return 'nat';
    // An unexpected string (a future mode, a localised/garbled line, an empty
    // body) is NOT trusted — fall back to the safe default.
    return 'unknown';
  } catch {
    // wslinfo absent (older WSL build), non-zero exit, or the wsl hop failed —
    // the mode is indeterminate. Safe default.
    return 'unknown';
  }
}

/**
 * Discover the WSL2 default-gateway IP (= the Windows host, as seen from inside
 * the WSL2 VM) — the reach path under NAT networking. Uses the
 * discovered/overridden distro (P-R4). Throws if the default route cannot be
 * parsed (a genuinely-broken WSL2 network is a fail-loud condition, as before).
 *
 * @param getDistro  optional lazy distro provider, so a caller can share a
 *   single `wsl -l -q` discovery between its mode probe and this gateway path;
 *   defaults to `resolveWslDistro` so standalone callers are unaffected.
 */
function resolveWslGatewayUrl(port: number, getDistro: () => string = resolveWslDistro): string {
  const route = execFileSync('wsl', ['-d', getDistro(), '--', 'ip', 'route', 'show', 'default'], {
    encoding: 'utf8',
    env: { ...process.env, WSL_UTF8: '1' },
  });
  const m = route.match(/default via (\S+)/);
  if (!m) {
    throw new Error(`failed to parse WSL2 default route for deploy URL: ${JSON.stringify(route)}`);
  }
  return `http://${m[1]}:${port}`;
}

/**
 * The URL Restate (inside WSL2 on Windows) should use to reach a handler
 * endpoint running on the Windows host. On Mac/Linux this is plain localhost.
 *
 * On Windows the form depends on the WSL2 networking mode (OIM-108):
 *  - **mirrored** (detected unambiguously) → `http://127.0.0.1:${port}` (WSL2
 *    shares the host loopback under mirrored networking). Pinned to the IPv4
 *    127.0.0.1, NOT dual-stack `localhost`, because the TS endpoint binds
 *    0.0.0.0 (IPv4 wildcard only) — a `::1`-first `localhost` resolution would
 *    miss the bind.
 *  - **NAT, or ANY detection uncertainty** (wslinfo absent / non-zero / weird
 *    output) → the WSL2 default-gateway-IP discovery (unchanged behaviour).
 *
 * The safe default is the NAT/gateway-IP path: returning a loopback URL under
 * NAT would break the TS-endpoint registration, so it is never returned unless
 * mirrored is established unambiguously. Force the mode with
 * `AGENTINVEST_WSL_NETWORKING=mirrored|nat`; bypass everything with an explicit
 * `AGENTINVEST_ENDPOINT_DEPLOY_URL`.
 *
 * @param port  the endpoint port (defaults to the TS endpoint port).
 */
export function resolveDeployUrl(port: number = ENDPOINT_PORT): string {
  if (process.env.AGENTINVEST_ENDPOINT_DEPLOY_URL) {
    return process.env.AGENTINVEST_ENDPOINT_DEPLOY_URL;
  }
  if (!isWindowsWsl2Host()) {
    return `http://localhost:${port}`;
  }
  // Windows: pick the reach form by the WSL2 networking mode. Only an
  // unambiguous `mirrored` switches to the host loopback; NAT and `unknown` (the
  // safe default) both take the gateway-IP path — current behaviour is preserved
  // exactly when detection is unavailable or ambiguous.
  //
  // Discover the distro at most ONCE per call and thread it into both the mode
  // probe and the gateway discovery: without the env override, the NAT path
  // otherwise spawns `wsl -l -q` twice per call (mode detection + the redundant
  // re-discovery in the gateway path). The getter is
  // lazy + memoized, so the env-override path (which never probes wslinfo and
  // never hits the gateway branch) still spawns ZERO distro lookups — current
  // behaviour preserved exactly on every path.
  let cachedDistro: string | undefined;
  const distro = (): string => (cachedDistro ??= resolveWslDistro());
  if (resolveWslNetworkingMode(distro) === 'mirrored') {
    // Pin to 127.0.0.1, NOT `localhost`. On Windows `localhost` is dual-stack
    // (127.0.0.1 + ::1) and many clients try ::1 first, but the TS endpoint
    // binds 0.0.0.0 (the IPv4 wildcard only — NOT ::), so a ::1-first
    // resolution would hit nothing. 127.0.0.1 is unambiguous IPv4 matching the
    // bind, removing the ::1-ambiguity failure mode under mirrored.
    return `http://127.0.0.1:${port}`;
  }
  return resolveWslGatewayUrl(port, distro);
}

/**
 * The URL Restate-in-WSL2 should use to reach a handler endpoint running INSIDE
 * WSL2 (the Python endpoint, OIM-101). Same network namespace → plain localhost
 * regardless of host OS.
 *
 * @param port  the in-WSL2 endpoint port (defaults to the Python endpoint port).
 */
export function resolveWslLocalDeployUrl(port: number = PY_ENDPOINT_PORT): string {
  return `http://localhost:${port}`;
}

/** Block until the shared Restate admin API answers /health, or throw. */
export async function awaitAdminReady(timeoutSeconds = 30): Promise<void> {
  const deadline = Date.now() + timeoutSeconds * 1000;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${ADMIN_URL}/health`, { signal: AbortSignal.timeout(2000) });
      if (r.ok) return;
    } catch {
      /* not up yet — retry */
    }
    await new Promise((res) => setTimeout(res, 500));
  }
  throw new Error(
    `Shared Restate admin at ${ADMIN_URL} not reachable within ${timeoutSeconds}s. ` +
      `Is the substrate running? Boot it with OpenIM's OWN launcher: ${LAUNCH_HINT}. ` +
      `See reference/ts/README.md.`,
  );
}

/**
 * The Restate server version OpenIM pins (the version contract). Kept in sync
 * with the installer's pin; the runtime skew check compares the live server
 * against this value. Override with RESTATE_PINNED_VERSION (test seam).
 */
export const OPENIM_PINNED_RESTATE_VERSION =
  process.env.RESTATE_PINNED_VERSION ?? '1.6.2';

/** The outcome of a runtime version-skew check. */
export interface VersionSkewStatus {
  /** The version the live server reports, or null if it could not be read. */
  running: string | null;
  /** The version OpenIM pins. */
  pinned: string;
  /** True iff a definite mismatch was observed (running known AND != pinned). */
  mismatch: boolean;
  /** True iff the running version could not be determined (indeterminate). */
  indeterminate: boolean;
}

/**
 * Read the live Restate server's reported version via the admin surface, or
 * null if it cannot be determined (an older server, or the endpoint is absent).
 *
 * Parses defensively: the admin `/version` body carries a JSON `"version"`
 * field; older builds report it only in a header. The shape is the same one the
 * launcher's start-time guard uses, lifted here so the long-lived orchestrator
 * session can re-check mid-session, not just at launch.
 */
export async function readRunningServerVersion(timeoutMs = 1500): Promise<string | null> {
  for (const p of ['/version', '/health']) {
    try {
      const res = await fetch(`${ADMIN_URL}${p}`, { signal: AbortSignal.timeout(timeoutMs) });
      if (!res.ok) continue;
      const text = await res.text();
      const hdr = res.headers.get('x-restate-server-version') ?? res.headers.get('server');
      const m =
        text.match(/"version"\s*:\s*"([^"]+)"/) ??
        (hdr ? hdr.match(/(\d+\.\d+\.\d+)/) : null) ??
        text.match(/(\d+\.\d+\.\d+)/);
      if (m) return m[1];
    } catch {
      /* try the next endpoint */
    }
  }
  return null;
}

/**
 * Runtime version-skew check for the long-lived orchestrator session.
 *
 * The launcher guards the version at start time, but the orchestrator session
 * outlives the launch: a sibling project can restart the shared server on a new
 * version mid-session. Cross-version replay determinism is not guaranteed, so an
 * orchestrator that journals fiduciary operations must re-check the live version
 * before it starts a NEW operation — not trust the start-time reading.
 *
 * Returns the status; the caller decides what to do with a mismatch (the
 * orchestrator's gate blocks NEW operations on a definite mismatch). An
 * indeterminate reading (version unreadable) is NOT treated as a mismatch — it
 * does not block — but it is reported so the caller can log it.
 *
 * @param pinned  the pinned version to compare against (defaults to the pin).
 */
export async function checkRuntimeVersionSkew(
  pinned: string = OPENIM_PINNED_RESTATE_VERSION,
  timeoutMs = 1500,
): Promise<VersionSkewStatus> {
  const running = await readRunningServerVersion(timeoutMs);
  if (running === null) {
    return { running: null, pinned, mismatch: false, indeterminate: true };
  }
  return {
    running,
    pinned,
    mismatch: running !== pinned,
    indeterminate: false,
  };
}

/** Register a handler endpoint with the shared Restate admin API. */
export async function registerDeployment(uri: string): Promise<string> {
  const res = await fetch(`${ADMIN_URL}/deployments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uri, force: true }),
  });
  if (!res.ok) {
    throw new Error(`deployment register failed ${res.status}: ${await res.text()}`);
  }
  const body = (await res.json()) as { id?: string };
  if (!body.id) {
    throw new Error(`deployment register: response missing 'id': ${JSON.stringify(body)}`);
  }
  return body.id;
}

/**
 * Deregister a deployment by id (OIM-107, P-R1 fold). A short-lived endpoint
 * (the cross-language smoke, a one-shot CLI proof) must deregister on teardown
 * so the SHARED Restate journal — used by OpenIM + any sibling project + every
 * smoke run —
 * does not accumulate dead-port deployments pointing at endpoints that no longer
 * listen. Best-effort + force: a failed deregister is logged, never fatal (the
 * proof already succeeded; this is hygiene on a shared journal).
 */
export async function deregisterDeployment(id: string): Promise<void> {
  try {
    const res = await fetch(`${ADMIN_URL}/deployments/${encodeURIComponent(id)}?force=true`, {
      method: 'DELETE',
    });
    if (!res.ok && res.status !== 404) {
      process.stderr.write(
        `[restate-reach] deregister ${id} returned ${res.status} (non-fatal): ${await res.text()}\n`,
      );
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(`[restate-reach] deregister ${id} failed (non-fatal): ${msg}\n`);
  }
}

/**
 * Prune deployments whose endpoint URI no longer answers (OIM-107, P-R1 fold).
 * Walks the admin /deployments list, probes each endpoint's `/health` (or its
 * discovery URI), and force-deletes the ones that do not respond — the
 * dead-port-deployment orphans the shared journal accumulates across runs.
 * Best-effort; returns the count pruned. Safe to call on a shared instance: it
 * only removes deployments whose endpoint is genuinely unreachable.
 */
export async function pruneDeadDeployments(probeTimeoutMs = 1500): Promise<number> {
  let pruned = 0;
  let list: { deployments?: { id?: string; uri?: string }[] };
  try {
    const res = await fetch(`${ADMIN_URL}/deployments`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return 0;
    list = (await res.json()) as typeof list;
  } catch {
    return 0;
  }
  for (const dep of list.deployments ?? []) {
    if (!dep.id || !dep.uri) continue;
    let alive: boolean;
    try {
      const r = await fetch(`${dep.uri.replace(/\/$/, '')}/health`, {
        signal: AbortSignal.timeout(probeTimeoutMs),
      });
      alive = r.ok || r.status === 404; // 404 = endpoint up but no /health route
    } catch {
      alive = false;
    }
    if (!alive) {
      await deregisterDeployment(dep.id);
      pruned += 1;
    }
  }
  return pruned;
}
