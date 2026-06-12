#!/usr/bin/env node
/**
 * OpenIM-OWNED Restate launcher (agentINVEST substrate, P-R1 decoupling).
 *
 * Boots the Restate dev server from OpenIM's OWN binaries + config + version
 * pin. A fresh OpenIM checkout brings its substrate up with THIS script and
 * NEVER reads a sibling project's source files — it imports OpenIM's own
 * `install-restate.mjs` and reads OpenIM's own `config/restate-dev.toml`.
 *
 * This discharges the OIM-100 pre-mortem's P-R1 (High/High): the floor used to
 * launch via a sibling project's launcher at a hardcoded absolute checkout path,
 * a source-file dependency OpenIM neither owned nor versioned. Now OpenIM owns
 * the launcher, the installer, the config and the version pin.
 *
 * Dev-time note (ADR-0054): the RUNNING instance may still be shared with a
 * sibling project sharing the dev substrate by
 * default — same pinned binary, same ports, one journal, no second cluster. If
 * the shared instance is already up (a sibling or a prior OpenIM run launched it),
 * this launcher DETECTS it (health-probes the admin API) and REUSES it — it
 * prints a "reusing" line and exits 0, never racing the bind. A genuinely-down
 * start still boots cleanly. This already-running guard (OIM-107, discharging the
 * OIM-100/101 P-R1 launcher bind-race) is what makes a second `pnpm dev:restate`
 * — and OIM-104's orchestrator launching alongside the sibling — idempotent instead
 * of an exit-139/port-collision. The decoupling is about SOURCE-FILE ownership +
 * the version contract; the reuse guard is about not forking the running process.
 *
 * Version-skew guard (P-R4): on detecting an already-running instance, the
 * launcher compares the running server's reported version against OpenIM's OWN
 * pin (RESTATE_VERSION) and warns LOUDLY on a mismatch — so a sibling-bumped
 * shared server is never talked to silently. It warns, it does not abort (the
 * operator decides); set RESTATE_SKEW_FATAL=1 to make a skew a hard exit 1.
 *
 * On Windows the Linux-musl binary runs inside WSL2 (default distro
 * Ubuntu-24.04; override with RESTATE_WSL_DISTRO). On Mac/Linux it runs native.
 */
