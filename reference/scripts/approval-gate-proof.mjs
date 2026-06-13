#!/usr/bin/env node
/**
 * PRODUCTION-VO FORCED-FIRE proof for the HIGH-STAKES APPROVAL GATE (seam 3) —
 * the same production-VO crash-replay pattern as dispatch-crash-proof.mjs. The
 * four-flow audit gate.
 *
 * What it proves, ALL on the REAL `investmentOperation` VO (a forced-fire fixture
 * plan with riskScore >= the test threshold, NO LLM call):
 *
 *   (i)   PAUSE      — the VO durably SUSPENDS at the awakeable (the handler logs
 *                      `PAUSING for operator approval. awakeableId=...`; the op is
 *                      mid-flight, awaiting); a crash mid-pause RESUMES STILL-AWAITING
 *                      on a fresh pid, the awakeable id STABLE (not re-prompted).
 *   (ii)  APPROVE    — resolve the awakeable via the ingress
 *                      (POST /restate/awakeables/{id}/resolve {"approved":true}) →
 *                      the operation PROCEEDS → completes; status=completed.
 *   (iii) REJECT     — resolve {"approved":false,"reason":...} → the operation ABORTS
 *                      terminally (OperationAbortedError, "aborted-by-operator");
 *                      status=aborted, NO retry-loop.
 *   (iv)  TIMEOUT    — no resolution within a test-shortened APPROVAL_TIMEOUT → the
 *                      operation ABORTS terminally ("aborted-by-timeout");
 *                      status=aborted.
 *
 *   REPLAY-SAFETY    — a crash AFTER the decision resolves: the decision is read back
 *                      from the journal, NOT re-prompted (no second awakeable; the
 *                      resumed run does not re-emit an `approval-required` notice).
 *
 * The awakeable is resolved exactly as an operator would (no Operator UI): the
 * Restate ingress awakeable API — `POST {ingress}/restate/awakeables/{id}/resolve`
 * (payload body) and `/reject`. The awakeable id is read from the journaled notify
 * record the handler logs (the operator's "notification").
 *
 * Reuse-safe teardown: the SHARED Python deployment (:9091
 * bd09/agentinvestPlanner/pyTools) is torn down ONLY if THIS run spawned it
 * (pySpawnedByUs). If reused, it is LEFT REGISTERED — never strip a shared resource
 * (other local projects sharing the dev substrate + concurrent OpenIM work depend
 * on it). NEVER `wsl --shutdown`.
 *
 * Run (from reference/, substrate up via `pnpm dev:restate`):
 *   node scripts/approval-gate-proof.mjs   (or: pnpm approval-gate)
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
const WSL_DISTRO = process.env.RESTATE_WSL_DISTRO ?? 'Ubuntu-24.04';

// Forced-fire knobs: a LOW test threshold so the fixture plan's riskScore fires the
// gate, and a SHORT timeout so the timeout-abort flow fires in seconds.
const TEST_THRESHOLD = process.env.APPROVAL_TEST_THRESHOLD ?? '0.5';
const TEST_TIMEOUT_MS = process.env.APPROVAL_TEST_TIMEOUT_MS ?? '8000';
const PROOF_PORT = process.env.APPROVAL_PROOF_PORT ?? '9098';

function log(line) {
  process.stderr.write(`[approval-gate] ${line}\n`);
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

/**
 * A deterministic HIGH-STAKES fixture plan: riskScore 0.9 (>= the 0.5 test
 * threshold → the gate FIRES). Two healthy SO-09-01 steps so dispatch (seam 2,
 * before the gate) completes cleanly and the run reaches seam 3.
 */
