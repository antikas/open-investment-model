#!/usr/bin/env node
/**
 * SUPERSEDED by scripts/plan-crash-proof.mjs (OIM-130). The production VO's
 * `execute` no longer journals a bare stub step — the planning step (the real
 * `.plan()` call) now lands at seam 1, so this script's `journaled stub step-id=`
 * witness is gone. The journaled-exactly-once crash-replay of the PRODUCTION VO is
 * proven by `pnpm plan-crash` (plan-crash-proof.mjs), which crashes the SAME
 * `investmentOperation` in the between-plan-and-terminal-write window and asserts
 * the LLM-call-count stays at 1 across the crash (replay reads the journaled plan,
 * the model is NOT re-invoked). The `pnpm shell-crash` script now runs plan-crash.
 * This file is retained for git history; it is NOT a live floor. Nothing references it:
 * package.json's `shell-crash` points at scripts/plan-crash-proof.mjs (verified OIM-184);
 * the only remaining mentions are historical docs.
 *
 * Shared-server-safe by construction (OIM-184): even though it is dead, this proof was
 * NEVER shared-deployment-stripping — it spawns ONLY its OWN TS `investmentOperation`
 * endpoint (shell-crash-endpoint.ts) and prunes ONLY `investmentOperation` deployments on
 * its OWN port (:9096 — see pruneShellDeployments). It NEVER spawns or prunes the shared
 * Python endpoint (:9091 — bd09/agentinvestPlanner/navData/pyTools). It is left in place
 * (superseded marker, not removed) because removing it would touch git-history-retained
 * code + the historical doc references for no shared-server-hygiene gain; a future run
 * tripping on it cannot strip the shared server. NEVER `wsl --shutdown`.
 *
 * --- original header (OIM-104, the stub-step crash proof) ---
 *
 * PRODUCTION-shell real-process-crash replay proof (closes P-CRASH-1).
 *
 * cycle-1's `crash-replay-proof.mjs` SIGKILLed a separate single-step
 * `crashReplayProbe`. This proof SIGKILLs the REAL production
 * `investmentOperation.execute` (gate → set(running) → run(stub-step) →
 * set(completed)) in the fiduciary-relevant window the pre-mortem named:
 * between the journaled stub step and the terminal `ctx.set('state','completed')`.
 *
 * Reaching that window. The production handler has no natural await point in that
 * window, so it reads an ENV-GATED, PROOF-ONLY durable pause
 * (`AGENTINVEST_CRASH_PROOF_DELAY_MS`) — a guarded `ctx.sleep` that is NEVER
 * reached when the env is unset (production runs with it unset; the journal shape
 * is then byte-for-byte identical). THIS controller sets that env on the endpoint
 * process it spawns, so the handler pauses in the window long enough to SIGKILL.
 *
 * Mechanism (see shell-crash-endpoint.ts):
 *   1. Spawn the shell-crash endpoint as a CHILD process (its own pid). It binds
 *      the REAL `investmentOperation` and registers against the shared Restate.
 *      The child env carries AGENTINVEST_CRASH_PROOF_DELAY_MS so execute pauses.
 *   2. Invoke `investmentOperation/<key>/execute` with an idempotency key
 *      (fire-and-forget — the handler will be sitting in the proof-pause).
 *   3. Capture the journaled stub stepId from the handler's own
 *      `journaled stub step-id=<uuid>` log line (proves the step ran + journaled,
 *      operation MID-FLIGHT in the pause window).
 *   4. SIGKILL the endpoint process tree (a real crash, no graceful shutdown).
 *   5. Restart a FRESH endpoint process (different pid); re-register.
 *   6. Re-POST the SAME key WITH THE SAME idempotency key — Restate ATTACHES to
 *      the resumed original invocation and returns its journaled OperationResult.
 *      Read the VO `status` too.
 *   7. Confirm: same inv_ id resumed (server logs Starting→Replaying→completed —
 *      surfaced on stdout), the resumed result's stepId EQUALS the pre-crash
 *      journaled stepId (the stub `ctx.run` step was REPLAYED from the journal,
 *      not re-run — a re-run would mint a new UUID), VO state reaches 'completed',
 *      and the pid changed (a real crash).
 *
 * Run (from reference/, substrate up via `pnpm dev:restate`):
 *   node scripts/shell-crash-proof.mjs   (or: pnpm shell-crash)
 */
