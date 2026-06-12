/**
 * The DEPLOYMENTS view — read-only. Lists the registered deployments on the local engine, each
 * with its endpoint, SDK, registered services (and revisions), and the count of in-flight
 * operations this console can correlate to it. No register or rollover actions — registration and
 * version rollover are owned by the engine's CLI; this surface only reads the live topology.
 *
 * The precise per-revision version distribution of in-flight operations is shown to the extent it
 * is readable here: the in-flight (at-gate) operations are correlated to a deployment by the
 * service that hosts them. The exact per-revision pin of each in-flight operation lives behind the
 * engine's binary query surface, which this thin console does not parse — so we show the topology
 * and the correlated in-flight count, and never fabricate a distribution we cannot read.
 */
import { listDeployments } from '@/lib/restate';
import { PageHeader, OfflineBanner, Card, EmptyState } from '@/components/primitives';

export const dynamic = 'force-dynamic';

export default async function DeploymentsPage() {
  const { deployments, inFlightTotal, versionDistributionPrecise } = await listDeployments();

  return (
    <div>
      <PageHeader
        title="Deployments"
        subtitle="Registered deployments, their services, and the in-flight-operation distribution. Read-only."
      />

      {deployments.length === 0 && (
        <OfflineBanner message="No deployments are registered, or the local engine is unreachable — start the engine and register a deployment to see the topology." />
      )}

      {deployments.length > 0 && (
        <div className="mb-6 flex flex-wrap items-center gap-x-8 gap-y-2 text-sm">
          <span className="text-ink-dim">
            <span className="font-mono tabular text-ink">{deployments.length}</span> deployment
            {deployments.length === 1 ? '' : 's'}
          </span>
          <span className="text-ink-dim">
            <span className="font-mono tabular text-ink">{inFlightTotal}</span> in-flight operation
            {inFlightTotal === 1 ? '' : 's'} awaiting a decision
          </span>
        </div>
      )}

      <div className="space-y-5">
        {deployments.map((dep) => (
          <Card key={dep.id}>
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 border-b border-surface-line px-5 py-3">
              <span className="font-mono text-sm text-ink">{dep.uri}</span>
              <span className="font-mono text-xs text-ink-faint tabular">{dep.id}</span>
              {dep.sdkVersion && (
                <span className="font-mono text-[11px] text-ink-faint">{dep.sdkVersion}</span>
              )}
              <span className="ml-auto font-mono text-xs text-ink-dim tabular">
                {dep.inFlightOnDeployment} in-flight
              </span>
            </div>
            {dep.services.length === 0 ? (
              <EmptyState>No services registered on this deployment.</EmptyState>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-line text-left text-[10px] uppercase tracking-[0.15em] text-ink-faint">
                    <th className="px-5 py-2 font-medium">service</th>
                    <th className="px-5 py-2 font-medium">revision</th>
                  </tr>
                </thead>
                <tbody>
                  {dep.services.map((svc) => (
                    <tr key={svc.name} className="border-b border-surface-line last:border-b-0">
                      <td className="px-5 py-2 font-mono text-ink">{svc.name}</td>
                      <td className="px-5 py-2 font-mono tabular text-ink-dim">
                        {svc.revision === null ? '—' : `r${svc.revision}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        ))}
      </div>

      {!versionDistributionPrecise && deployments.length > 0 && (
        <p className="mt-5 text-xs leading-relaxed text-ink-faint">
          In-flight operations are correlated to a deployment by the service that hosts them. The
          exact per-revision pin of each in-flight operation is read from the engine&apos;s binary
          query surface, which this console does not parse — the per-deployment count above reflects
          the operations awaiting a decision, not a precise per-revision breakdown.
        </p>
      )}
    </div>
  );
}
