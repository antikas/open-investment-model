'use client';

/**
 * One pending-approval row with the approve/reject controls. A client component only
 * for the small interaction (a reason field + two submit buttons that post to the
 * server actions); the data was fetched server-side and passed in as props. The
 * action runs on the server — the awakeable is resolved there, never from the browser.
 */
import { useState, useTransition } from 'react';
import type { PendingApproval } from '@/lib/restate';
import { approve, reject } from './actions';
import { RiskChip, Field } from '@/components/primitives';

export function ApprovalRow({ approval }: { approval: PendingApproval }) {
  const [reason, setReason] = useState('');
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function submit(action: (fd: FormData) => Promise<void>) {
    const fd = new FormData();
    fd.set('operationId', approval.operationId);
    fd.set('awakeableId', approval.awakeableId);
    fd.set('origin', approval.origin);
    fd.set('reason', reason);
    setError(null);
    startTransition(async () => {
      try {
        await action(fd);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    });
  }

  return (
    <div className="border-b border-surface-line last:border-b-0 px-5 py-4">
      <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
        <Field label="operation" value={approval.operationId} />
        <Field label="awakeable" value={approval.awakeableId} />
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase tracking-[0.15em] text-ink-faint">risk</span>
          <RiskChip riskScore={approval.riskScore} threshold={approval.threshold} />
        </div>
        <Field label="origin" value={approval.origin} />
        <Field label="steps" value={approval.stepCount} />
        <Field label="raised" value={new Date(approval.raisedAt).toLocaleString()} mono={false} />
      </div>

      {approval.summary && (
        <p className="mt-3 text-sm text-ink-dim">
          <span className="text-ink">{approval.summary}</span>
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="reason (recorded on the decision)"
          className="flex-1 min-w-[16rem] rounded border border-surface-line bg-surface px-3 py-1.5 font-mono text-sm text-ink placeholder:text-ink-faint focus:border-amber-signal/50 focus:outline-none"
        />
        <button
          type="button"
          disabled={pending}
          onClick={() => submit(approve)}
          className="rounded border border-approve/50 bg-approve/10 px-4 py-1.5 font-mono text-sm text-approve hover:bg-approve/20 disabled:opacity-50 transition-colors"
        >
          {pending ? '…' : 'Approve → proceed'}
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={() => submit(reject)}
          className="rounded border border-reject/50 bg-reject/10 px-4 py-1.5 font-mono text-sm text-reject hover:bg-reject/20 disabled:opacity-50 transition-colors"
        >
          {pending ? '…' : 'Reject → abort'}
        </button>
      </div>

      {error && <p className="mt-2 font-mono text-xs text-reject">{error}</p>}
    </div>
  );
}
