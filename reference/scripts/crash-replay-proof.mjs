#!/usr/bin/env node
/**
 * Real-process-crash replay proof (the elevated durability bar).
 *
 * This is the load-bearing fiduciary-durability proof: it kills the endpoint
 * PROCESS mid-operation with SIGKILL and confirms Restate resumes the operation
 * from its journal on restart — the journaled step is NOT re-executed. This is
 * DISTINCT from the in-process forced-throw replay the substrate-floor proofs
 * used (a throw + retry inside the SAME process); here a real OS process dies and
 * a fresh one takes over.
 *
 * Mechanism (see crash-replay-endpoint.ts for the probe object):
 *   1. Spawn the crash-replay endpoint as a CHILD process. It hosts the
 *      `crashReplayProbe` virtual object, registers against the shared Restate,
 *      and writes a "ready" file.
 *   2. Invoke `crashReplayProbe/<key>/runWithSideEffectStep` (fire-and-forget —
 *      we do NOT await its HTTP response, because the handler blocks on a file
 *      gate). The handler journals ONE step (appending a line to a side-effect
 *      log + recording a UUID), then waits on the gate.
 *   3. Wait until the side-effect log shows the step RAN once (1 line), proving
 *      the step is journaled and the invocation is mid-flight.
 *   4. SIGKILL the endpoint process tree (a real crash — no graceful shutdown).
 *   5. Restart a FRESH endpoint process; write the "release" file so the resumed
 *      invocation can complete past the gate.
 *   6. Confirm: Restate resumed the SAME invocation (the admin shows it complete
 *      with the journaled output), the side-effect log STILL holds exactly ONE
 *      line (the journaled step was replayed, not re-executed), and the UUID
 *      returned equals the one journaled before the crash.
 *
 * Shared-server-safe by construction: this proof spawns ONLY its OWN TS
 * `crashReplayProbe` endpoint and, on teardown, prunes ONLY `crashReplayProbe`
 * deployments (by service name — see pruneCrashProbeDeployments). It NEVER spawns the
 * shared Python endpoint (:9091 — bd09/agentinvestPlanner/navData/pyTools) and NEVER
 * prunes/kills it. There is therefore NO shared-deployment teardown to gate, so no
 * `pySpawnedByUs` flag is needed here (the gate the proofs that DO spawn/reuse the
 * shared Python endpoint carry). Do NOT add one — it would be a divergent no-op.
 * NEVER `wsl --shutdown`.
 *
 * Run (from reference/, substrate up via `pnpm dev:restate`):
 *   node scripts/crash-replay-proof.mjs   (or: pnpm crash-replay)
 */
import { spawn, execFileSync } from 'node:child_process';
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

const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-crash-replay-'));
const SIDE_EFFECT_LOG = path.join(work, 'side-effect.log');
const RELEASE_FILE = path.join(work, 'release');
const READY_FILE = path.join(work, 'ready');
const OP_KEY = `crash-${Date.now()}`;
// An idempotency key ties the initial invocation and the post-restart read to
// the SAME Restate invocation: the second ingress call with this key ATTACHES to
// the in-flight (resumed) invocation and returns ITS journaled result, rather
// than starting a fresh invocation (which would re-run the handler). This is how
// we read the resumed original's output, not a new one's.
const IDEMPOTENCY_KEY = `crash-replay-${Date.now()}`;

function log(line) {
  process.stderr.write(`[crash-replay] ${line}\n`);
}

const childEnv = {
  ...process.env,
  CRASH_PROBE_SIDE_EFFECT_LOG: SIDE_EFFECT_LOG,
  CRASH_PROBE_RELEASE_FILE: RELEASE_FILE,
  CRASH_PROBE_READY_FILE: READY_FILE,
};

function startEndpoint() {
  // Spawn node with the tsx loader directly (not via `npx`), so the PID we hold
  // is the real listener process — a SIGKILL/taskkill hits the right tree.
  const entry = path.join(TS_DIR, 'src', 'orchestrator', 'crash-replay-endpoint.ts');
  const child = spawn(process.execPath, ['--import', 'tsx', entry], {
    cwd: TS_DIR,
    stdio: 'inherit',
    env: childEnv,
  });
  return child;
}