import { spawn, execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REFERENCE_ROOT = path.resolve(__dirname, '..');
const TS_DIR = path.join(REFERENCE_ROOT, 'ts');

const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://localhost:9070';
const INGRESS_URL = process.env.RESTATE_INGRESS_URL ?? 'http://localhost:8080';
const isWin = process.platform === 'win32';

// The proof-only durable pause the production handler reads ONLY when this env is
// set. 9s is comfortably longer than the ~2s settle we wait before SIGKILL, so
// the crash lands inside the pause window (step journaled, terminal write not yet).
const CRASH_PROOF_DELAY_MS = process.env.AGENTINVEST_CRASH_PROOF_DELAY_MS ?? '9000';

const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-shell-crash-'));
const READY_FILE = path.join(work, 'ready');
const OP_KEY = `shellcrash-${Date.now()}`;
const IDEMPOTENCY_KEY = `shell-crash-${Date.now()}`;

function log(line) {
  process.stderr.write(`[shell-crash] ${line}\n`);
}

const childEnv = {
  ...process.env,
  SHELL_CRASH_READY_FILE: READY_FILE,
  AGENTINVEST_CRASH_PROOF_DELAY_MS: CRASH_PROOF_DELAY_MS,
};

// We capture the child's stdout/stderr (NOT inherit) so we can parse the
// production handler's `journaled stub step-id=<uuid>` line — the pre-crash
// stepId witness — while still echoing the lines for the auditor.
let capturedStepIdBefore = null;
let sawStarting = false;
let sawReplaying = false;
let sawCompleted = false;

function attachLogParsing(child) {
  const onChunk = (buf) => {
    const text = buf.toString();
    process.stderr.write(text); // echo through for the auditor's transcript
    const m = text.match(/journaled stub step-id=([0-9a-fA-F-]{36})/);
    if (m && !capturedStepIdBefore) capturedStepIdBefore = m[1];
    if (/Starting invocation/.test(text)) sawStarting = true;
    if (/Replaying invocation/.test(text)) sawReplaying = true;
    if (/Invocation completed successfully/.test(text)) sawCompleted = true;
  };
  child.stdout?.on('data', onChunk);
  child.stderr?.on('data', onChunk);
}

function startEndpoint() {
  const entry = path.join(TS_DIR, 'src', 'orchestrator', 'shell-crash-endpoint.ts');
  const child = spawn(process.execPath, ['--import', 'tsx', entry], {
    cwd: TS_DIR,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: childEnv,
  });
  attachLogParsing(child);
  return child;
}

function killTree(child) {
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

function invokeExecuteAsync(key) {
  // Fire-and-forget — the handler sits in the proof-pause; the connection dies
  // with the crashed endpoint. We read the result after resume by attaching with
  // the same idempotency key.
  const controller = new AbortController();
  fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'idempotency-key': IDEMPOTENCY_KEY },
    body: JSON.stringify({ kind: 'shell-crash-proof' }),
    signal: controller.signal,
  }).catch(() => undefined);
  return controller;
}

async function attachExecuteAfterResume(key) {
  // Same key + SAME idempotency key → Restate attaches to the resumed in-flight
  // invocation and returns ITS journaled OperationResult (it does NOT start a
  // fresh invocation, which would re-run execute + mint a new stepId).
  const res = await fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'idempotency-key': IDEMPOTENCY_KEY },
    body: JSON.stringify({ kind: 'shell-crash-proof' }),
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) throw new Error(`resume-attach failed ${res.status}: ${await res.text()}`);
  return res.json();
}

async function readStatus(key) {
  const res = await fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`status failed ${res.status}: ${await res.text()}`);
  return res.json();
}

