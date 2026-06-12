/** Shared presentational primitives for the operator console — server components, no client JS. */
import type { ReactNode } from 'react';

/** A page header: a title + a one-line subtitle describing what the surface shows. */
export function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="mb-6">
      <h1 className="font-mono text-lg font-semibold tracking-tight text-ink">{title}</h1>
      <p className="mt-1 text-sm text-ink-dim">{subtitle}</p>
    </div>
  );
}

/** A connectivity banner — shown when the local engine / agentINVEST handlers are not reachable. */
export function OfflineBanner({ message }: { message: string }) {
  return (
    <div className="mb-6 rounded border border-reject/40 bg-reject/10 px-4 py-3 text-sm text-ink">
      <span className="font-mono text-reject">engine unreachable</span>
      <span className="ml-2 text-ink-dim">{message}</span>
    </div>
  );
}

/** A card surface. */
export function Card({ children }: { children: ReactNode }) {
  return (
    <div className="rounded border border-surface-line bg-surface-raised/60 overflow-hidden">{children}</div>
  );
}

/** An empty-state row inside a card. */
export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="px-5 py-8 text-center text-sm text-ink-faint">{children}</div>;
}

/** A small monospace key/value pair for a record field. */
export function Field({ label, value, mono = true }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-[0.15em] text-ink-faint">{label}</span>
      <span className={`text-sm text-ink ${mono ? 'font-mono tabular' : ''}`}>{value}</span>
    </div>
  );
}

/** A status pill — colour-coded by lifecycle state. */
export function StatusPill({ status }: { status: string }) {
  const tone =
    status === 'completed' || status === 'published'
      ? 'border-approve/40 bg-approve/10 text-approve'
      : status === 'aborted'
        ? 'border-reject/40 bg-reject/10 text-reject'
        : status === 'pending' || status === 'running' || status === 'striking'
          ? 'border-amber-signal/40 bg-amber-signal/10 text-amber-signal'
          : 'border-surface-line bg-surface-line/30 text-ink-dim';
  return (
    <span className={`inline-flex items-center rounded border px-2 py-0.5 font-mono text-[11px] ${tone}`}>
      {status}
    </span>
  );
}

/** A risk-score chip — amber when at/above the high-stakes threshold. */
export function RiskChip({ riskScore, threshold }: { riskScore: number; threshold: number }) {
  const high = riskScore >= threshold;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono text-[11px] tabular ${
        high ? 'border-amber-signal/50 bg-amber-signal/10 text-amber-signal' : 'border-surface-line text-ink-dim'
      }`}
    >
      risk {riskScore.toFixed(2)}
      {high && <span className="text-ink-faint">≥ {threshold.toFixed(2)}</span>}
    </span>
  );
}