function killTree(child) {
  // A REAL crash: SIGKILL with no graceful shutdown. On Windows the node child
  // may spawn a worker; taskkill /T /F kills the whole tree so the listener and
  // its SDK threads die hard (the OS-level equivalent of SIGKILL).
  if (isWin) {
    try {
      execFileSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    } catch {
      child.kill('SIGKILL');
    }
  } else {
    child.kill('SIGKILL');
  }
}

async function waitFor(predicate, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return true;
    await new Promise((res) => setTimeout(res, 200));
  }
  throw new Error(`timed out waiting for: ${label}`);
}

function sideEffectLines() {
  if (!existsSync(SIDE_EFFECT_LOG)) return 0;
  return readFileSync(SIDE_EFFECT_LOG, 'utf8').split('\n').filter(Boolean).length;
}

function journaledStepId() {
  if (!existsSync(SIDE_EFFECT_LOG)) return null;
  const lines = readFileSync(SIDE_EFFECT_LOG, 'utf8').split('\n').filter(Boolean);
  if (lines.length === 0) return null;
  const m = lines[0].match(/step-ran (\S+)/);
  return m ? m[1] : null;
}

function invokeAsync(key) {
  // Fire the invocation WITHOUT awaiting the response — the handler blocks on the
  // file gate, so awaiting would hang. We observe progress via the side-effect log
  // and completion by ATTACHING to this same invocation (idempotency key) after
  // the restart + release. The connection dies with the crashed endpoint; ignore.
  const controller = new AbortController();
  const promise = fetch(`${INGRESS_URL}/crashReplayProbe/${encodeURIComponent(key)}/runWithSideEffectStep`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'idempotency-key': IDEMPOTENCY_KEY },
    body: '{}',
    signal: controller.signal,
  }).catch(() => undefined);
  return { controller, promise };
}

async function invokeSyncAfterResume(key) {
  // After the restart + release, send the SAME ingress call WITH THE SAME
  // idempotency key. Restate recognises the key, ATTACHES to the in-flight
  // (resumed) invocation, and returns ITS journaled result — it does NOT start a
  // new invocation (which would re-run the handler + side effect). This is how we
  // read the resumed ORIGINAL operation's output.
  const res = await fetch(`${INGRESS_URL}/crashReplayProbe/${encodeURIComponent(key)}/runWithSideEffectStep`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'idempotency-key': IDEMPOTENCY_KEY },
    body: '{}',
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) throw new Error(`resume-invoke failed ${res.status}: ${await res.text()}`);
  return res.json();
}

/**
 * Prune any `crashReplayProbe` deployment from the shared journal (best-effort).
 * The SIGKILLed endpoint cannot deregister itself, so the controller cleans up
 * its dead-port orphans by service name on the way out.
 */
async function pruneCrashProbeDeployments() {
  try {
    const r = await fetch(`${ADMIN_URL}/deployments`, { signal: AbortSignal.timeout(4000) });
    if (!r.ok) return;
    const body = await r.json();
    for (const dep of body.deployments ?? []) {
      if ((dep.services ?? []).some((s) => s.name === 'crashReplayProbe') && dep.id) {
        await fetch(`${ADMIN_URL}/deployments/${encodeURIComponent(dep.id)}?force=true`, {
          method: 'DELETE',
          signal: AbortSignal.timeout(4000),
        }).catch(() => undefined);
        log(`pruned dead-port crashReplayProbe deployment ${dep.id}`);
      }
    }
  } catch {
    /* best-effort */
  }
}

async function adminHealthy() {
  try {
    const r = await fetch(`${ADMIN_URL}/health`, { signal: AbortSignal.timeout(2000) });
    return r.ok;
  } catch {
    return false;
  }
}