async function pruneShellDeployments() {
  // The SIGKILLed endpoint can't deregister itself; prune dead-port
  // `investmentOperation` deployments registered by THIS proof from the shared
  // journal (by URI port, so we never touch the dev-server's own binding).
  try {
    const r = await fetch(`${ADMIN_URL}/deployments`, { signal: AbortSignal.timeout(4000) });
    if (!r.ok) return;
    const body = await r.json();
    for (const dep of body.deployments ?? []) {
      const isOurs =
        (dep.services ?? []).some((s) => s.name === 'investmentOperation') &&
        typeof dep.uri === 'string' &&
        dep.uri.includes(`:${process.env.AGENTINVEST_SHELL_CRASH_PORT ?? '9096'}`);
      if (isOurs && dep.id) {
        await fetch(`${ADMIN_URL}/deployments/${encodeURIComponent(dep.id)}?force=true`, {
          method: 'DELETE',
          signal: AbortSignal.timeout(4000),
        }).catch(() => undefined);
        log(`pruned dead-port investmentOperation deployment ${dep.id} (${dep.uri})`);
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
  log(`proof-only durable pause AGENTINVEST_CRASH_PROOF_DELAY_MS=${CRASH_PROOF_DELAY_MS}ms (set ONLY on the proof endpoint; production runs unset)`);
  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: (cd ${REFERENCE_ROOT} && pnpm dev:restate).`);
    process.exit(1);
  }

  // ── 1. start the PRODUCTION-shell endpoint (process 1) ──────────────────
  log('starting the shell-crash endpoint (process 1) — binds the REAL investmentOperation...');
  let child = startEndpoint();
  await waitFor(() => existsSync(READY_FILE), 60_000, 'endpoint process 1 ready');
  const pid1 = readFileSync(READY_FILE, 'utf8').trim();
  log(`endpoint process 1 ready (pid ${pid1}); registered.`);
  await new Promise((res) => setTimeout(res, 2000));

  // ── 2. invoke the REAL execute; do not await (handler sits in the pause) ─
  log(`invoking investmentOperation/${OP_KEY}/execute (async; handler will pause in the crash window)`);
  invokeExecuteAsync(OP_KEY);

  // ── 3. wait until the stub step is journaled (its log line appears) ─────
  await waitFor(() => capturedStepIdBefore !== null, 30_000, 'the stub step to journal (journaled stub step-id= log line)');
  log(`stub step journaled: stepId(before)=${capturedStepIdBefore}. Operation is MID-FLIGHT in the proof-pause window (terminal set not yet written).`);

  // ── 4. SIGKILL the endpoint process (a real crash) IN the window ────────
  log(`SIGKILL the endpoint process tree (pid ${child.pid}) — a REAL crash, between the journaled step and the terminal state write.`);
  rmSync(READY_FILE, { force: true });
  killTree(child);
  await new Promise((res) => setTimeout(res, 1500));
  log('endpoint process 1 is dead. The production operation is interrupted, its stub step in the journal, the terminal write NOT done.');

  // ── 5. restart a FRESH endpoint (process 2) ─────────────────────────────
  log('restarting a FRESH endpoint (process 2) — same shared Restate, env still carries the (now-elapsing) pause.');
  child = startEndpoint();
  await waitFor(() => existsSync(READY_FILE), 60_000, 'endpoint process 2 ready');
  const pid2 = readFileSync(READY_FILE, 'utf8').trim();
  log(`endpoint process 2 ready (pid ${pid2}); re-registered. (pid ${pid1} -> ${pid2}: a different process.)`);
  await new Promise((res) => setTimeout(res, 2000));

  // ── 6. attach to the resumed invocation + read its journaled result ─────
  log('attaching to the resumed invocation (same idempotency key) to read its journaled OperationResult...');
  const result = await attachExecuteAfterResume(OP_KEY);
  const status = await readStatus(OP_KEY);
  const stepIdAfter = result.stepId;

  log('');
  log('RESULT:');
  log(`  journaled stub stepId BEFORE crash: ${capturedStepIdBefore}`);
  log(`  resumed OperationResult.stepId AFTER restart: ${stepIdAfter}`);
  log(`  resumed OperationResult.status: ${result.status}`);
  log(`  VO state (status handler) AFTER resume: ${JSON.stringify(status)}`);
  log(`  endpoint pid BEFORE: ${pid1}  AFTER: ${pid2}`);
  log(`  server log witnesses — Starting=${sawStarting} Replaying=${sawReplaying} Completed=${sawCompleted}`);

  const stepStable = capturedStepIdBefore && stepIdAfter && capturedStepIdBefore === stepIdAfter;
  const reachedCompleted = result.status === 'completed' && status && status.status === 'completed';
  const voStepMatches = status && status.stepId === capturedStepIdBefore;
  const realRestart = pid1 !== pid2;
  const resumedSameInvocation = sawReplaying; // Restate logged Replaying for the original inv id on the new pid

  const ok = stepStable && reachedCompleted && voStepMatches && realRestart && resumedSameInvocation;

  // cleanup: kill process 2, prune our dead-port deployment from the shared journal
  try {
    child.kill('SIGKILL');
  } catch {
    /* best-effort */
  }
  await new Promise((res) => setTimeout(res, 500));
  await pruneShellDeployments();
  rmSync(work, { recursive: true, force: true });

  log('');
  if (ok) {
    log('PRODUCTION-SHELL REAL-PROCESS-CRASH REPLAY PROVEN:');
    log('  - the REAL investmentOperation was SIGKILLed mid-execute, between its journaled stub step and the terminal ctx.set(completed)');
    log('  - Restate RESUMED the SAME invocation from the journal on a fresh process (Replaying invocation on the new pid)');
    log('  - the journaled stub step was REPLAYED, not re-run (resumed stepId == pre-crash stepId; a re-run would mint a new UUID)');
    log('  - the VO reached terminal state completed with the same journaled stepId, on a different pid (a real crash)');
    process.exit(0);
  }
  log(
    `FAILED: stepStable=${stepStable} reachedCompleted=${reachedCompleted} ` +
      `voStepMatches=${voStepMatches} realRestart=${realRestart} resumedSameInvocation=${resumedSameInvocation}`,
  );
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
