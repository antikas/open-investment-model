import type { Config } from 'tailwindcss';

/**
 * Tailwind config for the agentINVEST Operator UI — a restrained, utilitarian
 * control-room palette: a deep slate surface, a single amber accent for the
 * pending-approval urgency state, and decision green/red. Operator-functional,
 * not a design showcase. The display/body fonts are loaded via next/font in the
 * layout and surfaced as CSS variables.
 */
const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0e141b',
          raised: '#161e29',
          line: '#243140',
        },
        ink: {
          DEFAULT: '#e7edf3',
          dim: '#9fb0c0',
          faint: '#647689',
        },
        amber: { signal: '#f0a830' },
        approve: '#3fb27f',
        reject: '#e2625b',
      },
      fontFamily: {
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};

export default config;
