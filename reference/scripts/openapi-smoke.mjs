#!/usr/bin/env node
/**
 * curl-driven SMOKE TEST of EVERY agentINVEST OpenAPI endpoint (reuse-safe, live).
 *
 * WHAT IT DOES. With the shared Restate substrate up + bd09 registered, this proof curls
 * EVERY endpoint of the OpenAPI surface and asserts the status + a well-formed response:
 *
 *   over the Restate INGRESS (the bd09 handler operations from the spec):
 *     - POST /bd09/list_capabilities  (arity-0, NO body)          -> 200 + the catalogue
 *     - POST /bd09/execute_so  (a VALID envelope {soId, args})     -> 200 + a typed result
 *     - POST /bd09/execute_so  (a MALFORMED body — not an envelope) -> a clean 4xx (NOT 5xx, NOT 200)
 *
 *   over the DOCS APP (make_docs_app, served on a port THIS script spawns):
 *     - GET /openapi.json                                          -> 200 + the validated 3.1 spec
 *     - GET /docs                                                  -> 200 + the Swagger UI HTML
 *     - GET /no-such-path  (the well-formed-error check, IN #3)    -> 404 + a structured JSON error
 *
 * MASK-IMMUNE SUCCESS ORACLE. Each check derives PASS/FAIL from the curl's ACTUAL
 * status code + a structural assertion on the body (a substring / JSON shape), NOT from a wrapped
 * `pnpm`/`uv`/`curl` exit a shell could mask. The gate prints a single stdout sentinel
 * `OPENAPI_SMOKE_RESULT: PASS|FAIL rc=N` (N = the count of failed checks) derived from those
 * per-check results — that sentinel is the oracle; this script's own exit merely mirrors it.
 *
 * REUSE-SAFE. The shared Python endpoint on :9091 (bd09/agentinvestPlanner/pyTools/...)
 * is REUSED if already serving and LEFT REGISTERED + RUNNING on exit. It is spawned (with
 * --no-register: the deployment is already registered pointing at :9091) ONLY if it is not
 * serving, and torn down on exit ONLY in that case (gated on `pySpawnedByUs`). The docs app runs
 * on a port THIS script always spawns (`pyDocsSpawnedByUs` is always true) and is always torn down.
 * The shared bd09 deployment registration in Restate is NEVER pruned. NEVER `wsl --shutdown`.
 *
 * Run (from reference/, substrate up):  node scripts/openapi-smoke.mjs   (or: pnpm openapi:smoke)
 */
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REFERENCE_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(REFERENCE_ROOT, '..');

const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://localhost:9070';
const INGRESS_URL = process.env.RESTATE_INGRESS_URL ?? 'http://localhost:8080';
const isWin = process.platform === 'win32';
const WSL_DISTRO = process.env.RESTATE_WSL_DISTRO ?? 'Ubuntu-24.04';

// The docs app port THIS script spawns (distinct from :9091 the endpoint, :9092 the default
// serve_docs port serve_docs uses, :8080 ingress, :9070 admin). Always spawned-by-us → always
// torn down.
const DOCS_PORT = Number(process.env.OPENAPI_SMOKE_DOCS_PORT ?? '9093');
const SAMPLE_SO_ID = process.env.OPENAPI_SMOKE_SO_ID ?? 'SO-09-01';
// A genuinely VALID args payload for SO-09-01 (compute_total_return / Modified-Dietz): the tool
// requires beginning_value, ending_value, period_days (a no-flow window). A 200 here proves a valid
// call returns a well-formed result; the malformed-body check proves a bad call is a clean 4xx.
const VALID_SO_ARGS = {
  beginning_value: 1000000,
  ending_value: 1050000,
  period_days: 90,
  cash_flows: [],
};