import { execFileSync, spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { ensureRestate, RESTATE_VERSION } from './install-restate.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// reference/scripts/ -> reference/
const REFERENCE_ROOT = path.resolve(__dirname, '..');

const NODE_NAME = process.env.RESTATE_NODE_NAME ?? 'dev';
const WSL_DISTRO = process.env.RESTATE_WSL_DISTRO ?? 'Ubuntu-24.04';
const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://localhost:9070';

/**
 * Health-probe the shared Restate admin API. Returns true iff it answers 200 —
 * i.e. an instance (a sibling project's, or a prior OpenIM run's) is already up. Used as
 * the already-running guard so a second launch reuses rather than racing the
 * bind (OIM-107). Single short-timeout probe; a 200 is the up signal.
 */
async function adminHealthy(timeoutMs = 1500) {
  try {
    const res = await fetch(`${ADMIN_URL}/health`, { signal: AbortSignal.timeout(timeoutMs) });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Report the running server's version via the admin /version endpoint, or null
 * if it cannot be determined (older server, or the endpoint is absent). Used by
 * the version-skew guard (P-R4) to compare against OpenIM's OWN pin.
 */
async function runningServerVersion(timeoutMs = 1500) {
  for (const p of ['/version', '/health']) {
    try {
      const res = await fetch(`${ADMIN_URL}${p}`, { signal: AbortSignal.timeout(timeoutMs) });
      if (!res.ok) continue;
      const text = await res.text();
      // The admin surface reports the version in a JSON body or a header
      // depending on the server build; parse defensively.
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
 * Version-skew guard (P-R4): warn LOUDLY when the running shared server's
 * version differs from OpenIM's OWN pin, so a sibling-bumped server is never
 * talked to silently. Warns by default; RESTATE_SKEW_FATAL=1 makes it exit 1.
 * Returns true on a detected mismatch.
 */
function reportVersionSkew(running) {
  if (!running) {
    process.stderr.write(
      `[restate-dev] note: could not determine the running server's version ` +
        `(admin /version unavailable); skipping the version-skew check (OpenIM pin v${RESTATE_VERSION}).\n`,
    );
    return false;
  }
  if (running === RESTATE_VERSION) {
    process.stderr.write(
      `[restate-dev] version check OK — running server v${running} matches OpenIM's pin v${RESTATE_VERSION}.\n`,
    );
    return false;
  }
  process.stderr.write(
    `\n[restate-dev] !!! VERSION SKEW !!!\n` +
      `  The already-running shared Restate server reports v${running},\n` +
      `  but OpenIM pins v${RESTATE_VERSION} (scripts/install-restate.mjs).\n` +
      `  A sibling project likely bumped + restarted the shared instance.\n` +
      `  Risk: OpenIM's pinned SDKs talk to a mismatched server. Reconcile the pin,\n` +
      `  or restart the shared instance from OpenIM's binary. Set RESTATE_SKEW_FATAL=1\n` +
      `  to make this a hard failure.\n\n`,
  );
  return true;
}
const CONFIG_FILE =
  process.env.RESTATE_CONFIG_FILE ?? path.join(REFERENCE_ROOT, 'config', 'restate-dev.toml');

const BASE_DIR_DEFAULT =
  process.platform === 'win32' ? '/tmp/restate-dev' : path.join(REFERENCE_ROOT, '.restate-dev');
const BASE_DIR = process.env.RESTATE_BASE_DIR ?? BASE_DIR_DEFAULT;

function toWslPath(winPath) {
  const norm = winPath.replace(/\\/g, '/');
  if (norm.startsWith('//')) {
    throw new Error(
      `UNC path not supported by run-restate-server.mjs: ${winPath}. ` +
        `Check the repo out under a lettered local drive (e.g. C:\\, D:\\) — ` +
        `the runner translates drive-lettered paths into WSL2's /mnt/<letter>/ form.`,
    );
  }
  const m = norm.match(/^([A-Za-z]):(.*)$/);
  if (!m) return norm;
  return `/mnt/${m[1].toLowerCase()}${m[2]}`;
}

function preflightWsl() {
  let listing;
  try {
    // WSL_UTF8=1 forces wsl.exe to emit UTF-8. The historical default is
    // UTF-16LE on Windows, which would corrupt the parse.
    listing = execFileSync('wsl', ['-l', '-q'], {
      encoding: 'utf8',
      env: { ...process.env, WSL_UTF8: '1' },
    });
  } catch (err) {
    process.stderr.write(
      `[restate-dev] wsl.exe not reachable: ${err.message}\n` +
        `  Recover: run 'wsl --install' once (admin PowerShell), then ` +
        `'wsl --install -d ${WSL_DISTRO} --no-launch' to register the distro.\n`,
    );
    process.exit(1);
  }
  const distros = listing
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (!distros.includes(WSL_DISTRO)) {
    process.stderr.write(
      `[restate-dev] WSL2 distro '${WSL_DISTRO}' is not registered.\n` +
        `  Installed: ${distros.length === 0 ? '(none)' : distros.join(', ')}\n` +
        `  Recover: 'wsl --install -d ${WSL_DISTRO} --no-launch' (one-time), or set ` +
        `RESTATE_WSL_DISTRO to an installed distro name.\n`,
    );
    process.exit(1);
  }
}

const binaryWindowsPath = path.join(REFERENCE_ROOT, 'tools', 'restate-server');
const passThrough = process.argv.slice(2);
const binaryArgs = [
  '--node-name',
  NODE_NAME,
  '--base-dir',
  BASE_DIR,
  '--config-file',
  process.platform === 'win32' ? toWslPath(CONFIG_FILE) : CONFIG_FILE,
  ...passThrough,
];

// Already-running guard (OIM-107, P-R1): if the shared Restate is already up
// (a sibling project's, or a prior OpenIM run's), DETECT it and REUSE it — never race the
// bind. This is the idempotency the orchestrator (OIM-104) relies on and the fix
// for the exit-139/port-collision seen in OIM-101/102. Probed FIRST, before the
// WSL preflight + install, so a reuse is cheap (no download, no WSL hop needed).
if (await adminHealthy()) {
  const running = await runningServerVersion();
  const skew = reportVersionSkew(running);
  process.stderr.write(
    `[restate-dev] shared Restate already running at ${ADMIN_URL} — reusing it ` +
      `(no second cluster, no bind-race). Admin: ${ADMIN_URL}.\n`,
  );
  if (skew && process.env.RESTATE_SKEW_FATAL === '1') {
    process.stderr.write(`[restate-dev] RESTATE_SKEW_FATAL=1 set — exiting 1 on the version skew.\n`);
    process.exit(1);
  }
  process.exit(0);
}

// Preflight first on Windows so a missing WSL2 distro fails loud BEFORE the
// install path downloads the binaries — fail-fast on a busted environment.
if (process.platform === 'win32') {
  preflightWsl();
}

try {
  await ensureRestate();
} catch (err) {
  process.stderr.write(`[restate-dev] install failed: ${err.message}\n`);
  process.exit(1);
}

let cmd;
let args;
if (process.platform === 'win32') {
  cmd = 'wsl';
  args = ['-d', WSL_DISTRO, '--', toWslPath(binaryWindowsPath), ...binaryArgs];
} else {
  cmd = binaryWindowsPath;
  args = binaryArgs;
}

process.stderr.write(
  `[restate-dev] launching: ${cmd} ${args.map((a) => (/\s/.test(a) ? JSON.stringify(a) : a)).join(' ')}\n`,
);

const spawnedAt = Date.now();
const child = spawn(cmd, args, { stdio: 'inherit' });

// Human/script-facing readiness signal: poll the admin /health endpoint in the
// background and print ONE line when it first 200s, then stop. The poll never
// writes to stdout (the child owns stdout under `inherit`) and self-terminates
// on the first 200 or when the child exits, so it cannot keep the process alive.
const ADMIN_HEALTH_URL = `${process.env.RESTATE_ADMIN_URL ?? 'http://localhost:9070'}/health`;
let shuttingDown = false;
let readinessAnnounced = false;
const readinessTimer = setInterval(async () => {
  if (readinessAnnounced || shuttingDown) return;
  try {
    const res = await fetch(ADMIN_HEALTH_URL, { signal: AbortSignal.timeout(1500) });
    if (res.ok) {
      readinessAnnounced = true;
      clearInterval(readinessTimer);
      process.stderr.write(`[restate-dev] ready — ${ADMIN_HEALTH_URL} responding\n`);
    }
  } catch {
    // Not up yet; keep polling until the server binds or the child exits.
  }
}, 500);
readinessTimer.unref();

function forward(signal) {
  return () => {
    if (shuttingDown) return;
    shuttingDown = true;
    child.kill(signal);
  };
}
process.on('SIGINT', forward('SIGINT'));
process.on('SIGTERM', forward('SIGTERM'));

child.on('error', (err) => {
  clearInterval(readinessTimer);
  process.stderr.write(`[restate-dev] failed to launch ${cmd}: ${err.message}\n`);
  process.exit(127);
});

child.on('exit', async (code, signal) => {
  clearInterval(readinessTimer);
  if (signal === 'SIGINT' || signal === 'SIGTERM') process.exit(0);

  // TOCTOU close (OIM-107): the already-running guard probed BEFORE the bind, so
  // a sibling could have started the shared instance in the window between the
  // probe and our bind — our child would then exit fast on a port collision
  // (a non-zero code, or SIGSEGV/139 on some builds). If the child died early
  // AND the admin is now healthy, the substrate IS up (a sibling won the race) —
  // treat it as a reuse (exit 0), not a crash. What this guarantees (and all the
  // goal requires): no bind-race, no exit-139, no second cluster, and idempotent
  // reuse for the realistic sequential second-launch (instance already up). It is
  // NOT fully race-free in the simultaneous-cold case: if two launchers both pass
  // the probe and bind at once, the loser's child dies before the winner's admin
  // is /health-200, so the loser falls through to a clean exit 1 (port collision)
  // rather than exit 0. That clean failure is acceptable — it is bounded and
  // never a 139 or a second cluster.
  const diedEarly = Date.now() - spawnedAt < 8000;
  if ((code !== 0 || signal) && diedEarly && (await adminHealthy())) {
    const running = await runningServerVersion();
    reportVersionSkew(running);
    process.stderr.write(
      `[restate-dev] a shared Restate became reachable at ${ADMIN_URL} while we were ` +
        `starting (a sibling won the bind race) — reusing it. No second cluster.\n`,
    );
    process.exit(0);
  }

  if (signal) {
    process.stderr.write(`[restate-dev] child terminated by signal ${signal}\n`);
    process.exit(1);
  }
  process.exit(code ?? 1);
});