function buildHighStakesFixturePlan() {
  return {
    steps: [
      {
        soId: 'SO-09-01',
        args: { beginning_value: '1000000', ending_value: '1050000', period_days: 90, cash_flows: [] },
        rationale: 'forced-fire fixture step 0',
      },
      {
        soId: 'SO-09-01',
        args: { beginning_value: '2000000', ending_value: '2100000', period_days: 90, cash_flows: [] },
        rationale: 'forced-fire fixture step 1',
      },
    ],
    riskScore: 0.9,
    summary: 'high-stakes approval-gate forced-fire fixture (riskScore 0.9)',
  };
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
  log('starting the PYTHON endpoint (bd09 — the dispatch target before seam 3)...');
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

/** Per-TS-endpoint log state — reset between processes. */
function makeLogState() {
  return {
    awakeableId: null,
    sawPausing: false,
    sawReplaying: false,
    sawCompleted: false,
    sawPostDecisionPause: false,
    notifyCount: 0,
  };
}

function attachLogParsing(child, state) {
  const onChunk = (buf) => {
    const text = buf.toString();
    process.stderr.write(text);
    // The handler logs `PAUSING for operator approval. awakeableId=<id>` once when the
    // gate fires (the operator's notification). Capture the awakeable id.
    const m = text.match(/awakeableId=(\S+)/);
    if (m && !state.awakeableId) state.awakeableId = m[1].replace(/[.,]+$/, '');
    if (/PAUSING for operator approval/.test(text)) state.sawPausing = true;
    // The journaled approval-notify record (`OPERATOR APPROVAL REQUIRED`) — count
    // emissions so replay-safety can assert it is NOT re-emitted on resume.
    const notifies = text.match(/OPERATOR APPROVAL REQUIRED/g);
    if (notifies) state.notifyCount += notifies.length;
    if (/journaled approval decision and the terminal state write/.test(text)) state.sawPostDecisionPause = true;
    if (/Replaying invocation/.test(text)) state.sawReplaying = true;
    if (/Invocation completed successfully/.test(text)) state.sawCompleted = true;
  };
  child.stdout?.on('data', onChunk);
  child.stderr?.on('data', onChunk);
}

function startTsEndpoint(fixturePlan, readyFile, state, extraEnv = {}) {
  const entry = path.join(TS_DIR, 'src', 'orchestrator', 'dispatch-proof-endpoint.ts');
  const child = spawn(process.execPath, ['--import', 'tsx', entry], {
    cwd: TS_DIR,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      AGENTINVEST_DISPATCH_PROOF_PORT: String(PROOF_PORT),
      DISPATCH_PROOF_READY_FILE: readyFile,
      AGENTINVEST_DISPATCH_FIXTURE_PLAN: JSON.stringify(fixturePlan),
      AGENTINVEST_HIGH_STAKES_THRESHOLD: TEST_THRESHOLD,
      AGENTINVEST_APPROVAL_TIMEOUT_MS: TEST_TIMEOUT_MS,
      ...extraEnv,
    },
  });
  attachLogParsing(child, state);
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

/** Fire-and-forget invoke of execute (the op pauses at the gate; we don't await). */
function invokeExecuteAsync(key, idempotencyKey, fixturePlan) {
  const controller = new AbortController();
  fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'idempotency-key': idempotencyKey },
    body: JSON.stringify({ kind: 'approval-gate-proof', params: { task: fixturePlan.summary } }),
    signal: controller.signal,
  }).catch(() => undefined);
  return controller;
}

/** Attach to the (resumed/awaited) invocation by idempotency key; returns its result or the terminal error. */
async function attachExecute(key, idempotencyKey, fixturePlan, timeoutMs = 90_000) {
  const res = await fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'idempotency-key': idempotencyKey },
    body: JSON.stringify({ kind: 'approval-gate-proof', params: { task: fixturePlan.summary } }),
    signal: AbortSignal.timeout(timeoutMs),
  });
  const text = await res.text();
  return { ok: res.ok, status: res.status, body: text };
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