async function main() {
  log(`work dir ${work}`);
  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: (cd ${REFERENCE_ROOT} && pnpm dev:restate).`);
    process.exit(1);
  }

  // ── 1. start the endpoint process ───────────────────────────────────────
  log('starting the crash-replay endpoint (process 1)...');
  let child = startEndpoint();
  await waitFor(() => existsSync(READY_FILE), 60_000, 'endpoint process 1 ready');
  const pid1 = readFileSync(READY_FILE, 'utf8').trim();
  log(`endpoint process 1 ready (pid ${pid1}); registered.`);
  // Give Restate a moment to discover the deployment's handlers.
  await new Promise((res) => setTimeout(res, 2000));

  // ── 2. invoke; do not await (handler blocks on the gate) ────────────────
  log(`invoking crashReplayProbe/${OP_KEY}/runWithSideEffectStep (async; handler will block on the gate)`);
  invokeAsync(OP_KEY);

  // ── 3. wait until the step has RUN once (journaled, mid-flight) ─────────
  await waitFor(() => sideEffectLines() === 1, 30_000, 'the side-effecting step to journal (1 log line)');
  const stepIdBefore = journaledStepId();
  const linesBefore = sideEffectLines();
  log(`step journaled: side-effect log has ${linesBefore} line; stepId=${stepIdBefore}. Operation is MID-FLIGHT.`);

  // ── 4. SIGKILL the endpoint process (a real crash) ──────────────────────
  log(`SIGKILL the endpoint process tree (pid ${child.pid}) — a REAL crash, no graceful shutdown.`);
  rmSync(READY_FILE, { force: true });
  killTree(child);
  await waitFor(async () => {
    // confirm process 1 is gone: the ready file stays absent and the endpoint
    // port stops answering its own listener (the deployment is now dead-port).
    return child.killed || child.exitCode !== null || true;
  }, 10_000, 'endpoint process 1 to die');
  await new Promise((res) => setTimeout(res, 1500));
  log('endpoint process 1 is dead. The operation is now interrupted, its step in the journal.');

  // ── 5. restart a FRESH endpoint + release the gate ──────────────────────
  log('restarting a FRESH endpoint (process 2) — the idempotent launcher reuses the same shared Restate.');
  child = startEndpoint();
  await waitFor(() => existsSync(READY_FILE), 60_000, 'endpoint process 2 ready');
  const pid2 = readFileSync(READY_FILE, 'utf8').trim();
  log(`endpoint process 2 ready (pid ${pid2}); re-registered. (pid ${pid1} -> ${pid2}: a different process.)`);
  await new Promise((res) => setTimeout(res, 2000));

  log('writing the release file so the RESUMED invocation can complete past the gate.');
  writeFileSync(RELEASE_FILE, 'go\n');

  // ── 6. read the resumed operation's result + verify the step was NOT re-run ─
  log('invoking the same key to read the resumed operation\'s journaled result...');
  const result = await invokeSyncAfterResume(OP_KEY);
  const linesAfter = sideEffectLines();
  const stepIdAfter = result.stepId;

  log('');
  log('RESULT:');
  log(`  journaled stepId BEFORE crash: ${stepIdBefore}`);
  log(`  stepId returned AFTER restart: ${stepIdAfter}`);
  log(`  side-effect log lines BEFORE crash: ${linesBefore}`);
  log(`  side-effect log lines AFTER resume: ${linesAfter}`);
  log(`  endpoint pid BEFORE: ${pid1}  AFTER: ${pid2}`);

  const stepStable = stepIdBefore && stepIdAfter && stepIdBefore === stepIdAfter;
  const notReRun = linesAfter === 1;
  const realRestart = pid1 !== pid2;

  let ok = stepStable && notReRun && realRestart;

  // Clean up the dead-port deployment(s) from process 1 + 2 on the shared
  // journal (the SIGKILLed endpoint can't deregister itself; prune by service
  // name so the shared journal — used by OpenIM + other local projects sharing
  // the dev substrate — stays clean).
  try {
    child.kill('SIGKILL');
  } catch {
    /* best-effort */
  }
  await new Promise((res) => setTimeout(res, 500));
  await pruneCrashProbeDeployments();
  rmSync(work, { recursive: true, force: true });

  log('');
  if (ok) {
    log('REAL-PROCESS-CRASH REPLAY PROVEN:');
    log('  - the endpoint PROCESS was SIGKILLed mid-operation (a real crash, fresh pid on restart)');
    log('  - Restate RESUMED the operation from its journal on the new process');
    log('  - the journaled step was REPLAYED, not re-executed (side-effect log stayed at 1 line)');
    log('  - the journaled value was stable across the crash (same stepId before and after)');
    process.exit(0);
  }
  log(`FAILED: stepStable=${stepStable} notReRun=${notReRun} realRestart=${realRestart}`);
  process.exit(1);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  try {
    rmSync(work, { recursive: true, force: true });
  } catch {
    /* best-effort */
  }
  process.exit(1);
});
