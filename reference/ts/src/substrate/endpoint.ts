/**
 * agentINVEST handler endpoint.
 *
 * Hosts the agentINVEST Restate handlers (the placeholder service + the
 * `InvestmentOperation` orchestrator virtual object) and listens for Restate's
 * invocation callbacks. The
 * shared Restate instance (run by a sibling project sharing the dev substrate)
 * reaches this endpoint at the URL
 * resolved by `restate-reach.ts` and registered via its admin API.
 *
 * Bind host: defaults to 127.0.0.1 (loopback-only — never the LAN). On a
 * Windows/WSL2 host the `serve` path widens the bind to 0.0.0.0 so that
 * Restate-inside-WSL2 can reach this listener at the Windows-host gateway IP
 * (the same shape a sibling project's runtime uses). The exposure is dev-only and the
 * handler surface here is a no-op placeholder.
 *
 * More handlers bind here (the orchestrator virtual
 * object, the per-BD services, the typed tool surface). This file is the seam:
 * future handlers are added to the `.bind(...)` chain. The CLI's `serve`
 * subcommand calls `runEndpoint`.
 */
import { createServer, type Http2Server } from 'node:http2';
import { endpoint } from '@restatedev/restate-sdk';
import { placeholderService } from './placeholder-service.js';
import { investmentOperation } from '../orchestrator/investment-operation.js';
import { navCalculation } from '../orchestrator/nav-calculation-workflow.js';
import { approvalRegistry, approvalRegistryReader } from '../orchestrator/approval-registry.js';
import { auditJournalExport } from '../audit/audit-journal-export-handler.js';
import { ENDPOINT_PORT } from './restate-reach.js';

const DEFAULT_BIND = '127.0.0.1';

/**
 * Start the agentINVEST handler endpoint and return the bound server.
 *
 * @param port  TCP port to listen on (default: the resolved ENDPOINT_PORT).
 * @param bind  Bind host. Default 127.0.0.1. Pass '0.0.0.0' on Windows/WSL2
 *              so Restate-in-WSL2 can reach it (the `serve` CLI path does this).
 */
export async function runEndpoint(
  port: number = ENDPOINT_PORT,
  bind: string = process.env.AGENTINVEST_ENDPOINT_BIND ?? DEFAULT_BIND,
): Promise<Http2Server> {
  const e = endpoint()
    .bind(placeholderService)
    .bind(investmentOperation)
    .bind(navCalculation)
    .bind(approvalRegistry)
    .bind(approvalRegistryReader)
    .bind(auditJournalExport);
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
  process.stderr.write(`[agentinvest-endpoint] listening on ${bind}:${port}\n`);
  return server;
}
