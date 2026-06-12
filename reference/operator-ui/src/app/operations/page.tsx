/**
 * The OPERATIONS DASHBOARD — read-only. Lists the operations the local engine has run
 * (in-flight + completed `investmentOperation`s and `navCalculation` strikes) with
 * their lifecycle status, and links each to its recorded audit trail (the OIM-134
 * `operation-closed` record / the NAV publish record). No mutation — an operator reads
 * the audit trail here; the decision surface is the Approvals queue.
 */
import Link from 'next/link';
import { listOperations, agentinvestRegistered } from '@/lib/restate';
import { PageHeader, OfflineBanner, Card, EmptyState, StatusPill } from '@/components/primitives';

export const dynamic = 'force-dynamic';

export default async function OperationsPage() {
  const registered = await agentinvestRegistered();
  const operations = await listOperations();

  return (
    <div>
      <PageHeader
        title="Operations"
        subtitle="In-flight and completed operations, with the recorded audit trail. Read-only."
      />

      {!registered && (
        <OfflineBanner message="The agentINVEST handlers are not registered on the local engine — start the endpoint to see operations." />
      )}

      <Card>
        {operations.length === 0 ? (
          <EmptyState>
            No operations recorded yet. Running an operation or striking a NAV records an audit trail readable
            here.
          </EmptyState>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-line text-left text-[10px] uppercase tracking-[0.15em] text-ink-faint">
                <th className="px-5 py-3 font-medium">operation</th>
                <th className="px-5 py-3 font-medium">kind</th>
                <th className="px-5 py-3 font-medium">status</th>
                <th className="px-5 py-3 font-medium">summary</th>
                <th className="px-5 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {operations.map((op) => (
                <tr key={`${op.kind}:${op.operationId}`} className="border-b border-surface-line last:border-b-0">
                  <td className="px-5 py-3 font-mono tabular text-ink">{op.operationId}</td>
                  <td className="px-5 py-3 font-mono text-xs text-ink-dim">{op.kind}</td>
                  <td className="px-5 py-3">
                    <StatusPill status={op.status} />
                  </td>
                  <td className="px-5 py-3 text-ink-dim max-w-md truncate">{op.summary ?? '—'}</td>
                  <td className="px-5 py-3 text-right">
                    <Link
                      href={`/operations/${op.kind}/${encodeURIComponent(op.operationId)}`}
                      className="font-mono text-xs text-amber-signal hover:underline"
                    >
                      audit trail →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
