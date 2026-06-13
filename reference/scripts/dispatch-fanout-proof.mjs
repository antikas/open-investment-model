#!/usr/bin/env node
/**
 * PRODUCTION-VO PARALLEL FAN-OUT latency proof for the DISPATCH step (seam 2).
 *
 * Proves intra-handler outbound fan-out: one handler making N parallel
 * `ctx.serviceClient` calls — on the REAL `investmentOperation` VO, not a probe.
 *
 * What it proves: dispatching N independent plan steps to `bd09.execute_so` from one
 * handler IN PARALLEL (the production `Promise.allSettled` fan-out) completes in
 * ~max(step) not ~sum(step) — a MEASURED latency improvement vs a serial baseline of
 * the SAME N execute_so RPCs (apples-to-apples, both over the real substrate).
 *
 * Mechanism:
 *   1. Start the PYTHON endpoint (binds bd09 + agentinvestPlanner); wait for bd09 to
 *      register. (The proofs feed a deterministic fixture plan, so the planner is
 *      not called — but the Python endpoint hosts bd09, the dispatch target.)
 *   2. Build a deterministic fixture plan of N independent, VALID SO-09-01 steps
 *      (begin/end NAV + period — the bd09 happy path; no LLM).
 *   3. Start a SERIAL TS endpoint (AGENTINVEST_DISPATCH_SERIAL set) + a PARALLEL TS
 *      endpoint (unset), each binding the REAL investmentOperation, each fed the
 *      same fixture plan.
 *   4. Invoke investmentOperation/<key>/execute on each; time the wall-clock of the
 *      whole operation (dominated by the N dispatched execute_so RPCs).
 *   5. Assert: both return status=completed with N fulfilled stepResults; the
 *      PARALLEL wall-clock is materially LESS than the SERIAL wall-clock (the
 *      fan-out win). The gate is parallel < serial * SPEEDUP_BAR (default 0.7) AND
 *      an absolute floor, so a sub-noise run does not green spuriously.
 *
 * Run (from reference/, substrate up via `pnpm dev:restate`):
 *   node scripts/dispatch-fanout-proof.mjs   (or: pnpm dispatch-fanout)
 */
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REFERENCE_ROOT = path.resolve(__dirname, '..');
const TS_DIR = path.join(REFERENCE_ROOT, 'ts');

const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://localhost:9070';
const INGRESS_URL = process.env.RESTATE_INGRESS_URL ?? 'http://localhost:8080';
const isWin = process.platform === 'win32';
const WSL_DISTRO = process.env.RESTATE_WSL_DISTRO ?? 'Ubuntu-24.04';

// N=16: large enough that the dispatched-RPC component dominates the fixed VO
// overhead (the version-skew gate + the plan journaling + the round-trip), so the
// parallel ~max(step) vs serial ~sum(step) gap is unambiguous and not flaky. (At
// N=8 the speedup is real but ~1.3x — too close to the fixed-overhead floor to bar
// reliably; at N=16 it is ~1.8x, comfortably clear.)
const N_STEPS = Number(process.env.DISPATCH_FANOUT_N ?? 16);
const SPEEDUP_BAR = Number(process.env.DISPATCH_FANOUT_SPEEDUP_BAR ?? 0.7);
const ABS_MARGIN_MS = Number(process.env.DISPATCH_FANOUT_ABS_MARGIN_MS ?? 50);

const SERIAL_PORT = process.env.DISPATCH_SERIAL_PORT ?? '9097';
const PARALLEL_PORT = process.env.DISPATCH_PARALLEL_PORT ?? '9098';

const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-dispatch-fanout-'));

function log(line) {
  process.stderr.write(`[dispatch-fanout] ${line}\n`);
}

function toWsl(p) {
  return '/mnt/' + p[0].toLowerCase() + p.slice(2).replace(/\\/g, '/');
}

