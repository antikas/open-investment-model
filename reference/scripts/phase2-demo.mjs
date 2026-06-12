#!/usr/bin/env node
/**
 * agentINVEST end-to-end analytics demo runner — one command, fresh checkout.
 *
 * Brings the whole analytics stack up from a clean state and runs the multi-step
 * analyst task ("a fund's total return, then a breakdown by sector") across it:
 *
 *   1. Verifies the shared Restate substrate is reachable (boot it first with
 *      OpenIM's OWN launcher: `pnpm dev:restate` from reference/). The launcher
 *      reuses a running shared instance idempotently — it does not disrupt a
 *      sibling sharing the server.
 *   2. Asserts the canonical marts are built (the duckdb store exists); if not,
 *      tells the operator to run `pnpm dbt:build` first. (Pass `--build-data` to
 *      run `dbt build` here as part of the fresh-checkout boot.)
 *   3. Starts the PYTHON endpoint (the `bd09` dispatch service) — on Windows
 *      inside WSL2 via uv (`uv run python -m agentinvest_tools.endpoint`); native
 *      otherwise — and waits for it to register `bd09` against the shared Restate.
 *      Reuse-safe (OIM-184): if a `bd09` endpoint is ALREADY registered (the shared
 *      :9091 carrying bd09/agentinvestPlanner/navData/pyTools), it is REUSED — not
 *      re-spawned — and LEFT REGISTERED on exit. Only an endpoint THIS run spawned is
 *      torn down. Never strip a shared resource (other local projects sharing the dev
 *      substrate + concurrent OpenIM work depend on it). NEVER `wsl --shutdown`.
 *   4. Runs the demo (`python -m agentinvest_demo`), which reads the marts,
 *      dispatches SO-09-01 then SO-09-05 to `bd09` over the substrate, reconciles
 *      the breakdown to the total return, and reports the per-operation latency.
 *      The runner reads the demo's pass/fail outcome from the demo's machine-readable
 *      `PHASE2_DEMO_RESULT:` stdout line, NOT its exit code — `uv run` masks every
 *      non-zero child exit to 0 in this WSL2 launch env, so the exit code is not a
 *      trustworthy success oracle; stdout, which uv cannot eat, is.
 *   5. Deregisters the `bd09` endpoint so the shared journal stays clean — ONLY if
 *      THIS run spawned it (a reused shared endpoint is left registered).
 *
 * The Python side runs inside WSL2 on Windows (the Restate Python SDK + the data
 * toolchain are Linux-native — the ADR-0054 polyglot split), with the uv env +
 * the duckdb store on WSL2-native ext4 (the OIM-110 checkout-keyed paths, via the
 * shared `agentinvest-venv-path.sh` helper). The demo runs under the `dbt` group
 * so duckdb is available to read the marts.
 *
 * Run:  node scripts/phase2-demo.mjs            (from reference/)
 *   or: pnpm demo:phase2
 *   with a data build: pnpm demo:phase2 --build-data
 *   for a chosen fund: pnpm demo:phase2 --fund PF-0002
 */
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REFERENCE_ROOT = path.resolve(__dirname, '..');

const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://localhost:9070';
const isWin = process.platform === 'win32';
const WSL_DISTRO = process.env.RESTATE_WSL_DISTRO ?? 'Ubuntu-24.04';

// Pass-through args after the runner's own flags: --build-data (run dbt build
// first) is consumed here; everything else (e.g. --fund PF-0002, --begin, --end)
// is forwarded to the demo CLI.
const rawArgs = process.argv.slice(2);
const buildData = rawArgs.includes('--build-data');
const demoArgs = rawArgs.filter((a) => a !== '--build-data');

function log(line) {
  process.stderr.write(`[demo:phase2] ${line}\n`);
}

/** The WSL2 path to reference/ (drive-lettered -> /mnt/<letter>/...). */
function wslReferenceRoot() {
  return '/mnt/' + REFERENCE_ROOT[0].toLowerCase() + REFERENCE_ROOT.slice(2).replace(/\\/g, '/');
}

