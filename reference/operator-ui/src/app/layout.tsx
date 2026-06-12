import type { Metadata } from 'next';
import { JetBrains_Mono, IBM_Plex_Sans } from 'next/font/google';
import Link from 'next/link';
import './globals.css';

/*
 * The operator console shell. A distinctive but restrained type pairing: IBM Plex Sans
 * for chrome/labels (an engineered, utilitarian sans) and JetBrains Mono for all data
 * (ids, scores, money, journals) so columns align and figures read unambiguously. The
 * shell carries the connectivity posture + the honest-boundary banner so an operator
 * always knows what they are looking at.
 */
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono', display: 'swap' });
const sans = IBM_Plex_Sans({ subsets: ['latin'], weight: ['400', '500', '600'], variable: '--font-sans', display: 'swap' });

export const metadata: Metadata = {
  title: 'agentINVEST — Operator Console',
  description: 'The operator surface for high-stakes approvals and the operation audit trail.',
};

const NAV = [
  { href: '/approvals', label: 'Approvals queue' },
  { href: '/operations', label: 'Operations' },
  { href: '/deployments', label: 'Deployments' },
  { href: '/canonical', label: 'Canonical data' },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${mono.variable} ${sans.variable}`}>
      <body className="font-sans antialiased min-h-screen">
        <header className="border-b border-surface-line bg-surface-raised/70 backdrop-blur sticky top-0 z-10">
          <div className="mx-auto max-w-6xl px-6 py-3 flex items-center gap-6">
            <Link href="/" className="flex items-baseline gap-2 shrink-0">
              <span className="font-mono text-sm font-semibold tracking-tight text-ink">agentINVEST</span>
              <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint">operator</span>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="px-3 py-1.5 rounded text-ink-dim hover:text-ink hover:bg-surface-line/50 transition-colors"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
            <span className="ml-auto font-mono text-[11px] text-ink-faint hidden sm:block">
              single-operator · localhost · synthetic data
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-6 pb-10 pt-4 text-[11px] leading-relaxed text-ink-faint">
          Operator console (v0.1): the Approvals queue, the Operations dashboard, the Deployments view,
          and the read-only Canonical-data inspector. Reads the local engine over its admin and ingress
          APIs on the server — no key in the browser. No app-layer sign-in: a single operator on a trusted
          localhost; a network boundary is the access control at deploy. Figures are synthetic; this is a
          workstation surface, not a production console.
        </footer>
      </body>
    </html>
  );
}
