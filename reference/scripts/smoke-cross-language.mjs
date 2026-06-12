#!/usr/bin/env node
/**
 * Cross-language RPC smoke orchestrator (OIM-101) — one command, fresh checkout.
 *
 * Brings up everything the TS↔Python typed-RPC proof needs, in order, then runs
 * the proof and tears down:
 *
 *   1. Verifies the shared Restate substrate is reachable (boot it first with
 *      OpenIM's OWN launcher: `pnpm dev:restate` from reference/ — P-R1).
 *   2. Starts the PYTHON endpoint (pyTools) — on Windows, inside WSL2 via uv
 *      (`uv run python -m agentinvest_tools.endpoint`); native otherwise. It
 *      registers itself against the shared Restate on its own port (9091).
 *      Reuse-safe (OIM-184): if a `pyTools` endpoint is ALREADY registered (the
 *      shared :9091 carrying bd09/agentinvestPlanner/navData/pyTools), it is REUSED —
 *      not re-spawned — and LEFT REGISTERED on exit. Only an endpoint THIS run
 *      spawned is torn down. Never strip a shared resource (other local projects
 *      sharing the dev substrate + concurrent OpenIM work depend on it). NEVER
 *      `wsl --shutdown`.
 *   3. Runs the TS cross-language smoke (`tsx src/rpc/cross-language-smoke.ts`),
 *      which stands up the TS orchestrator endpoint, registers it, and invokes
 *      a handler that calls the Python pyTools service over Restate typed RPC.
 *   4. Asserts the round-trip crossed the boundary, then stops the Python endpoint —
 *      ONLY if THIS run spawned it (a reused shared endpoint is left registered).
 *
 * This is the documented run command the audit replays. The Python endpoint runs
 * inside WSL2 because the Restate Python SDK is Linux-native (no Windows wheel);
 * that placement is the ADR-0054 polyglot split, not a workaround.
 *
 * Run:  node scripts/smoke-cross-language.mjs   (from reference/)
 *   or: pnpm smoke:cross-language
 */
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REFERENCE_ROOT = path.resolve(__dirname, '..');
const TS_DIR = path.join(REFERENCE_ROOT, 'ts');

const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://localhost:9070';
const isWin = process.platform === 'win32';
const WSL_DISTRO = process.env.RESTATE_WSL_DISTRO ?? 'Ubuntu-24.04';

function log(line) {
  process.stderr.write(`[smoke-cross-language] ${line}\n`);
}

async function awaitAdmin(timeoutSeconds = 20) {
  const deadline = Date.now() + timeoutSeconds * 1000;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${ADMIN_URL}/health`, { signal: AbortSignal.timeout(2000) });
      if (r.ok) return true;
    } catch {
      /* retry */
    }
    await new Promise((res) => setTimeout(res, 500));
  }
  return false;
}

function startPythonEndpoint() {
  // On Windows the Python endpoint runs inside WSL2 (Linux-native SDK). The
  // Python SOURCE lives on the 9p mount (/mnt/d/...); the uv ENVIRONMENT lands on
  // WSL2-native ext4 (UV_PROJECT_ENVIRONMENT, OIM-107) — the same split the dbt
  // launcher uses, so the cold import is fast (ext4) and the source stays in-repo.
  const wslPythonDir = '/mnt/' + REFERENCE_ROOT[0].toLowerCase() + REFERENCE_ROOT.slice(2).replace(/\\/g, '/') + '/python';
  const nativePythonDir = path.join(REFERENCE_ROOT, 'python');
  let cmd;
  let args;
  // Pin uv's project dir explicitly (--directory <reference/python>) on BOTH
  // branches — not just the cwd — so a glitched invocation can NEVER fall back to
  // the repo-root cwd and write a stray pyproject.toml/uv.lock there (OIM-107
  // leak-guard, root cause).
  if (isWin) {
    cmd = 'wsl';
    args = [
      '-d',
      WSL_DISTRO,
      '--',
      'bash',
      '-lc',
      `export PATH="$HOME/.local/bin:$PATH"; ` +
        // Checkout-keyed ext4 venv (OIM-110, P-MAJOR-2 fix) via the SSOT helper —
        // same placement/perf as dbt-build.sh, but keyed on this checkout so a
        // concurrent checkout / CI run does not share one venv. An explicit
        // UV_PROJECT_ENVIRONMENT still wins.
        `. ${wslPythonDir}/../scripts/lib/agentinvest-venv-path.sh; ` +
        `agentinvest_set_venv_env "$(cd ${wslPythonDir}/../.. && pwd)"; ` +
        `cd ${wslPythonDir} && uv run --directory ${wslPythonDir} python -m agentinvest_tools.endpoint`,
    ];
  } else {
    cmd = 'uv';
    args = ['run', '--directory', nativePythonDir, 'python', '-m', 'agentinvest_tools.endpoint'];
  }
  log(`starting Python endpoint: ${cmd} ${args.join(' ')}`);
  const child = spawn(cmd, args, {
    cwd: isWin ? undefined : path.join(REFERENCE_ROOT, 'python'),
    stdio: 'inherit',
    env: { ...process.env, WSL_UTF8: '1' },
  });
  return child;
}

async function awaitPyToolsRegistered(timeoutSeconds = 45) {
  const deadline = Date.now() + timeoutSeconds * 1000;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${ADMIN_URL}/deployments`, { signal: AbortSignal.timeout(3000) });
      if (r.ok) {
        const body = await r.json();
        const found = (body.deployments ?? []).some((dep) =>
          (dep.services ?? []).some((s) => s.name === 'pyTools'),
        );
        if (found) return true;
      }
    } catch {
      /* retry */
    }
    await new Promise((res) => setTimeout(res, 1500));
  }
  return false;
}