function log(line) {
  process.stderr.write(`[openapi-smoke] ${line}\n`);
}
function toWsl(p) {
  return '/mnt/' + p[0].toLowerCase() + p.slice(2).replace(/\\/g, '/');
}
function shq(s) {
  return `'${s.replace(/'/g, `'\\''`)}'`;
}
function wslPrelude() {
  const wslRef = toWsl(REFERENCE_ROOT);
  const repo = toWsl(REPO_ROOT);
  return (
    `export PATH="$HOME/.local/bin:$PATH"; ` +
    `tr -d '\\r' < ${wslRef}/scripts/lib/agentinvest-venv-path.sh > /tmp/agentinvest-venv-path.sh; ` +
    `. /tmp/agentinvest-venv-path.sh; ` +
    `agentinvest_set_venv_env '${repo}'; ` +
    `cd ${wslRef}/python`
  );
}

/** Spawn a long-lived Python process running `python -c <code>` inside the venv (WSL on Windows). */
function spawnPython(pyCode, label) {
  const env = { ...process.env, WSL_UTF8: '1' };
  let cmd;
  let args;
  if (isWin) {
    cmd = 'wsl';
    args = ['-d', WSL_DISTRO, '--', 'bash', '-lc', `${wslPrelude()} && uv run python -c ${shq(pyCode)}`];
  } else {
    cmd = 'bash';
    args = [
      '-lc',
      `export PATH="$HOME/.local/bin:$PATH" && cd ${REFERENCE_ROOT}/python && uv run python -c ${shq(pyCode)}`,
    ];
  }
  log(`spawning ${label}...`);
  return spawn(cmd, args, { stdio: ['ignore', 'inherit', 'inherit'], env });
}

async function reachable(url, ms = 3000, init = {}) {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(ms), ...init });
    return r.ok;
  } catch {
    return false;
  }
}

async function adminHealthy() {
  return reachable(`${ADMIN_URL}/health`, 3000);
}
async function bd09Registered() {
  return reachable(`${ADMIN_URL}/services/bd09/openapi`, 3000);
}

/** Is the Python endpoint :9091 actually SERVING (process up), not just registered in metadata? */
async function pyEndpointServing() {
  // The endpoint answers a Restate discovery handshake on /; any HTTP answer (even non-200) means
  // a process is bound and serving. A connection error (000) means the process is down.
  try {
    await fetch('http://localhost:9091/', { signal: AbortSignal.timeout(2500) });
    return true; // got an HTTP response → a process is bound
  } catch (err) {
    // A timeout/connection-refused → not serving. (A 4xx would have resolved, not thrown.)
    return false;
  }
}

/** Verify mirrored networking (localhost forwarding depends on it). Best-effort, Windows-only. */
function verifyMirrored() {
  if (!isWin) return true;
  const res = spawnSync('wsl', ['-d', WSL_DISTRO, '--', 'wslinfo', '--networking-mode'], {
    encoding: 'utf8',
  });
  const mode = (res.stdout ?? '').trim();
  if (mode !== 'mirrored') {
    log(`WARNING: WSL networking-mode is '${mode}', expected 'mirrored'. localhost forwarding may be unreliable.`);
    return false;
  }
  log(`WSL networking-mode: mirrored (localhost forwarding OK).`);
  return true;
}

async function waitUntil(pred, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await pred()) return true;
    await new Promise((r) => setTimeout(r, 700));
  }
  return false;
}

/**
 * One curl-style check. Returns { name, ok, status, detail }. The oracle is structural:
 * `expectStatus` matched (or, for the malformed case, a 4xx class) AND `bodyAssert(body)` holds.
 */
async function check(name, doFetch, assertFn) {
  try {
    const { status, body } = await doFetch();
    const verdict = assertFn(status, body);
    const ok = verdict === true;
    return { name, ok, status, detail: ok ? '' : String(verdict) };
  } catch (err) {
    return { name, ok: false, status: '000', detail: `request error: ${err.message}` };
  }
}

async function fetchText(url, init = {}) {
  const r = await fetch(url, { signal: AbortSignal.timeout(20_000), ...init });
  const body = await r.text();
  return { status: r.status, body };
}

// --- teardown state -------------------------------------------------------------------------
let pyChild = null;
let pySpawnedByUs = false; // the SHARED :9091 endpoint — killed ONLY if we spawned it
let docsChild = null;
let docsSpawnedByUs = false; // the docs app port — ALWAYS ours → always killed

function teardown() {
  if (docsSpawnedByUs && docsChild) {
    try {
      docsChild.kill('SIGKILL');
    } catch {
      /* best-effort */
    }
  }
  // Kill the shared Python endpoint ONLY if THIS run spawned it; a reused one stays up + registered
  // (other local projects sharing the dev substrate + concurrent OpenIM work depend on the shared
  // deployment).
  if (pySpawnedByUs && pyChild) {
    try {
      pyChild.kill('SIGKILL');
    } catch {
      /* best-effort */
    }
  }
}

function finish(failCount) {
  teardown();
  if (!pySpawnedByUs) {
    log('reused the shared :9091 endpoint — left bd09/agentinvestPlanner/pyTools registered + running.');
  } else {
    log('spawned :9091 for this run — torn down (registration in Restate is left intact, pointing at :9091).');
  }
  // The sentinel IS the oracle; this script's exit mirrors it.
  process.stdout.write(`OPENAPI_SMOKE_RESULT: ${failCount === 0 ? 'PASS' : 'FAIL'} rc=${failCount}\n`);
  process.exit(failCount === 0 ? 0 : 1);
}

async function main() {
  verifyMirrored();

  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: (cd ${REFERENCE_ROOT} && pnpm dev:restate). Aborting.`);
    finish(99);
    return;
  }
  if (!(await bd09Registered())) {
    log('bd09 is NOT registered in Restate. The smoke needs the registered bd09 surface. Aborting.');
    finish(98);
    return;
  }

  // Bring up :9091 reuse-safe: reuse if already serving; else spawn with --no-register (the
  // deployment is already registered pointing at :9091 — we provide the live process it expects,
  // WITHOUT re-registering or touching any sibling project's deployment on the shared substrate).
  if (await pyEndpointServing()) {
    log('the shared Python endpoint :9091 is already SERVING — reusing it (left intact on exit).');
  } else {
    log('bd09 is registered but :9091 is not serving (stale registration) — spawning the endpoint with --no-register.');
    pyChild = spawnPython(
      'import sys; sys.argv=["endpoint","--no-register"]; from agentinvest_tools.endpoint import main; main()',
      'the Python endpoint (:9091, --no-register)',
    );
    pySpawnedByUs = true;
    const up = await waitUntil(pyEndpointServing, 90_000, ':9091 serving');
    if (!up) {
      log(':9091 did not come up within the timeout. Aborting.');
      finish(97);
      return;
    }
    log(':9091 is serving (spawned by this run).');
  }

  // Spawn the docs app on DOCS_PORT (always ours). serve_docs binds 127.0.0.1:<port> and serves
  // /openapi.json + /docs + the JSON-404 over make_docs_app. It re-fetches the live bd09 spec from
  // the admin API per request (so the surface tracks the handlers — SSOT).
  docsChild = spawnPython(
    `import asyncio; from agentinvest_tools.openapi_surface import serve_docs; asyncio.run(serve_docs(port=${DOCS_PORT}))`,
    `the docs app (:${DOCS_PORT})`,
  );
  docsSpawnedByUs = true;
  const docsUp = await waitUntil(
    () => reachable(`http://localhost:${DOCS_PORT}/openapi.json`, 2500),
    60_000,
    `docs app :${DOCS_PORT} serving`,
  );
  if (!docsUp) {
    log(`docs app on :${DOCS_PORT} did not come up within the timeout. Aborting.`);
    finish(96);
    return;
  }
  log(`docs app serving on :${DOCS_PORT}.`);

  // The forwarding to the freshly-spawned :9091 can be cold on the first ingress hit; warm it.
  await fetchText(`${INGRESS_URL}/`).catch(() => undefined);

  const docsBase = `http://localhost:${DOCS_PORT}`;
  const results = [];

  // --- INGRESS: the bd09 handler operations -------------------------------------------------

  // list_capabilities is ARITY-0 — it must be POSTed with NO body and NO JSON content-type
  // (Restate rejects a non-empty body on an arity-0 handler). 200 + a catalogue naming soIds.
  results.push(
    await check(
      'ingress POST /bd09/list_capabilities (arity-0) -> 200 catalogue',
      () => fetchText(`${INGRESS_URL}/bd09/list_capabilities`, { method: 'POST' }),
      (status, body) => {
        if (status !== 200) return `expected 200, got ${status} (${body.slice(0, 160)})`;
        let parsed;
        try {
          parsed = JSON.parse(body);
        } catch {
          return `body is not JSON: ${body.slice(0, 160)}`;
        }
        const text = JSON.stringify(parsed);
        if (!text.includes('SO-09')) return `catalogue does not name an SO-09 soId: ${text.slice(0, 200)}`;
        return true;
      },
    ),
  );

  // execute_so with a VALID envelope {soId, args} -> 200 well-formed (the typed result envelope).
  results.push(
    await check(
      `ingress POST /bd09/execute_so (valid {soId:${SAMPLE_SO_ID}}) -> 200 typed result`,
      () =>
        fetchText(`${INGRESS_URL}/bd09/execute_so`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ soId: SAMPLE_SO_ID, args: VALID_SO_ARGS }),
        }),
      (status, body) => {
        if (status !== 200) return `expected 200, got ${status} (${body.slice(0, 200)})`;
        let parsed;
        try {
          parsed = JSON.parse(body);
        } catch {
          return `body is not JSON: ${body.slice(0, 160)}`;
        }
        // Well-formed typed result envelope (ExecuteSoOutput): a `result` object plus a
        // `provenance` block naming the soId it dispatched + the methodology. (The soId lives under
        // provenance — the result body is the tool's own typed output.)
        if (!parsed.result || typeof parsed.result !== 'object') {
          return `result envelope missing the typed result object (got ${JSON.stringify(parsed).slice(0, 200)})`;
        }
        if (!parsed.provenance || parsed.provenance.soId !== SAMPLE_SO_ID) {
          return `result envelope missing/mismatched provenance.soId (got ${JSON.stringify(parsed).slice(0, 200)})`;
        }
        return true;
      },
    ),
  );

  // execute_so with a MALFORMED body (a JSON string, not the {soId,...} envelope) -> a CLEAN 4xx
  // (the envelope serde rejects it as a TerminalError → 4xx; NEVER a 5xx, NEVER a silent 200).
  results.push(
    await check(
      'ingress POST /bd09/execute_so (malformed body) -> clean 4xx',
      () =>
        fetchText(`${INGRESS_URL}/bd09/execute_so`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify('i am a string, not an execute_so envelope'),
        }),
      (status, body) => {
        if (status >= 400 && status < 500) return true;
        return `expected a 4xx, got ${status} (a malformed call must be a clean 4xx, not 5xx/200): ${body.slice(0, 200)}`;
      },
    ),
  );

  // --- DOCS APP: the served OpenAPI surface + the well-formed error -------------------------

  results.push(
    await check(
      `docs GET /openapi.json -> 200 validated 3.1 spec`,
      () => fetchText(`${docsBase}/openapi.json`),
      (status, body) => {
        if (status !== 200) return `expected 200, got ${status}`;
        let parsed;
        try {
          parsed = JSON.parse(body);
        } catch {
          return `body is not JSON`;
        }
        if (parsed.openapi !== '3.1.0') return `openapi version is ${parsed.openapi}, expected 3.1.0`;
        if (!(parsed.paths && parsed.paths['/bd09/execute_so'])) return `spec missing the bd09 surface`;
        return true;
      },
    ),
  );

  results.push(
    await check(
      `docs GET /docs -> 200 Swagger UI HTML`,
      () => fetchText(`${docsBase}/docs`),
      (status, body) => {
        if (status !== 200) return `expected 200, got ${status}`;
        if (!body.includes('swagger-ui')) return `HTML does not contain the Swagger UI mount`;
        if (!body.includes('integrity=')) return `HTML missing the SRI integrity= on the CDN assets`;
        return true;
      },
    ),
  );

  // The well-formed-error check (IN #3): an unknown path -> a STRUCTURED JSON 404.
  results.push(
    await check(
      `docs GET /no-such-path -> 404 structured JSON error`,
      () => fetchText(`${docsBase}/no-such-path`),
      (status, body) => {
        if (status !== 404) return `expected 404, got ${status}`;
        let parsed;
        try {
          parsed = JSON.parse(body);
        } catch {
          return `404 body is not JSON (the well-formed-error contract): ${body.slice(0, 120)}`;
        }
        if (parsed.error !== 'not_found') return `404 JSON missing {error:"not_found"}: ${JSON.stringify(parsed)}`;
        if (typeof parsed.detail !== 'string') return `404 JSON missing a string detail: ${JSON.stringify(parsed)}`;
        return true;
      },
    ),
  );

  // --- report (mask-immune): per-check status + body assertion --------------------------------
  log('');
  log('SMOKE RESULTS (every endpoint):');
  let failCount = 0;
  for (const r of results) {
    log(`  [${r.ok ? 'PASS' : 'FAIL'}] ${r.name} (status=${r.status})${r.ok ? '' : ' — ' + r.detail}`);
    if (!r.ok) failCount += 1;
  }
  log('');
  finish(failCount);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  finish(95);
});
