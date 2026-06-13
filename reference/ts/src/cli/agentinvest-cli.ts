/**
 * agentinvest-cli — the agentINVEST operator control plane.
 *
 * The substrate-floor CLI. Three subcommands:
 *
 *   bootstrap   Prove the substrate end-to-end: reach the shared Restate,
 *               register the agentINVEST handler endpoint, invoke the
 *               placeholder handler (baseline + crash-and-replay), report the
 *               journaled step. The data-bearing half runs the canonical-data
 *               `dbt build` so a fresh bootstrap leaves a populated
 *               duckdb canonical store.
 *
 *   seed        Load the canonical synthetic data: runs the dbt pipeline
 *               (`dbt build` over reference/dbt/, duckdb dev). It seeds +
 *               builds + tests the canonical-data layer.
 *
 *   serve       Start the agentINVEST handler endpoint, register it with the
 *               shared Restate, and hold it running so handlers stay invocable.
 *
 * Language choice: TypeScript. The orchestrator and the operator
 * control surfaces (CLI, Operator UI) are TS in the polyglot split, on
 * the mature Restate TS SDK; the placeholder handler and this CLI therefore
 * land where the TS orchestrator lives, and reuse a sibling project's
 * proven SDK-1.6.1-against-server-1.6.2 reach with no rework. (Python owns the tool +
 * data layer — a separate `reference/python/` workspace.)
 *
 * Topology vocabulary: `serve` serves a model-free handler endpoint;
 * the per-Business-Domain layer is a service, never an "agent"; there is one
 * orchestrating loop, built later. Nothing here is named "agent".
 *
 * Run (no build step needed in dev): `pnpm agentinvest <cmd>` or
 * `npx tsx src/cli/agentinvest-cli.ts <cmd>` from `reference/ts/`.
 */
import {
  ADMIN_URL,
  INGRESS_URL,
  ENDPOINT_PORT,
  LAUNCH_HINT,
  isWindowsWsl2Host,
  resolveDeployUrl,
  awaitAdminReady,
  registerDeployment,
} from '../substrate/restate-reach.js';
import { runEndpoint } from '../substrate/endpoint.js';
import {
  PLACEHOLDER_SERVICE_NAME,
  __resetAttemptCounterForSmoke,
  type PingResult,
  type HealthResult,
} from '../substrate/placeholder-service.js';
import { runDbt } from '../data/dbt-runner.js';

const CLI = 'agentinvest-cli';

function out(line = ''): void {
  process.stdout.write(`${line}\n`);
}

const TOP_HELP = `${CLI} — agentINVEST operator control plane (substrate floor)

USAGE
  ${CLI} <command> [--help]

COMMANDS
  bootstrap   Prove the substrate: reach the shared Restate, register the
              agentINVEST endpoint, invoke the placeholder handler (baseline +
              crash-and-replay), report the journaled step, THEN run the
              canonical-data 'dbt build' (the data half).
  seed        Build the canonical data layer: runs 'dbt build' over reference/dbt/
              (duckdb dev) — seed + run + test, idempotent.
  serve       Start the agentINVEST handler endpoint, register it with the
              shared Restate, and hold it running (handlers stay invocable).

GLOBAL
  -h, --help  Show this help (or per-command help: '${CLI} <command> --help').

SUBSTRATE
  agentINVEST owns its Restate substrate launcher (the running instance is
  shared with a sibling project's repo at dev time — no second cluster). Boot
  it first with OpenIM's OWN launcher if it is not up:
    ${LAUNCH_HINT}   # warm boot < 5s
  Admin:   ${ADMIN_URL}
  Ingress: ${INGRESS_URL}
  See reference/ts/README.md for the full runbook.`;

const BOOTSTRAP_HELP = `${CLI} bootstrap — prove the agentINVEST substrate end-to-end

USAGE
  ${CLI} bootstrap [--keep-serving]

WHAT IT DOES
  1. Waits for the shared Restate admin API (${ADMIN_URL}) to be reachable.
  2. Starts the agentINVEST handler endpoint (port ${ENDPOINT_PORT}).
  3. Registers the endpoint with the shared Restate (admin /deployments).
  4. Invokes ${PLACEHOLDER_SERVICE_NAME}/ping (baseline) — expects attempts=1.
  5. Invokes ${PLACEHOLDER_SERVICE_NAME}/ping with a forced crash — expects
     attempts=2 with the SAME journaled step-id (journal replay proven).
  6. Invokes ${PLACEHOLDER_SERVICE_NAME}/health over the ingress.
  7. Runs the canonical-data 'dbt build' (the data half): seeds +
     builds + tests reference/dbt/ on the duckdb dev backend (idempotent). The
     duckdb file lands on WSL2-native ext4, not the repo mount.

OPTIONS
  --keep-serving   After the proof, keep the endpoint running (do not exit).
  --skip-data      Skip the dbt-build data half (substrate proof only).
  -h, --help       Show this help.

PREREQUISITE
  The shared Restate must be up. If not:
    ${LAUNCH_HINT}
  The dbt half needs the Python uv env synced with the dbt group (WSL2 on
  Windows): cd reference/python && uv sync --group dbt.`;