function runTsSmoke() {
  return new Promise((resolve) => {
    const child = spawn('npx', ['tsx', 'src/rpc/cross-language-smoke.ts'], {
      cwd: TS_DIR,
      stdio: 'inherit',
      shell: isWin,
    });
    child.on('exit', (code, signal) => resolve(signal ? `signal:${signal}` : (code ?? 1)));
    child.on('error', () => resolve(1));
  });
}

/**
 * Run the TS smoke with a cold-start warm-up/retry (OIM-107, F-1). OIM-101 saw a
 * one-shot cold-start exit 139 (SIGSEGV) on the very first run after a cold
 * WSL2/uv/tsx cache, with back-to-back runs 2–7 clean — i.e. a transient cold
 * fault, not a logic defect. A cold CI run would spuriously fail on it. So: if
 * the first attempt dies by signal (139/SIGSEGV) or with a non-zero code, warm
 * up briefly and retry once. A clean exit 0 returns immediately. A second
 * failure is a real failure and is returned.
 */
async function runTsSmokeWithRetry(attempts = 2) {
  for (let i = 1; i <= attempts; i += 1) {
    const result = await runTsSmoke();
    if (result === 0) return 0;
    if (i < attempts) {
      log(
        `TS smoke attempt ${i} did not pass (${result}); cold-start transient suspected ` +
          `(OIM-101 F-1). Warming up and retrying once...`,
      );
      await new Promise((res) => setTimeout(res, 2000));
    } else {
      log(`TS smoke failed after ${attempts} attempts (last: ${result}).`);
      return typeof result === 'number' ? result : 139;
    }
  }
  return 1;
}

/** Deregister a deployment by id from the shared admin journal (best-effort). */
async function deregister(id) {
  try {
    const r = await fetch(`${ADMIN_URL}/deployments/${encodeURIComponent(id)}?force=true`, {
      method: 'DELETE',
      signal: AbortSignal.timeout(4000),
    });
    if (!r.ok && r.status !== 404) log(`deregister ${id} -> ${r.status} (non-fatal)`);
  } catch {
    /* best-effort */
  }
}

/** Find + deregister the pyTools deployment so the shared journal stays clean (OIM-107). */
async function deregisterPyTools() {
  try {
    const r = await fetch(`${ADMIN_URL}/deployments`, { signal: AbortSignal.timeout(4000) });
    if (!r.ok) return;
    const body = await r.json();
    for (const dep of body.deployments ?? []) {
      if ((dep.services ?? []).some((s) => s.name === 'pyTools') && dep.id) {
        log(`deregistering pyTools deployment ${dep.id}`);
        await deregister(dep.id);
      }
    }
  } catch {
    /* best-effort */
  }
}

async function main() {
  log('verifying the shared Restate substrate is reachable...');
  if (!(await awaitAdmin())) {
    log(
      `Restate admin at ${ADMIN_URL} not reachable. Boot the substrate with OpenIM's OWN ` +
        `launcher first: (cd ${REFERENCE_ROOT} && pnpm dev:restate).`,
    );
    process.exit(1);
  }
  log('substrate reachable.');

  // Reuse the running shared pyTools if it is already registered (the shared :9091 —
  // carrying bd09/agentinvestPlanner/navData/pyTools); only spawn our own if not
  // (OIM-184 reuse-safety). pySpawnedByUs gates ALL Python-side teardown: a reused
  // shared endpoint is NEVER killed or deregistered (other local projects sharing the
  // dev substrate + concurrent OpenIM work depend on it). NEVER `wsl --shutdown`.
  let py = null;
  let pySpawnedByUs = false;
  if (await awaitPyToolsRegistered(2)) {
    log('pyTools already registered — reusing the running shared Python endpoint (no spawn). LEFT REGISTERED on exit.');
  } else {
    py = startPythonEndpoint();
    pySpawnedByUs = true;
  }
  let exitCode = 1;
  try {
    // Poll for the pyTools deployment to appear, rather than a fixed sleep —
    // the Python endpoint cold-starts (uv), binds, self-registers, and Restate
    // discovers it; that can take several seconds on a cold WSL2/uv cache.
    if (!(await awaitPyToolsRegistered(45))) {
      log('pyTools did not register within the timeout; aborting the smoke.');
      exitCode = 1;
    } else {
      log('pyTools registered; running the TS cross-language smoke.');
      exitCode = await runTsSmokeWithRetry();
    }
  } finally {
    if (pySpawnedByUs) {
      log('stopping the Python endpoint (THIS run spawned it)...');
      py.kill('SIGTERM');
      // On Windows, also stop the in-WSL2 server process group.
      if (isWin) {
        try {
          spawn('wsl', ['-d', WSL_DISTRO, '--', 'pkill', '-f', 'agentinvest_tools.endpoint'], {
            stdio: 'ignore',
            env: { ...process.env, WSL_UTF8: '1' },
          });
        } catch {
          /* best-effort */
        }
      }
      // Deregister the pyTools deployment so the SHARED journal does not accumulate
      // a dead-port orphan after the endpoint is gone (OIM-107). The TS orchestrator
      // smoke deregisters itself in its own finally.
      await deregisterPyTools();
    } else {
      log('reused the shared Python endpoint — leaving bd09/agentinvestPlanner/navData/pyTools registered on exit (not stripping a shared resource). The TS orchestrator smoke deregisters its OWN endpoint in its finally.');
    }
  }
  process.exit(exitCode);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  process.exit(1);
});