function wslPrelude() {
  const wslRef = toWsl(REFERENCE_ROOT);
  const repo = toWsl(path.resolve(REFERENCE_ROOT, '..'));
  return (
    `export PATH="$HOME/.local/bin:$PATH"; ` +
    `tr -d '\\r' < ${wslRef}/scripts/lib/agentinvest-venv-path.sh > /tmp/agentinvest-venv-path.sh; ` +
    `. /tmp/agentinvest-venv-path.sh; ` +
    `agentinvest_set_venv_env '${repo}'; ` +
    `cd ${wslRef}/python`
  );
}

/** A deterministic fixture plan of N independent, VALID SO-09-01 steps (no LLM). */
function buildFixturePlan(n) {
  const steps = [];
  for (let i = 0; i < n; i++) {
    steps.push({
      soId: 'SO-09-01',
      args: {
        beginning_value: String(1_000_000 + i),
        ending_value: String(1_050_000 + i),
        period_days: 90,
        cash_flows: [],
      },
      rationale: `fixture step ${i}`,
    });
  }
  return { steps, riskScore: 0.05, summary: `dispatch fan-out fixture (${n} independent steps)` };
}

function startPyEndpoint() {
  const env = { ...process.env, WSL_UTF8: '1' };
  let cmd;
  let args;
  if (isWin) {
    cmd = 'wsl';
    args = ['-d', WSL_DISTRO, '--', 'bash', '-lc', `${wslPrelude()} && uv run python -m agentinvest_tools.endpoint`];
  } else {
    cmd = 'bash';
    args = ['-lc', `export PATH="$HOME/.local/bin:$PATH" && cd ${REFERENCE_ROOT}/python && uv run python -m agentinvest_tools.endpoint`];
  }
  log('starting the PYTHON endpoint (bd09 + agentinvestPlanner)...');
  return spawn(cmd, args, { stdio: 'inherit', env });
}