/** The WSL2 path to the repo root (the parent of reference/). */
function wslRepoRoot() {
  const repoRoot = path.resolve(REFERENCE_ROOT, '..');
  return '/mnt/' + repoRoot[0].toLowerCase() + repoRoot.slice(2).replace(/\\/g, '/');
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

/**
 * The shared in-WSL2 prelude: PATH + the checkout-keyed ext4 venv/duckdb env, then cd python/.
 *
 * The repo-root path is passed LITERALLY (computed in JS, not via `$(cd .. && pwd)`) — under a
 * `wsl … bash -lc` invocation a command-substitution can come back empty (a login-shell quirk),
 * which would key the venv/duckdb on an empty string and miss the dbt-built store. The helper is
 * sourced from a CR-stripped copy (it lives on the 9p mount with CRLF endings, which a direct
 * source does not reliably define). Both keep the demo on the SAME checkout-keyed store the
 * `dbt-build` launcher writes — so the runner reads the marts that build populated.
 */
function wslPrelude() {
  const wslRef = wslReferenceRoot();
  const repo = wslRepoRoot();
  return (
    `export PATH="$HOME/.local/bin:$PATH"; ` +
    `tr -d '\\r' < ${wslRef}/scripts/lib/agentinvest-venv-path.sh > /tmp/agentinvest-venv-path.sh; ` +
    `. /tmp/agentinvest-venv-path.sh; ` +
    `agentinvest_set_venv_env '${repo}'; ` +
    `agentinvest_set_duckdb_env '${repo}'; ` +
    `cd ${wslRef}/python`
  );
}

/** The native (Mac/Linux) prelude — same keying, repo root passed literally. */
function nativePrelude() {
  const repo = path.resolve(REFERENCE_ROOT, '..');
  return (
    `export PATH="$HOME/.local/bin:$PATH"; ` +
    `. ${REFERENCE_ROOT}/scripts/lib/agentinvest-venv-path.sh; ` +
    `agentinvest_set_venv_env '${repo}'; ` +
    `agentinvest_set_duckdb_env '${repo}'; ` +
    `cd ${REFERENCE_ROOT}/python`
  );
}

/** Run `dbt build` (the marts) once, synchronously, from a clean state. */
function buildMarts() {
  log('building the canonical marts (dbt build)...');
  const r = spawnSync('node', [path.join('scripts', 'dbt-build.mjs')], {
    cwd: REFERENCE_ROOT,
    stdio: 'inherit',
  });
  if (r.status !== 0) {
    log('dbt build failed; cannot run the demo without the canonical marts.');
    process.exit(r.status ?? 1);
  }
}

function startBd09Endpoint() {
  let cmd;
  let args;
  if (isWin) {
    cmd = 'wsl';
    args = [
      '-d',
      WSL_DISTRO,
      '--',
      'bash',
      '-lc',
      `${wslPrelude()} && uv run --group dbt python -m agentinvest_tools.endpoint`,
    ];
  } else {
    cmd = 'bash';
    args = ['-lc', `${nativePrelude()} && uv run --group dbt python -m agentinvest_tools.endpoint`];
  }
  log(`starting the bd09 endpoint: ${cmd} ${isWin ? args.slice(0, 4).join(' ') + ' …' : '…'}`);
  return spawn(cmd, args, { stdio: 'inherit', env: { ...process.env, WSL_UTF8: '1' } });
}

async function awaitBd09Registered(timeoutSeconds = 60) {
  const deadline = Date.now() + timeoutSeconds * 1000;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${ADMIN_URL}/services/bd09/openapi`, {
        signal: AbortSignal.timeout(3000),
      });
      if (r.ok) return true;
    } catch {
      /* retry */
    }
    await new Promise((res) => setTimeout(res, 1500));
  }
  return false;
}

// The demo's machine-readable result line (phase2_demo.RESULT_SENTINEL_PREFIX). The demo prints
// it on its final stdout line on EVERY exit path: `PHASE2_DEMO_RESULT: PASS rc=0` on a clean pass,
// `PHASE2_DEMO_RESULT: FAIL rc=N` on any failure. The runner reads the outcome from THIS line, not
// from the process exit code — because in this WSL2 launch environment `uv run` masks every
// non-zero child exit to 0, so the demo's own `SystemExit(rc)` is invisible to the wsl/node layer
// (it cannot, however, eat stdout). Parsing the sentinel makes the fresh-checkout green
// load-bearing again. The demo keeps its `SystemExit(rc)` intact for direct invocation + the
// integration test; this line is the additive runner channel.
const DEMO_RESULT_SENTINEL = /^PHASE2_DEMO_RESULT:\s+(PASS|FAIL)\s+rc=(-?\d+)/;

/**
 * Parse the demo's outcome from its sentinel line. Returns the rc the sentinel carries
 * (0 on PASS, the demo's non-zero rc on FAIL), or null if no sentinel line was seen — a missing
 * sentinel means the demo did not reach any of its exit paths (it crashed before emitting, or the
 * stream was lost), which MUST be treated as a failure, never silently greened.
 */
function parseDemoSentinel(stdout) {
  let outcome = null;
  for (const line of stdout.split(/\r?\n/)) {
    const m = DEMO_RESULT_SENTINEL.exec(line.trim());
    if (m) outcome = { result: m[1], rc: Number.parseInt(m[2], 10) };
  }
  if (!outcome) return null;
  // Trust the textual PASS/FAIL as the primary signal; rc is the demo's own code.
  return outcome.result === 'PASS' ? 0 : outcome.rc || 1;
}

function runDemo() {
  return new Promise((resolve) => {
    let cmd;
    let args;
    if (isWin) {
      cmd = 'wsl';
      args = [
        '-d',
        WSL_DISTRO,
        '--',
        'bash',
        '-lc',
        `${wslPrelude()} && uv run --group dbt python -m agentinvest_demo ${demoArgs.join(' ')}`,
      ];
    } else {
      cmd = 'bash';
      args = [
        '-lc',
        `${nativePrelude()} && uv run --group dbt python -m agentinvest_demo ${demoArgs.join(' ')}`,
      ];
    }
    // Pipe stdout so the runner can parse the demo's result sentinel (the exit code is masked by
    // `uv run`), while still streaming the demo's human output to the console (tee). stderr stays
    // inherited (the demo's failure messages flow straight to the operator).
    const child = spawn(cmd, args, {
      stdio: ['inherit', 'pipe', 'inherit'],
      env: { ...process.env, WSL_UTF8: '1' },
    });
    let stdout = '';
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      stdout += chunk;
      process.stdout.write(chunk); // tee to the console — the human still sees the full demo output
    });
    child.on('exit', (code, signal) => {
      const sentinelRc = parseDemoSentinel(stdout);
      if (sentinelRc !== null) {
        // The demo reached an exit path and told us its outcome — trust the sentinel.
        resolve(sentinelRc);
        return;
      }
      // No sentinel: the demo did not complete an exit path (crashed before emitting / stream
      // lost). Do NOT green it — fall back to a non-zero signal. (The masked `uv run` exit code is
      // not trustworthy here, so a missing sentinel is treated as failure regardless of `code`.)
      log(
        'WARNING: the demo did not emit a result sentinel — treating as a failure ' +
          '(the demo did not complete an exit path).',
      );
      resolve(signal ? `signal:${signal}` : 1);
    });
    child.on('error', () => resolve(1));
  });
}

/** Deregister the bd09 deployment so the SHARED journal does not keep a dead-port orphan. */
async function deregisterBd09() {
  try {
    const r = await fetch(`${ADMIN_URL}/deployments`, { signal: AbortSignal.timeout(4000) });
    if (!r.ok) return;
    const body = await r.json();
    for (const dep of body.deployments ?? []) {
      if ((dep.services ?? []).some((s) => s.name === 'bd09') && dep.id) {
        log(`deregistering bd09 deployment ${dep.id}`);
        await fetch(`${ADMIN_URL}/deployments/${encodeURIComponent(dep.id)}?force=true`, {
          method: 'DELETE',
          signal: AbortSignal.timeout(4000),
        }).catch(() => {});
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
      `Restate admin at ${ADMIN_URL} not reachable. Boot the substrate first: ` +
        `(cd ${REFERENCE_ROOT} && pnpm dev:restate).`,
    );
    process.exit(1);
  }
  log('substrate reachable.');

  if (buildData) buildMarts();

  // Reuse the running shared bd09 if it is already registered (the shared :9091 —
  // carrying bd09/agentinvestPlanner/navData/pyTools); only spawn our own if not
  // (OIM-184 reuse-safety). pySpawnedByUs gates ALL Python-side teardown: a reused
  // shared endpoint is NEVER killed or deregistered (other local projects sharing the
  // dev substrate + concurrent OpenIM work depend on it). NEVER `wsl --shutdown`.
  let py = null;
  let pySpawnedByUs = false;
  if (await awaitBd09Registered(2)) {
    log('bd09 already registered — reusing the running shared Python endpoint (no spawn). LEFT REGISTERED on exit.');
  } else {
    py = startBd09Endpoint();
    pySpawnedByUs = true;
  }
  let exitCode = 1;
  try {
    if (!(await awaitBd09Registered(60))) {
      log('bd09 did not register within the timeout; aborting the demo.');
      exitCode = 1;
    } else {
      log('bd09 registered; running the end-to-end demo.');
      const result = await runDemo();
      exitCode = typeof result === 'number' ? result : 1;
    }
  } finally {
    if (pySpawnedByUs) {
      log('stopping the bd09 endpoint (THIS run spawned it)...');
      py.kill('SIGTERM');
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
      await deregisterBd09();
    } else {
      log('reused the shared Python endpoint — leaving bd09/agentinvestPlanner/navData/pyTools registered on exit (not stripping a shared resource).');
    }
  }
  process.exit(exitCode);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  process.exit(1);
});