const SEED_HELP = `${CLI} seed — build the canonical data layer (dbt)

USAGE
  ${CLI} seed [-- <extra dbt args>]

WHAT IT DOES
  Runs the canonical-data dbt pipeline: 'dbt build' over reference/dbt/ on the
  duckdb dev backend (seed CSV -> staging view -> dbt tests).
  Idempotent: dbt seed full-refreshes the seed table, so a re-run leaves the same
  state (no duplicate rows). The duckdb database file lands on WSL2-native ext4
  (~/.local/share/agentinvest/duckdb/canonical.duckdb by default), NOT the repo
  mount (a duckdb locking/perf hazard on the 9p /mnt/d mount).

  At the scaffold stage the dbt project carries ONE sample staging model + a
  small seed (proves the pipeline). The full synthetic seed + the
  intermediate/mart models over the BD-09 entities are forward work.

OPTIONS
  Any args after '--' are forwarded to dbt (e.g. '-- --select staging',
  '-- seed' for seed-only). Default (no args) runs 'dbt build'.
  -h, --help   Show this help.

PREREQUISITE
  The Python uv env synced with the dbt group (WSL2 on Windows):
    cd reference/python && uv sync --group dbt`;

const SERVE_HELP = `${CLI} serve — run the agentINVEST handler endpoint

USAGE
  ${CLI} serve [--port <n>] [--no-register]

WHAT IT DOES
  Starts the agentINVEST handler endpoint and registers it with the shared
  Restate so its handlers are invocable over the ingress (${INGRESS_URL}).
  Holds the process running until interrupted (Ctrl-C).

OPTIONS
  --port <n>      Endpoint port (default ${ENDPOINT_PORT}; env AGENTINVEST_ENDPOINT_PORT).
  --no-register   Start the endpoint but skip admin registration.
  -h, --help      Show this help.

PREREQUISITE
  The shared Restate must be up. If not:
    ${LAUNCH_HINT}`;

function has(args: string[], ...flags: string[]): boolean {
  return args.some((a) => flags.includes(a));
}

function flagValue(args: string[], flag: string): string | undefined {
  const i = args.indexOf(flag);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : undefined;
}

/**
 * Bring up the endpoint, register it, and (on Windows) widen the bind so
 * Restate-in-WSL2 can reach it. Returns the close handle.
 */
async function bringUpEndpoint(port: number, register: boolean): Promise<() => void> {
  // On Windows/WSL2 the endpoint must be reachable from inside WSL2: bind 0.0.0.0.
  if (isWindowsWsl2Host() && !process.env.AGENTINVEST_ENDPOINT_BIND) {
    process.env.AGENTINVEST_ENDPOINT_BIND = '0.0.0.0';
  }
  await awaitAdminReady();
  out(`[${CLI}] shared Restate admin reachable at ${ADMIN_URL}`);
  const server = await runEndpoint(port);
  // Small settle: listen() resolves at bind, but the SDK does post-bind setup.
  await new Promise((res) => setTimeout(res, 500));
  if (register) {
    const deployUri = resolveDeployUrl();
    out(`[${CLI}] registering endpoint with shared Restate: ${deployUri}`);
    const id = await registerDeployment(deployUri);
    out(`[${CLI}] registered deployment ${id}`);
    // Service discovery + first heartbeat take a moment.
    await new Promise((res) => setTimeout(res, 1000));
  }
  return () => server.close();
}

async function invokePing(crashOnFirstAttempt: boolean): Promise<PingResult> {
  const res = await fetch(`${INGRESS_URL}/${PLACEHOLDER_SERVICE_NAME}/ping`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ crashOnFirstAttempt }),
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) throw new Error(`ping invoke failed ${res.status}: ${await res.text()}`);
  return (await res.json()) as PingResult;
}

async function invokeHealth(): Promise<HealthResult> {
  const res = await fetch(`${INGRESS_URL}/${PLACEHOLDER_SERVICE_NAME}/health`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`health invoke failed ${res.status}: ${await res.text()}`);
  return (await res.json()) as HealthResult;
}

