// ESLint flat config for the agentINVEST TS reference package.
// Type-aware linting via typescript-eslint's recommended-type-checked preset
// over src/**; the config files themselves are linted untyped.
import js from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    ignores: ['node_modules/**', 'dist/**'],
  },
  // The build/config files (this file, vitest.config.ts) are outside the
  // tsconfig project graph; lint them with the non-type-aware preset only.
  {
    files: ['eslint.config.js', 'vitest.config.ts'],
    extends: [js.configs.recommended],
  },
  // The source tree: type-aware linting.
  {
    files: ['src/**/*.ts'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // Conventional underscore-prefixed args/vars are intentional ignores
      // (e.g. an unused Restate Context on a no-arg handler).
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
);
