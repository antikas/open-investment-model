/**
 * The APPROVALS QUEUE — the load-bearing surface. Lists the high-stakes approvals
 * awaiting an operator decision (a REAL data source: each row is a live operation or
 * NAV strike paused at the gate), and lets the operator approve (proceed) or reject
 * (abort, no publish) with a reason. The decision is recorded at the awakeable on the
 * server — the gate's own path of record.
 *
 * Server-rendered: the pending list is fetched on the server from the local engine; the
 * browser receives only the rendered rows + the small approve/reject form.
 */
import { listApprovals, agentinvestRegistered } from '@/lib/restate';
import { PageHeader, OfflineBanner, Card, EmptyState, StatusPill } from '@/components/primitives';
import { ApprovalRow } from './ApprovalRow';

// Always read the live state — no static caching of a fiduciary queue.
export const dynamic = 'force-dynamic';

export default async function ApprovalsPage() {
  const registered = await agentinvestRegistered();
  const { pending, resolved } = await listApprovals();

  return (
    <div>
      <PageHeader
        title="Approvals queue"
        subtitle="High-stakes operations paused for an operator decision. Approve to proceed; reject to abort (no publish)."
      />

      {!registered && (
        <OfflineBanner message="The agentINVEST handlers are not registered on the local engine — start the endpoint to see live approvals." />
      )}

      <Card>
        {pending.length === 0 ? (
          <EmptyState>
            No approvals awaiting a decision. A high-stakes operation (e.g. a NAV publish) pauses here when
            it reaches the gate.
          </EmptyState>
        ) : (
          pending.map((a) => <ApprovalRow key={a.operationId} approval={a} />)
        )}
      </Card>

      {resolved.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 font-mono text-xs uppercase tracking-[0.18em] text-ink-faint">Recently decided</h2>
          <Card>
            {resolved.slice(0, 12).map((a) => (
              <div
                key={a.operationId}
                className="flex flex-wrap items-center gap-x-6 gap-y-1 border-b border-surface-line last:border-b-0 px-5 py-3 text-sm"
              >
                <span className="font-mono tabular text-ink-dim">{a.operationId}</span>
                <StatusPill status={a.decision ?? 'resolved'} />
                <span className="font-mono text-xs text-ink-faint tabular">{a.awakeableId}</span>
                {a.summary && <span className="text-ink-dim truncate max-w-md">{a.summary}</span>}
                {a.resolvedAt && (
                  <span className="ml-auto text-xs text-ink-faint">{new Date(a.resolvedAt).toLocaleString()}</span>
                )}
              </div>
            ))}
          </Card>
        </section>
      )}
    </div>
  );
}
