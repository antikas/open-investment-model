/**
 * Cross-language RPC smoke test — the load-bearing proof of the TS↔Python seam.
 *
 * Proves a TypeScript handler invokes a Python handler over Restate's TYPED RPC,
 * the payload round-tripping as a typed structure, from a fresh checkout.
 *
 * The shape (TS calls Python):
 *  1. A thin TS orchestrator service (`tsOrchestratorSmoke`) is defined here. Its
 *     `runReturnViaPython` handler does NOT compute anything itself — it calls
 *     `ctx.serviceClient(PY_TOOLS).computeSimpleReturn(input)`, i.e. it dispatches
 *     to the Python `pyTools` service over Restate's service-to-service path.
 *     The call is fully typed on the TS side via the shared contract
 *     (py-tools-contract.ts); the implementation lives in Python.
 *  2. Both endpoints are registered against the one shared Restate:
 *     - the Python endpoint (pyTools) — started separately, inside WSL2 (the
 *       smoke runner starts it via uv before invoking), on its own port;
 *     - this TS orchestrator endpoint — started here, on its own port.
 *  3. The smoke invokes `tsOrchestratorSmoke/runReturnViaPython` over the ingress.
 *     That handler reaches into Python, gets the typed result, and returns it.
 *  4. We assert the result was `computedBy: 'python:pyTools'` and the maths is
 *     correct — proving the call genuinely crossed the TS→Python boundary (a
 *     same-language shortcut could never set `computedBy` to the Python marker,
 *     and the Python service is the only thing that can compute it).
 *
 * This is genuine cross-language typed RPC over the durable substrate — the call
 * goes through Restate's own service-to-service routing, journaled like any
 * step. It is NOT an HTTP shim and NOT a same-language fake.
 *
 * Run (from reference/ts/, with the substrate up and the Python endpoint served):
 *   pnpm smoke:rpc
 * The orchestrating run command that starts everything from a fresh checkout is
 * `reference/scripts/smoke-cross-language.mjs` (see reference/ts/README.md).
 */
import { createServer } from 'node:http2';
import { endpoint as restateEndpoint, service, type Context } from '@restatedev/restate-sdk';
import {
  ADMIN_URL,
  INGRESS_URL,
  awaitAdminReady,
  deregisterDeployment,
  isWindowsWsl2Host,
  registerDeployment,
  resolveDeployUrl,
} from '../substrate/restate-reach.js';
import { PY_TOOLS, type SimpleReturnInput, type SimpleReturnResult } from './py-tools-contract.js';

const TS_ORCHESTRATOR_SMOKE_NAME = 'tsOrchestratorSmoke';
// A port distinct from the floor's TS endpoint (9090) and the Python endpoint
// (9091) so this smoke's own TS endpoint does not clash with either.
const SMOKE_TS_PORT = Number(process.env.AGENTINVEST_SMOKE_TS_PORT ?? 9092);

/**
 * The thin TS orchestrator service whose handler crosses into Python. This is
 * the model-free service shape the real orchestrator extends; here it does
 * nothing but dispatch to the Python tool over typed RPC.
 */
const tsOrchestratorSmoke = service({
  name: TS_ORCHESTRATOR_SMOKE_NAME,
  handlers: {
    async runReturnViaPython(ctx: Context, input: SimpleReturnInput): Promise<SimpleReturnResult> {
      // THE CROSS-LANGUAGE CALL: typed on the TS side via PY_TOOLS, routed by
      // Restate to the Python `pyTools` service. The result type is the shared
      // contract's SimpleReturnResult — typed end to end.
      const result = await ctx.serviceClient(PY_TOOLS).computeSimpleReturn(input);
      return result;
    },
  },
});