async function awaitServiceRegistered(service, timeoutSeconds = 90) {
  const deadline = Date.now() + timeoutSeconds * 1000;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${ADMIN_URL}/services/${service}/openapi`, { signal: AbortSignal.timeout(3000) });
      if (r.ok) return true;
    } catch {
      /* retry */
    }
    await new Promise((res) => setTimeout(res, 1500));
  }
  return false;
}

function startTsEndpoint({ port, readyFile, serial, fixturePlan }) {
  const entry = path.join(TS_DIR, 'src', 'orchestrator', 'dispatch-proof-endpoint.ts');
  const env = {
    ...process.env,
    AGENTINVEST_DISPATCH_PROOF_PORT: String(port),
    DISPATCH_PROOF_READY_FILE: readyFile,
    AGENTINVEST_DISPATCH_FIXTURE_PLAN: JSON.stringify(fixturePlan),
  };
  if (serial) env.AGENTINVEST_DISPATCH_SERIAL = '1';
  const child = spawn(process.execPath, ['--import', 'tsx', entry], {
    cwd: TS_DIR,
    stdio: ['ignore', 'inherit', 'inherit'],
    env,
  });
  return child;
}

async function waitFor(predicate, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return true;
    await new Promise((res) => setTimeout(res, 200));
  }
  throw new Error(`timed out waiting for: ${label}`);
}

async function timedExecute(key, fixturePlan) {
  const started = Date.now();
  const res = await fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: 'dispatch-fanout-proof', params: { task: fixturePlan.summary } }),
    signal: AbortSignal.timeout(120_000),
  });
  const elapsedMs = Date.now() - started;
  if (!res.ok) throw new Error(`execute failed ${res.status}: ${await res.text()}`);
  return { result: await res.json(), elapsedMs };
}

async function adminHealthy() {
  try {
    const r = await fetch(`${ADMIN_URL}/health`, { signal: AbortSignal.timeout(2000) });
    return r.ok;
  } catch {
    return false;
  }
}

async function pruneDeployments(serviceName, port) {
  try {
    const r = await fetch(`${ADMIN_URL}/deployments`, { signal: AbortSignal.timeout(4000) });
    if (!r.ok) return;
    const body = await r.json();
    for (const dep of body.deployments ?? []) {
      const isOurs =
        (dep.services ?? []).some((s) => s.name === serviceName) &&
        typeof dep.uri === 'string' &&
        dep.uri.includes(`:${port}`);
      if (isOurs && dep.id) {
        await fetch(`${ADMIN_URL}/deployments/${encodeURIComponent(dep.id)}?force=true`, {
          method: 'DELETE',
          signal: AbortSignal.timeout(4000),
        }).catch(() => undefined);
        log(`pruned dispatch-proof ${serviceName} deployment ${dep.id} (${dep.uri})`);
      }
    }
  } catch {
    /* best-effort */
  }
}

let pyChild = null;
// Did THIS run spawn the shared Python endpoint (bd09/agentinvestPlanner/pyTools on
// :9091)? Only true if we started it; false on reuse. The TS proof endpoints are
// always this-run-spawned (always killed); the shared Python endpoint is killed ONLY
// if we spawned it — reusing then killing it would strip the shared deployment that
// other local projects sharing the dev substrate + concurrent OpenIM work depend on.
let pySpawnedByUs = false;
let serialChild = null;
let parallelChild = null;

function killAll() {
  for (const c of [serialChild, parallelChild]) {
    try {
      if (c) c.kill('SIGKILL');
    } catch {
      /* best-effort */
    }
  }
  // Kill the Python endpoint ONLY if THIS run spawned it; never a reused shared one.
  if (pySpawnedByUs) {
    try {
      if (pyChild) pyChild.kill('SIGKILL');
    } catch {
      /* best-effort */
    }
  }
}

async function main() {
  log(`work dir ${work}; N=${N_STEPS} steps; speedup bar parallel < serial*${SPEEDUP_BAR} (abs margin ${ABS_MARGIN_MS}ms)`);
  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: (cd ${REFERENCE_ROOT} && pnpm dev:restate).`);
    process.exit(1);
  }

  const fixturePlan = buildFixturePlan(N_STEPS);

  // ── 1. Python endpoint up (bd09 — the dispatch target) ───────────────────
  // Reuse the running bd09 if already registered (shared :9091); only spawn if not.
  if (await awaitServiceRegistered('bd09', 2)) {
    log('bd09 already registered — reusing the running Python endpoint (no spawn). It will be LEFT INTACT on exit.');
  } else {
    pyChild = startPyEndpoint();
    pySpawnedByUs = true;
    if (!(await awaitServiceRegistered('bd09'))) {
      log('bd09 did not register within the timeout. Aborting.');
      killAll();
      process.exit(1);
    }
    log('bd09 registered (dispatch target reachable).');
  }

  // ── 2. the SERIAL endpoint + the PARALLEL endpoint (both the REAL VO) ─────
  const serialReady = path.join(work, 'serial-ready');
  const parallelReady = path.join(work, 'parallel-ready');
  log('starting the SERIAL dispatch-proof endpoint (AGENTINVEST_DISPATCH_SERIAL set)...');
  serialChild = startTsEndpoint({ port: SERIAL_PORT, readyFile: serialReady, serial: true, fixturePlan });
  await waitFor(() => existsSync(serialReady), 60_000, 'serial endpoint ready');
  const serialPid = readFileSync(serialReady, 'utf8').trim();
  log(`serial endpoint ready (pid ${serialPid}); registered on :${SERIAL_PORT}.`);

  // Warm bd09 (cold-path import/registration) on the serial endpoint BEFORE timing,
  // so neither timed run pays the one-off cold cost (the fan-out win is a steady-
  // state property, the same warm-vs-cold discipline as phase2-demo).
  log('warming bd09 (one untimed execute) so the timed runs are steady-state...');
  await timedExecute(`fanout-warm-${Date.now()}`, fixturePlan);

  // ── 3. time the SERIAL baseline (N execute_so RPCs, one at a time) ────────
  const serialKey = `fanout-serial-${Date.now()}`;
  const serial = await timedExecute(serialKey, fixturePlan);
  log(
    `SERIAL: ${serial.elapsedMs}ms — ${serial.result.fulfilledCount}/${serial.result.stepResults.length} fulfilled ` +
      `(N=${N_STEPS} execute_so RPCs awaited one at a time).`,
  );

  // bring up the PARALLEL endpoint
  log('starting the PARALLEL dispatch-proof endpoint (AGENTINVEST_DISPATCH_SERIAL unset — the production fan-out)...');
  parallelChild = startTsEndpoint({ port: PARALLEL_PORT, readyFile: parallelReady, serial: false, fixturePlan });
  await waitFor(() => existsSync(parallelReady), 60_000, 'parallel endpoint ready');
  const parallelPid = readFileSync(parallelReady, 'utf8').trim();
  log(`parallel endpoint ready (pid ${parallelPid}); registered on :${PARALLEL_PORT}.`);
  await new Promise((res) => setTimeout(res, 1000));

  // ── 4. time the PARALLEL fan-out (same N RPCs, Promise.allSettled) ────────
  const parallelKey = `fanout-parallel-${Date.now()}`;
  const parallel = await timedExecute(parallelKey, fixturePlan);
  log(
    `PARALLEL: ${parallel.elapsedMs}ms — ${parallel.result.fulfilledCount}/${parallel.result.stepResults.length} fulfilled ` +
      `(N=${N_STEPS} execute_so RPCs via Promise.allSettled).`,
  );

  // ── 5. assert the fan-out win ────────────────────────────────────────────
  const bothCompleted =
    serial.result.status === 'completed' &&
    parallel.result.status === 'completed' &&
    serial.result.fulfilledCount === N_STEPS &&
    parallel.result.fulfilledCount === N_STEPS;
  const speedup = serial.elapsedMs / Math.max(parallel.elapsedMs, 1);
  const fastEnough =
    parallel.elapsedMs < serial.elapsedMs * SPEEDUP_BAR &&
    serial.elapsedMs - parallel.elapsedMs >= ABS_MARGIN_MS;

  log('');
  log('RESULT:');
  log(`  N independent steps:   ${N_STEPS}`);
  log(`  SERIAL wall-clock:     ${serial.elapsedMs}ms`);
  log(`  PARALLEL wall-clock:   ${parallel.elapsedMs}ms`);
  log(`  speedup (serial/par):  ${speedup.toFixed(2)}x  (bar: parallel < serial*${SPEEDUP_BAR} AND >=${ABS_MARGIN_MS}ms faster)`);
  log(`  both completed N/N:    ${bothCompleted}`);

  killAll();
  await new Promise((res) => setTimeout(res, 800));
  await pruneDeployments('investmentOperation', SERIAL_PORT);
  await pruneDeployments('investmentOperation', PARALLEL_PORT);
  rmSync(work, { recursive: true, force: true });

  const ok = bothCompleted && fastEnough;
  log('');
  if (ok) {
    log('PRODUCTION-VO PARALLEL FAN-OUT PROVEN:');
    log(`  - the REAL investmentOperation dispatched ${N_STEPS} independent steps to bd09.execute_so from one handler`);
    log('  - the parallel Promise.allSettled fan-out completed in ~max(step), the serial baseline in ~sum(step)');
    log(`  - measured latency improvement: ${serial.elapsedMs}ms serial -> ${parallel.elapsedMs}ms parallel (${speedup.toFixed(2)}x)`);
    process.exit(0);
  }
  log(
    `FAILED: bothCompleted=${bothCompleted} fastEnough=${fastEnough} ` +
      `(serial=${serial.elapsedMs}ms parallel=${parallel.elapsedMs}ms speedup=${speedup.toFixed(2)}x)`,
  );
  process.exit(1);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  killAll();
  try {
    rmSync(work, { recursive: true, force: true });
  } catch {
    /* best-effort */
  }
  process.exit(1);
});
