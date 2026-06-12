/**
 * ESLint flat config for the Operator UI — Next.js core-web-vitals + TypeScript rules
 * via eslint-config-next's flat preset. Lints src/**; ignores the build output.
 */
import { FlatCompat } from '@eslint/eslintrc';

const compat = new FlatCompat({ baseDirectory: import.meta.dirname });

export default [
  { ignores: ['.next/**', 'node_modules/**', 'next-env.d.ts'] },
  ...compat.config({
    extends: ['next/core-web-vitals', 'next/typescript'],
  }),
];
