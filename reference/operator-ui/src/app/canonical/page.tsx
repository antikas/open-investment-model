/**
 * The CANONICAL-DATA INSPECTOR — read-only. A fixed viewer over the dbt-built canonical layer:
 * the published marts and the realised staging entities, each with its row count; and, for a
 * selected table, the column headers + a capped sample (≤25 rows) of real rows.
 *
 * This is NOT a query console. The only inputs are: which table to inspect (selected from the
 * listed set — a link, validated against the server-side allowlist) and an implicit capped row
 * limit. There is no free-form SQL and no injection surface: the table name is checked against the
 * store-derived allowlist in the Python read handler before any sample SQL runs; an unknown or
 * crafted name is refused. The console reaches the canonical layer through the engine's ingress on
 * the server — no store path or secret in the browser.
 */
import Link from 'next/link';
import { listCanonicalTables, sampleCanonicalTable } from '@/lib/restate';
import { PageHeader, OfflineBanner, Card, EmptyState } from '@/components/primitives';

export const dynamic = 'force-dynamic';

export default async function CanonicalPage({
  searchParams,
}: {
  searchParams: Promise<{ table?: string }>;
}) {
  const { table: requested } = await searchParams;
  const { tables, available } = await listCanonicalTables();

  // Only inspect a table that is in the listed (allowlisted) set — the link target is validated
  // against the live set before we sample (defence in depth; the handler re-validates regardless).
  const selectedName = requested && tables.some((t) => t.name === requested) ? requested : null;
  const sample = selectedName ? await sampleCanonicalTable(selectedName) : null;

  const canonical = tables
    .filter((t) => t.layer === 'canonical')
    .map((t) => ({ ...t, label: entityModelLabel(t.table) }));
  const bitemporal = tables.filter((t) => t.layer === 'bitemporal');
  const marts = tables.filter((t) => t.layer === 'mart');
  const staging = tables.filter((t) => t.layer === 'staging');

  return (
    <div>
      <PageHeader
        title="Canonical data"
        subtitle="The canonical layer: the realised entity model, the bi-temporal as-of views, the computed marts, and the comparator feeds. Read-only."
      />

      {!available && (
        <OfflineBanner message="The canonical-data read endpoint is not reachable — start the data endpoint to inspect the canonical layer." />
      )}

      {available && tables.length === 0 && (
        <Card>
          <EmptyState>
            No canonical tables found. Build the canonical layer to inspect the marts and staging
            entities here.
          </EmptyState>
        </Card>
      )}

      {tables.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[18rem_1fr]">
          <aside className="space-y-5">
            <TableGroup title="canonical entities" tables={canonical} selectedName={selectedName} />
            <TableGroup title="bi-temporal (as-of)" tables={bitemporal} selectedName={selectedName} />
            <TableGroup title="marts" tables={marts} selectedName={selectedName} />
            <TableGroup title="staging / feeds" tables={staging} selectedName={selectedName} />
          </aside>

          <section>
            {!selectedName ? (
              <Card>
                <EmptyState>Select a table to view its columns and a capped sample of rows.</EmptyState>
              </Card>
            ) : sample === null ? (
              <Card>
                <EmptyState>That table is not available to inspect.</EmptyState>
              </Card>
            ) : (
              <div>
                <div className="mb-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  {(() => {
                    const lbl = entityModelLabel(sample.name.split('.').pop() ?? '');
                    return lbl ? (
                      <>
                        <h2 className="text-sm text-ink">{lbl}</h2>
                        <span className="font-mono text-xs text-ink-faint">{sample.name}</span>
                      </>
                    ) : (
                      <h2 className="font-mono text-sm text-ink">{sample.name}</h2>
                    );
                  })()}
                  <span className="font-mono text-xs text-ink-faint tabular">
                    {sample.rowCount} row{sample.rowCount === 1 ? '' : 's'}
                  </span>
                  <span className="font-mono text-xs text-ink-faint">
                    showing {sample.sampled} (cap {sample.limit})
                  </span>
                </div>
                <Card>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-surface-line text-left text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                          {sample.columns.map((col) => (
                            <th key={col} className="whitespace-nowrap px-4 py-2 font-medium">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sample.rows.map((row, i) => (
                          <tr key={i} className="border-b border-surface-line last:border-b-0">
                            {row.map((cell, j) => (
                              <td key={j} className="whitespace-nowrap px-4 py-2 font-mono tabular text-ink-dim">
                                {cell === null ? <span className="text-ink-faint">∅</span> : cell}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

/**
 * Map a realised canonical entity table (stg_eNN_*) to its model identity, e.g.
 * "stg_e01_legal_entity" -> "E-01 Legal Entity". Returns null for non-entity tables (marts, feeds,
 * bi-temporal), which keep their dbt name. Reader-facing only — the dbt object name stays the real
 * handle (the canonical layer becomes an actual named layer in a later reworking of the data layer).
 */
function entityModelLabel(tableName: string): string | null {
  const m = /^stg_e(\d{2})_(.+)$/.exec(tableName);
  if (!m) return null;
  const title = m[2].split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  return `E-${m[1]} ${title}`;
}

/** A grouped list of inspectable tables — each a link that selects the table for the sample view. */
function TableGroup({
  title,
  tables,
  selectedName,
}: {
  title: string;
  tables: { name: string; table: string; rowCount: number; label?: string | null }[];
  selectedName: string | null;
}) {
  if (tables.length === 0) return null;
  return (
    <div>
      <h2 className="mb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-faint">{title}</h2>
      <Card>
        <ul>
          {tables.map((t) => {
            const active = t.name === selectedName;
            return (
              <li key={t.name} className="border-b border-surface-line last:border-b-0">
                <Link
                  href={`/canonical?table=${encodeURIComponent(t.name)}`}
                  className={`flex items-baseline justify-between gap-3 px-4 py-2 text-sm transition-colors ${
                    active ? 'bg-surface-line/40 text-ink' : 'text-ink-dim hover:bg-surface-line/30 hover:text-ink'
                  }`}
                >
                  <span className="min-w-0">
                    {t.label ? (
                      <>
                        <span className="block truncate">{t.label}</span>
                        <span className="block truncate font-mono text-[11px] text-ink-faint">{t.table}</span>
                      </>
                    ) : (
                      <span className="font-mono">{t.table}</span>
                    )}
                  </span>
                  <span className="shrink-0 font-mono text-xs text-ink-faint tabular">{t.rowCount}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </Card>
    </div>
  );
}
