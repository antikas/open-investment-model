/**
 * One operation's AUDIT TRAIL — read-only. Renders the recorded state of an operation
 * or NAV strike: the lifecycle status, the plan + resolved args + step results +
 * aggregate + gate decision (the `operation-closed` audit record), or the NAV
 * strike's step checkpoints + publish record. The raw record is shown verbatim so the
 * operator reads exactly what was journaled. No mutation.
 */
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getOperation } from '@/lib/restate';
import { PageHeader, Card, Field, StatusPill } from '@/components/primitives';

export const dynamic = 'force-dynamic';

export default async function OperationDetailPage({
  params,
}: {
  params: Promise<{ kind: string; operationId: string }>;
}) {
  const { kind, operationId } = await params;
  const decodedId = decodeURIComponent(operationId);
  const state = await getOperation(kind, decodedId);
  if (!state) notFound();

  const status = typeof state.status === 'string' ? state.status : 'unknown';
  const audit = state.auditRecord as Record<string, unknown> | undefined;
  const publish = state.publishRecord as Record<string, unknown> | undefined;

  return (
    <div>
      <Link href="/operations" className="font-mono text-xs text-ink-dim hover:text-ink">
        ← Operations
      </Link>
      <div className="mt-2">
        <PageHeader title={decodedId} subtitle={`${kind} — recorded audit trail`} />
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-6">
        <Field label="status" value={<StatusPill status={status} />} mono={false} />
        <Field label="kind" value={kind} />
      </div>

      {audit && (
        <section className="mb-6">
          <h2 className="mb-3 font-mono text-xs uppercase tracking-[0.18em] text-ink-faint">
            operation-closed audit record
          </h2>
          <Card>
            <RecordBlock record={audit} />
          </Card>
        </section>
      )}

      {publish && (
        <section className="mb-6">
          <h2 className="mb-3 font-mono text-xs uppercase tracking-[0.18em] text-ink-faint">NAV publish record</h2>
          <Card>
            <RecordBlock record={publish} />
          </Card>
        </section>
      )}

      <section>
        <h2 className="mb-3 font-mono text-xs uppercase tracking-[0.18em] text-ink-faint">recorded state (verbatim)</h2>
        <Card>
          <pre className="overflow-x-auto px-5 py-4 font-mono text-xs leading-relaxed text-ink-dim tabular">
            {JSON.stringify(state, null, 2)}
          </pre>
        </Card>
      </section>
    </div>
  );
}

/** Render the top-level scalar fields of a record as labelled fields; nested objects as JSON. */
function RecordBlock({ record }: { record: Record<string, unknown> }) {
  const entries = Object.entries(record);
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-4 px-5 py-4">
      {entries.map(([key, value]) => (
        <Field
          key={key}
          label={key}
          value={
            value !== null && typeof value === 'object' ? (
              <span className="text-ink-dim">{summarise(value)}</span>
            ) : (
              String(value)
            )
          }
        />
      ))}
    </div>
  );
}

/** A compact one-line summary of a nested value (count for arrays, key-count for objects). */
function summarise(value: object): string {
  if (Array.isArray(value)) return `[${value.length} item${value.length === 1 ? '' : 's'}]`;
  return `{${Object.keys(value).length} field${Object.keys(value).length === 1 ? '' : 's'}}`;
}
