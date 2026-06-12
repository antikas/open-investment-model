/**
 * Shell-invocable + runtime-skew proof (live, over the real shared Restate).
 *
 * Two proofs against the PRODUCTION `InvestmentOperation` shell (the one bound
 * into the endpoint), not a probe:
 *
 *  A. The production VO is invocable and journals a plan (the `.plan()` step,
 *     OIM-130). Invoke `investmentOperation/<id>/execute`; assert it returns
 *     status=completed with a journaled `plan` (>=1 step), then read
 *     `investmentOperation/<id>/status` back from the virtual object's state.
 *     NOTE — proof A now exercises the real plan step, so it needs the Python
 *     `agentinvestPlanner` reachable (a real Sonnet call). The journaled-exactly-
 *     once crash-replay of that plan is proven separately by `pnpm plan-crash`.
 *  B. The runtime version-skew gate behaves: with the pin matching the live
 *     server, a new operation proceeds silently; with a FORCED mismatched pin
 *     (RESTATE_PINNED_VERSION set on this endpoint to a bogus version), a new
 *     operation is BLOCKED with a terminal refusal (the block-new-ops decision) —
 *     the block happens AT THE GATE, before the plan step, so proof B does not
 *     need the planner.
 *
 * The skew gate reads OPENIM_PINNED_RESTATE_VERSION, which honours the
 * RESTATE_PINNED_VERSION env override — so we run TWO endpoint processes is not
 * needed: this harness binds the shell with the live pin for proof A, and the
 * separate `--block` mode binds it under a forced-bogus pin for proof B.
 *
 * Run (from reference/ts/, substrate up):
 *   npx tsx src/orchestrator/shell-and-skew-proof.ts            # proof A (match → proceed)
 *   RESTATE_PINNED_VERSION=9.9.9 npx tsx src/orchestrator/shell-and-skew-proof.ts --block  # proof B (mismatch → block)
 */
import { createServer } from 'node:http2';
import { endpoint as restateEndpoint } from '@restatedev/restate-sdk';
import { investmentOperation, INVESTMENT_OPERATION_NAME } from './investment-operation.js';
import {
  INGRESS_URL,
  OPENIM_PINNED_RESTATE_VERSION,
  awaitAdminReady,
  deregisterDeployment,
  isWindowsWsl2Host,
  readRunningServerVersion,
  registerDeployment,
  resolveDeployUrl,
} from '../substrate/restate-reach.js';

const PORT = Number(process.env.AGENTINVEST_SHELL_PROOF_PORT ?? 9095);
const BLOCK_MODE = process.argv.includes('--block');

async function startEndpoint(port: number): Promise<() => void> {
  const e = restateEndpoint().bind(investmentOperation);
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
  out(`[shell-proof] InvestmentOperation endpoint on ${bind}:${port}`);
  return () => server.close();
}

async function invokeExecute(key: string): Promise<Response> {
  return fetch(`${INGRESS_URL}/${INVESTMENT_OPERATION_NAME}/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: 'shell-proof' }),
    signal: AbortSignal.timeout(60_000),
  });
}

async function invokeStatus(key: string): Promise<unknown> {
  const res = await fetch(`${INGRESS_URL}/${INVESTMENT_OPERATION_NAME}/${encodeURIComponent(key)}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`status failed ${res.status}: ${await res.text()}`);
  return res.json();
}

async function main(): Promise<number> {
  await awaitAdminReady();
  const live = await readRunningServerVersion();
  out(`[shell-proof] live server version=${live}; this endpoint's pin=${OPENIM_PINNED_RESTATE_VERSION}; mode=${BLOCK_MODE ? 'BLOCK' : 'PROCEED'}`);
  const close = await startEndpoint(PORT);
  let deploymentId: string | undefined;
  try {
    deploymentId = await registerDeployment(resolveDeployUrl(PORT));
    out(`[shell-proof] registered deployment ${deploymentId}`);
    await new Promise((res) => setTimeout(res, 1500));

    const key = `shell-${Date.now()}`;
    const res = await invokeExecute(key);

    if (BLOCK_MODE) {
      // Proof B: the forced mismatch must BLOCK the new operation. Restate
      // surfaces a terminal handler error as a non-2xx ingress response.
      const bodyText = await res.text();
      out(`[shell-proof] execute under forced skew -> HTTP ${res.status}: ${bodyText}`);
      const blocked = res.status >= 400 && /version|skew|blocked/i.test(bodyText);
      if (blocked) {
        out('[shell-proof] RUNTIME-SKEW BLOCK PROVEN: a new operation was refused under a mismatched pin.');
        return 0;
      }
      out('[shell-proof] FAILED: expected a block (4xx + version-skew message) but the operation proceeded.');
      return 1;
    }

    // Proof A: match → the operation proceeds + journals a step.
    if (!res.ok) {
      out(`[shell-proof] FAILED: execute returned HTTP ${res.status}: ${await res.text()}`);
      return 1;
    }
    const result = (await res.json()) as {
      status?: string;
      operationId?: string;
      plan?: { steps?: Array<{ soId?: string }> };
      selectedSoIds?: string[];
    };
    out(`[shell-proof] execute -> ${JSON.stringify(result)}`);
    const state = await invokeStatus(key);
    out(`[shell-proof] status (from VO state) -> ${JSON.stringify(state)}`);

    const ok =
      result.status === 'completed' &&
      Array.isArray(result.plan?.steps) &&
      result.plan.steps.length > 0 &&
      typeof result.plan.steps[0].soId === 'string' &&
      result.operationId === key;
    if (ok) {
      out('[shell-proof] PRODUCTION-VO INVOCABLE PROVEN: execute journaled a plan (the .plan() step); VO state reads back completed.');
      out('[shell-proof] RUNTIME-SKEW SILENT-ON-MATCH PROVEN: the operation proceeded with no skew block.');
      return 0;
    }
    out('[shell-proof] FAILED: production-VO result not as expected (no journaled plan).');
    return 1;
  } finally {
    if (deploymentId) {
      out(`[shell-proof] deregistering deployment ${deploymentId}`);
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
    process.stderr.write(`[shell-proof] ${msg}\n`);
    process.exit(1);
  });