/** Resolve an awakeable via the Restate ingress — exactly how a CLI/admin operator would. */
async function resolveAwakeable(awakeableId, payload) {
  const res = await fetch(`${INGRESS_URL}/restate/awakeables/${encodeURIComponent(awakeableId)}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`resolve awakeable failed ${res.status}: ${await res.text()}`);
  log(`resolved awakeable ${awakeableId} with ${JSON.stringify(payload)} (via the ingress — the operator path).`);
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
        log(`pruned approval-proof ${serviceName} deployment ${dep.id} (${dep.uri})`);
      }
    }
  } catch {
    /* best-effort */
  }
}

const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-approval-'));
let pyChild = null;
// Did THIS run spawn the shared Python endpoint (bd09/agentinvestPlanner/pyTools on
// :9091)? Only true if WE started it; false if we REUSED an already-running shared
// endpoint. Gates ALL Python-side teardown — never strip a shared deployment we did
// not spawn (other local projects sharing the dev substrate + concurrent
// OpenIM work depend on it). The TS proof endpoint we always spawn, so it is always
// cleaned up.
let pySpawnedByUs = false;
let tsChild = null;

/**
 * Run a forced-fire flow that ends WITHOUT a crash (approve / reject / timeout): start
 * a fresh TS endpoint, invoke, wait for the pause, optionally resolve, attach for the
 * terminal result, assert the status.
 */
async function runFlow({ label, key, fixturePlan, resolvePayload, expectStatus, expectAbortKind }) {
  log('');
  log(`──── FLOW: ${label} ────`);
  const readyFile = path.join(work, `ready-${key}`);
  const idem = `approval-${key}-${Date.now()}`;
  const state = makeLogState();
  tsChild = startTsEndpoint(fixturePlan, readyFile, state);
  await waitFor(() => existsSync(readyFile), 60_000, `${label}: TS endpoint ready`);
  await new Promise((res) => setTimeout(res, 1500));

  log(`invoking investmentOperation/${key}/execute (async; will dispatch then PAUSE at the gate)`);
  invokeExecuteAsync(key, idem, fixturePlan);

  // (i) PAUSE — wait until the handler logs the pause + emits the awakeable id.
  await waitFor(() => state.sawPausing && state.awakeableId !== null, 60_000, `${label}: gate to PAUSE`);
  log(`PAUSE confirmed — awakeableId=${state.awakeableId} (durable suspend; notifies=${state.notifyCount}).`);

  let terminal;
  if (resolvePayload !== undefined) {
    // (ii)/(iii) resolve via the ingress (the operator path), then attach for the result.
    await new Promise((res) => setTimeout(res, 500));
    await resolveAwakeable(state.awakeableId, resolvePayload);
    terminal = await attachExecute(key, idem, fixturePlan);
  } else {
    // (iv) TIMEOUT — do NOT resolve; attach and let the durable timeout fire.
    log(`NOT resolving — awaiting the ${TEST_TIMEOUT_MS}ms durable timeout to fire.`);
    terminal = await attachExecute(key, idem, fixturePlan);
  }

  await new Promise((res) => setTimeout(res, 800));
  const status = await readStatus(key);
  log(`terminal: HTTP ${terminal.status} ok=${terminal.ok}; VO status=${status && status.status}` +
    `${status && status.abort ? ` abort=${JSON.stringify(status.abort)}` : ''}`);

  const statusOk = status && status.status === expectStatus;
  const abortOk = expectAbortKind ? status && status.abort && status.abort.kind === expectAbortKind : true;
  // For aborts, the terminal HTTP must be a clean 4xx (terminal, no retry-storm), not a 5xx.
  const terminalShapeOk =
    expectStatus === 'completed' ? terminal.ok : !terminal.ok && terminal.status >= 400 && terminal.status < 500;
  const pass = statusOk && abortOk && terminalShapeOk && state.notifyCount === 1;

  killTree(tsChild);
  tsChild = null;
  await new Promise((res) => setTimeout(res, 600));
  await pruneDeployments('investmentOperation', PROOF_PORT);

  if (!pass) {
    log(`FLOW ${label} FAILED: statusOk=${statusOk} abortOk=${abortOk} terminalShapeOk=${terminalShapeOk} ` +
      `notifyCount=${state.notifyCount} (expected 1)`);
  } else {
    log(`FLOW ${label} PASS: status=${status.status}` +
      `${expectAbortKind ? ` abort=${status.abort.kind}` : ''}; one notify; clean terminal shape.`);
  }
  return pass;
}

/**
 * (i) PAUSE durability + REPLAY-SAFETY: pause at the gate, SIGKILL mid-pause, restart,
 * confirm the op resumes STILL-AWAITING (the awakeable id stable, NOT re-prompted),
 * THEN resolve and confirm the decision is read back (no second notify on resume).
 */
async function runCrashMidPauseThenApprove(fixturePlan) {
  log('');
  log('──── FLOW: PAUSE durability + REPLAY-SAFETY (crash mid-pause → resume still-awaiting → approve) ────');
  const key = `approvalcrash-${Date.now()}`;
  const idem = `approval-crash-${Date.now()}`;
  const readyFile = path.join(work, `ready-${key}`);

  // process 1 — pause at the gate
  // A LONG approval timeout for the crash flow so the durable timeout does NOT fire
  // during the crash+restart window (we want the op STILL-AWAITING on resume, then we
  // resolve it ourselves). The durable timer is journaled at the original deadline; a
  // short test timeout would (correctly) fire mid-restart and abort by timeout.
  const LONG_TIMEOUT = '600000';
  const state1 = makeLogState();
  tsChild = startTsEndpoint(fixturePlan, readyFile, state1, { AGENTINVEST_APPROVAL_TIMEOUT_MS: LONG_TIMEOUT });
  await waitFor(() => existsSync(readyFile), 60_000, 'crash: TS endpoint 1 ready');
  const pid1 = readFileSync(readyFile, 'utf8').trim();
  await new Promise((res) => setTimeout(res, 1500));

  log(`invoking investmentOperation/${key}/execute (async; will PAUSE at the gate)`);
  invokeExecuteAsync(key, idem, fixturePlan);
  await waitFor(() => state1.sawPausing && state1.awakeableId !== null, 60_000, 'crash: gate to PAUSE');
  const awakeableBefore = state1.awakeableId;
  log(`PAUSED — awakeableId=${awakeableBefore}; notifies(before crash)=${state1.notifyCount}. SIGKILL now (mid-pause).`);

  // SIGKILL mid-pause — a real crash while awaiting.
  rmSync(readyFile, { force: true });
  killTree(tsChild);
  await new Promise((res) => setTimeout(res, 1500));
  log('TS endpoint 1 dead. The op is suspended at the awakeable, its decision NOT yet made.');

  // process 2 — restart; the op must resume STILL-AWAITING (not re-prompt, not complete).
  const state2 = makeLogState();
  tsChild = startTsEndpoint(fixturePlan, readyFile, state2, { AGENTINVEST_APPROVAL_TIMEOUT_MS: LONG_TIMEOUT });
  await waitFor(() => existsSync(readyFile), 60_000, 'crash: TS endpoint 2 ready');
  const pid2 = readFileSync(readyFile, 'utf8').trim();
  log(`TS endpoint 2 ready (pid ${pid1} -> ${pid2}). Giving the resumed op a moment...`);
  await new Promise((res) => setTimeout(res, 4000));

  // It must STILL be awaiting (status running/undefined, not completed/aborted) and
  // must NOT have emitted a fresh notify on resume (the awakeable is read back, the
  // gate does not re-prompt). Restate replays the journaled awakeable; the id is stable.
  let midStatus = null;
  try {
    midStatus = await readStatus(key);
  } catch {
    /* state may be 'running' with no terminal write yet */
  }
  const stillAwaiting = !midStatus || midStatus.status === 'running';
  const noRePrompt = state2.notifyCount === 0; // the resumed process did NOT re-emit the notify
  log(`after resume: VO status=${midStatus && midStatus.status} (still-awaiting=${stillAwaiting}); ` +
    `notifies(resumed process)=${state2.notifyCount} (re-prompt-free=${noRePrompt}); ` +
    `Replaying=${state2.sawReplaying}.`);

  // Now resolve (approve) via the ingress — using the SAME awakeable id (it is stable
  // across the crash). The op must proceed to completed.
  await resolveAwakeable(awakeableBefore, { approved: true });
  const terminal = await attachExecute(key, idem, fixturePlan);
  await new Promise((res) => setTimeout(res, 800));
  const finalStatus = await readStatus(key);
  log(`after approve (same awakeable id): HTTP ${terminal.status}; VO status=${finalStatus && finalStatus.status}.`);

  killTree(tsChild);
  tsChild = null;
  await new Promise((res) => setTimeout(res, 600));
  await pruneDeployments('investmentOperation', PROOF_PORT);

  const realRestart = pid1 !== pid2;
  const resumedSameInvocation = state2.sawReplaying;
  const reachedCompleted = terminal.ok && finalStatus && finalStatus.status === 'completed';
  const pass = stillAwaiting && noRePrompt && realRestart && resumedSameInvocation && reachedCompleted;
  if (!pass) {
    log(`CRASH/REPLAY FAILED: stillAwaiting=${stillAwaiting} noRePrompt=${noRePrompt} realRestart=${realRestart} ` +
      `resumedSameInvocation=${resumedSameInvocation} reachedCompleted=${reachedCompleted}`);
  } else {
    log('CRASH/REPLAY PASS: crashed mid-pause → resumed STILL-AWAITING on a fresh pid (Replaying), the awakeable id ' +
      'stable, NO re-prompt; then the SAME awakeable id was resolved → op completed. The durable pause survived a crash.');
  }
  return pass;
}

/**
 * REPLAY-SAFETY (decision read-back): pause at the gate (with a post-DECISION crash
 * pause armed — AGENTINVEST_APPROVAL_CRASH_DELAY_MS, which sits AFTER seam 3, between
 * the resolved decision and the terminal write), resolve approve so the decision
 * JOURNALS, wait until the op enters that post-decision pause, SIGKILL there, restart,
 * and confirm the journaled decision is READ BACK (the resumed process does NOT
 * re-emit the approval notice / re-prompt) and the op completes.
 */
async function runCrashAfterDecision(fixturePlan) {
  log('');
  log('──── FLOW: REPLAY-SAFETY (crash AFTER the decision resolves → decision read back, not re-prompted) ────');
  const key = `approvalafter-${Date.now()}`;
  const idem = `approval-after-${Date.now()}`;
  const readyFile = path.join(work, `ready-${key}`);

  // process 1 — pause at the gate, with the POST-DECISION crash pause armed so that
  // AFTER we approve, the op pauses in the between-decision-and-terminal-write window.
  const state1 = makeLogState();
  tsChild = startTsEndpoint(fixturePlan, readyFile, state1, { AGENTINVEST_APPROVAL_CRASH_DELAY_MS: '12000' });
  await waitFor(() => existsSync(readyFile), 60_000, 'after: TS endpoint 1 ready');
  const pid1 = readFileSync(readyFile, 'utf8').trim();
  await new Promise((res) => setTimeout(res, 1500));

  log('invoking; will PAUSE at the gate, then (after approve) PAUSE again post-decision (the crash window).');
  invokeExecuteAsync(key, idem, fixturePlan);
  await waitFor(() => state1.sawPausing && state1.awakeableId !== null, 60_000, 'after: gate to PAUSE');
  const awakeableBefore = state1.awakeableId;
  log(`PAUSED at the gate — awakeableId=${awakeableBefore}. Resolving approve so the decision JOURNALS...`);

  // Resolve approve — the decision journals; the op proceeds INTO the armed post-decision
  // pause (12s). We SIGKILL during that pause: a real crash AFTER the decision, BEFORE the
  // terminal write. On resume the journaled decision must be read back (no re-prompt).
  await resolveAwakeable(awakeableBefore, { approved: true });
  // Wait for the op to ENTER the post-decision pause window (the handler logs the
  // PROOF-ONLY pause), so the crash lands AFTER the decision journaled and inside the
  // pre-terminal-write window.
  await waitFor(() => state1.sawPostDecisionPause, 30_000, 'after: op to enter the post-decision pause');
  log('op is in the post-decision pause window (decision journaled, terminal write pending). SIGKILL now.');
  rmSync(readyFile, { force: true });
  killTree(tsChild);
  await new Promise((res) => setTimeout(res, 1500));
  log('SIGKILLed AFTER the decision resolved (in the post-decision pause). On resume the decision must be READ BACK.');

  // process 2 — restart with the SAME crash-delay env so the handler code MATCHES the
  // journal (the journaled `ctx.sleep` entry must be reproduced by the replayed code —
  // otherwise Restate raises "Replayed journal doesn't match the handler code"). On
  // resume the op replays past the (already-elapsed) sleep, reads the journaled decision
  // back, and completes.
  const state2 = makeLogState();
  tsChild = startTsEndpoint(fixturePlan, readyFile, state2, { AGENTINVEST_APPROVAL_CRASH_DELAY_MS: '12000' });
  await waitFor(() => existsSync(readyFile), 60_000, 'after: TS endpoint 2 ready');
  const pid2 = readFileSync(readyFile, 'utf8').trim();
  await new Promise((res) => setTimeout(res, 2000));

  const terminal = await attachExecute(key, idem, fixturePlan);
  await new Promise((res) => setTimeout(res, 800));
  const finalStatus = await readStatus(key);
  log(`after resume: HTTP ${terminal.status}; VO status=${finalStatus && finalStatus.status}; ` +
    `notifies(resumed process)=${state2.notifyCount} (must be 0 — decision read back, not re-prompted); ` +
    `Replaying=${state2.sawReplaying}.`);

  killTree(tsChild);
  tsChild = null;
  await new Promise((res) => setTimeout(res, 600));
  await pruneDeployments('investmentOperation', PROOF_PORT);

  const realRestart = pid1 !== pid2;
  const decisionReadBack = state2.notifyCount === 0; // no re-prompt on resume
  const reachedCompleted = terminal.ok && finalStatus && finalStatus.status === 'completed';
  const pass = realRestart && decisionReadBack && reachedCompleted;
  if (!pass) {
    log(`AFTER-DECISION REPLAY FAILED: realRestart=${realRestart} decisionReadBack=${decisionReadBack} ` +
      `reachedCompleted=${reachedCompleted}`);
  } else {
    log('AFTER-DECISION REPLAY PASS: crashed AFTER the decision resolved → on resume the journaled decision was READ ' +
      'BACK (the resumed process did NOT re-emit the approval notice / re-prompt), op completed. Replay-safe.');
  }
  return pass;
}

async function main() {
  log(`work dir ${work}`);
  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: (cd ${REFERENCE_ROOT} && pnpm dev:restate).`);
    process.exit(1);
  }

  const fixturePlan = buildHighStakesFixturePlan();
  log(`forced-fire: fixture riskScore=${fixturePlan.riskScore} >= test threshold ${TEST_THRESHOLD} → the gate FIRES.`);
  log(`test timeout: ${TEST_TIMEOUT_MS}ms (shortened from the 24h provisional default for the timeout-abort flow).`);

  // bd09 up (the seam-2 dispatch target, reached before the gate). Reuse the shared
  // :9091 endpoint if registered; only spawn if not (reuse-safety).
  if (await awaitServiceRegistered('bd09', 2)) {
    log('bd09 already registered — reusing the running Python endpoint (no spawn). LEFT INTACT on exit (shared).');
  } else {
    pyChild = startPyEndpoint();
    pySpawnedByUs = true;
    if (!(await awaitServiceRegistered('bd09'))) {
      log('bd09 did not register within the timeout. Aborting.');
      try {
        pyChild.kill('SIGKILL');
      } catch {
        /* best-effort */
      }
      process.exit(1);
    }
    log('bd09 registered (dispatch target reachable).');
  }

  const results = {};
  // (i)+replay-safety: crash mid-pause → resume still-awaiting → approve.
  results.crashMidPause = await runCrashMidPauseThenApprove(fixturePlan);
  // replay-safety: crash AFTER the decision → read back, not re-prompted.
  results.crashAfterDecision = await runCrashAfterDecision(fixturePlan);
  // (ii) approve.
  results.approve = await runFlow({
    label: 'APPROVE (resolve {approved:true} → proceeds → completes)',
    key: `approve-${Date.now()}`,
    fixturePlan,
    resolvePayload: { approved: true },
    expectStatus: 'completed',
  });
  // (iii) reject.
  results.reject = await runFlow({
    label: 'REJECT (resolve {approved:false} → terminal abort "aborted-by-operator")',
    key: `reject-${Date.now()}`,
    fixturePlan,
    resolvePayload: { approved: false, reason: 'forced-fire proof: operator rejects the high-stakes plan' },
    expectStatus: 'aborted',
    expectAbortKind: 'aborted-by-operator',
  });
  // (iv) timeout.
  results.timeout = await runFlow({
    label: 'TIMEOUT (no resolution within the test timeout → terminal abort "aborted-by-timeout")',
    key: `timeout-${Date.now()}`,
    fixturePlan,
    resolvePayload: undefined,
    expectStatus: 'aborted',
    expectAbortKind: 'aborted-by-timeout',
  });

  // Teardown — only what THIS run spawned. The TS proof endpoints are all
  // self-pruned per flow. The shared Python :9091 deployment is torn down ONLY if WE
  // spawned it; if reused, LEAVE IT REGISTERED (other local projects sharing the dev
  // substrate + concurrent OpenIM work depend on it).
  if (pySpawnedByUs) {
    try {
      pyChild.kill('SIGKILL');
    } catch {
      /* best-effort */
    }
    await new Promise((res) => setTimeout(res, 600));
    await pruneDeployments('agentinvestPlanner', process.env.AGENTINVEST_PY_ENDPOINT_PORT ?? '9091');
  } else {
    log('reused the shared Python endpoint — leaving bd09/agentinvestPlanner/pyTools registered on exit (shared).');
  }
  rmSync(work, { recursive: true, force: true });

  const allPass =
    results.crashMidPause && results.crashAfterDecision && results.approve && results.reject && results.timeout;

  log('');
  log('SUMMARY:');
  log(`  (i) PAUSE durable + crash-resumes-still-awaiting : ${results.crashMidPause ? 'PASS' : 'FAIL'}`);
  log(`  replay-safety: crash-after-decision read back    : ${results.crashAfterDecision ? 'PASS' : 'FAIL'}`);
  log(`  (ii) APPROVE → proceeds → completes              : ${results.approve ? 'PASS' : 'FAIL'}`);
  log(`  (iii) REJECT → terminal abort (by-operator)      : ${results.reject ? 'PASS' : 'FAIL'}`);
  log(`  (iv) TIMEOUT → terminal abort (by-timeout)       : ${results.timeout ? 'PASS' : 'FAIL'}`);
  log('');
  if (allPass) {
    log('PRODUCTION-VO HIGH-STAKES APPROVAL GATE PROVEN: all four flows + replay-safety green on the REAL');
    log('investmentOperation VO; the awakeable resolved via the ingress (the operator path); aborts terminal (no retry-storm).');
    process.exit(0);
  }
  log('FAILED — see the per-flow diagnostics above.');
  process.exit(1);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  try {
    if (tsChild) killTree(tsChild);
    if (pyChild && pySpawnedByUs) pyChild.kill('SIGKILL');
  } catch {
    /* best-effort */
  }
  try {
    rmSync(work, { recursive: true, force: true });
  } catch {
    /* best-effort */
  }
  process.exit(1);
});