async function startTsEndpoint(port: number): Promise<() => void> {
  const e = restateEndpoint().bind(tsOrchestratorSmoke);
  const bind = isWindowsWsl2Host() ? '0.0.0.0' : '127.0.0.1';
  const server = createServer(e.http2Handler());
  await new Promise<void>((resolve, reject) => {
    const onError = (err: Error): void => {
      server.off('error', onError);
      reject(err);
    };
    server.once('error', onError);
    server.listen({ port, host: bind }, () => {
      server.off('error', onError);
      resolve();
    });
  });
  process.stderr.write(`[cross-language-smoke] TS orchestrator endpoint on ${bind}:${port}\n`);
  return () => server.close();
}

async function invokeViaIngress(input: SimpleReturnInput): Promise<SimpleReturnResult> {
  const res = await fetch(`${INGRESS_URL}/${TS_ORCHESTRATOR_SMOKE_NAME}/runReturnViaPython`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) {
    throw new Error(`invoke failed ${res.status}: ${await res.text()}`);
  }
  return (await res.json()) as SimpleReturnResult;
}

async function main(): Promise<number> {
  out('[cross-language-smoke] TS → Python typed RPC over Restate');
  await awaitAdminReady();
  out(`[cross-language-smoke] shared Restate admin reachable at ${ADMIN_URL}`);

  const close = await startTsEndpoint(SMOKE_TS_PORT);
  let deploymentId: string | undefined;
  try {
    // Register THIS TS orchestrator endpoint. (The Python pyTools endpoint is
    // registered separately by its own serve path, before this runs.)
    const deployUri = resolveDeployUrl(SMOKE_TS_PORT);
    out(`[cross-language-smoke] registering TS orchestrator endpoint: ${deployUri}`);
    deploymentId = await registerDeployment(deployUri);
    out(`[cross-language-smoke] registered deployment ${deploymentId}`);
    await new Promise((res) => setTimeout(res, 1500));

    // 100 begin + 50 contribution -> 165 end. Expected simple return = 0.10.
    const input: SimpleReturnInput = { beginningValue: 100, endingValue: 165, cashFlow: 50 };
    out(`[cross-language-smoke] TS invokes ${TS_ORCHESTRATOR_SMOKE_NAME}/runReturnViaPython ${JSON.stringify(input)}`);
    const result = await invokeViaIngress(input);
    out(`[cross-language-smoke] round-trip result: ${JSON.stringify(result)}`);

    // ASSERT the boundary was genuinely crossed.
    if (result.computedBy !== 'python:pyTools') {
      throw new Error(
        `BOUNDARY NOT CROSSED: computedBy='${result.computedBy}', expected 'python:pyTools'. ` +
          `The Python service is the only thing that can set this marker.`,
      );
    }
    const expected = (165 - 100 - 50) / (100 + 50); // 0.10
    if (Math.abs(result.simpleReturn - expected) > 1e-9) {
      throw new Error(`WRONG RESULT: got ${result.simpleReturn}, expected ${expected}`);
    }
    if (
      result.echo.beginningValue !== input.beginningValue ||
      result.echo.endingValue !== input.endingValue ||
      result.echo.cashFlow !== input.cashFlow
    ) {
      throw new Error(`ECHO MISMATCH: ${JSON.stringify(result.echo)} != ${JSON.stringify(input)}`);
    }

    out('');
    out('[cross-language-smoke] CROSS-LANGUAGE RPC PROVEN:');
    out('  - TS orchestrator handler invoked the Python pyTools service over Restate typed RPC');
    out(`  - the typed payload round-tripped (computedBy=${result.computedBy}, simpleReturn=${result.simpleReturn})`);
    out('  - the boundary is genuine: only the Python service can set computedBy=python:pyTools');
    return 0;
  } finally {
    // Deregister this short-lived endpoint from the SHARED journal before the
    // listener closes, so the smoke does not leave a dead-port orphan.
    if (deploymentId) {
      out(`[cross-language-smoke] deregistering deployment ${deploymentId}`);
      await deregisterDeployment(deploymentId);
    }
    close();
  }
}

function out(line = ''): void {
  process.stdout.write(`${line}\n`);
}

main()
  .then((code) => process.exit(code))
  .catch((err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(`[cross-language-smoke] ${msg}\n`);
    process.exit(1);
  });