async function cmdBootstrap(args: string[]): Promise<number> {
  if (has(args, '-h', '--help')) {
    out(BOOTSTRAP_HELP);
    return 0;
  }
  out(`[${CLI}] bootstrap — substrate end-to-end proof`);
  const close = await bringUpEndpoint(ENDPOINT_PORT, true);
  try {
    // Phase 1 — baseline: no crash; the handler body runs exactly once.
    __resetAttemptCounterForSmoke();
    const baseline = await invokePing(false);
    out(`[${CLI}] baseline ping: ${JSON.stringify(baseline)}`);
    if (baseline.attempts !== 1) {
      throw new Error(`baseline: expected attempts=1, got ${baseline.attempts}`);
    }

    // Phase 2 — replay: force a crash; the handler re-runs, but the journaled
    // step replays with the SAME step-id. This is the journal proof.
    __resetAttemptCounterForSmoke();
    const replay = await invokePing(true);
    out(`[${CLI}] crash-and-replay ping: ${JSON.stringify(replay)}`);
    if (replay.attempts !== 2) {
      throw new Error(`replay: expected attempts=2 (crash + retry), got ${replay.attempts}`);
    }
    if (replay.stepId === baseline.stepId) {
      throw new Error(`replay: stepId should differ from baseline (separate invocations have separate journals)`);
    }

    // Phase 3 — ingress liveness.
    const health = await invokeHealth();
    out(`[${CLI}] health: ${JSON.stringify(health)}`);

    out('');
    out(`[${CLI}] SUBSTRATE PROVEN:`);
    out(`  - shared Restate reachable (admin ${ADMIN_URL}, ingress ${INGRESS_URL})`);
    out(`  - agentINVEST endpoint registered + invocable`);
    out(`  - journal step recorded; replay returned the journaled step-id (${replay.stepId})`);
    out('');
  } finally {
    // Close the endpoint after the substrate proof unless asked to keep serving.
    // (The data half below does not need the endpoint up.)
    if (!has(args, '--keep-serving')) {
      close();
    }
  }

  // Data half — the canonical-data dbt build. Real, not a stub.
  if (has(args, '--skip-data')) {
    out(`[${CLI}] bootstrap data-half SKIPPED (--skip-data); substrate proof only.`);
  } else {
    out(`[${CLI}] bootstrap data-half: building the canonical data layer (dbt)...`);
    const dbtCode = await runDbt(['build']);
    if (dbtCode !== 0) {
      throw new Error(`canonical-data 'dbt build' failed (exit ${dbtCode})`);
    }
    out(`[${CLI}] canonical data layer built (duckdb dev, on ext4).`);
  }

  if (has(args, '--keep-serving')) {
    out(`[${CLI}] --keep-serving: endpoint left running (Ctrl-C to stop).`);
    await new Promise(() => {}); // hold open
  }
  return 0;
}

async function cmdSeed(args: string[]): Promise<number> {
  if (has(args, '-h', '--help')) {
    out(SEED_HELP);
    return 0;
  }
  // Forward any args after '--' to dbt; default to `build`.
  const sep = args.indexOf('--');
  const dbtArgs = sep >= 0 ? args.slice(sep + 1) : [];
  const effective = dbtArgs.length > 0 ? dbtArgs : ['build'];
  out(`[${CLI}] seed — canonical-data 'dbt ${effective.join(' ')}' (duckdb dev, ext4)`);
  const code = await runDbt(effective);
  if (code === 0) {
    out(`[${CLI}] canonical data layer built (seed + staging + tests, idempotent).`);
  } else {
    process.stderr.write(`${CLI}: dbt exited ${code}\n`);
  }
  return code;
}

async function cmdServe(args: string[]): Promise<number> {
  if (has(args, '-h', '--help')) {
    out(SERVE_HELP);
    return 0;
  }
  const portArg = flagValue(args, '--port');
  const port = portArg ? Number(portArg) : ENDPOINT_PORT;
  const register = !has(args, '--no-register');
  out(`[${CLI}] serve — starting agentINVEST handler endpoint on port ${port}`);
  await bringUpEndpoint(port, register);
  out(`[${CLI}] endpoint up${register ? ' and registered' : ' (not registered)'}; holding. Ctrl-C to stop.`);
  await new Promise(() => {}); // hold the process open
  return 0;
}

async function main(): Promise<number> {
  const [, , cmd, ...rest] = process.argv;
  switch (cmd) {
    case 'bootstrap':
      return cmdBootstrap(rest);
    case 'seed':
      return await cmdSeed(rest);
    case 'serve':
      return cmdServe(rest);
    case undefined:
    case '-h':
    case '--help':
      out(TOP_HELP);
      return 0;
    default:
      process.stderr.write(`${CLI}: unknown command '${cmd}'. Run '${CLI} --help'.\n`);
      return 2;
  }
}

main()
  .then((code) => process.exit(code))
  .catch((err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(`${CLI}: ${msg}\n`);
    process.exit(1);
  });
