import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Unit tests only by default (the cross-language RPC smoke is a runnable
    // script under src/rpc/, not a unit test — it needs the live substrate).
    include: ['src/**/*.test.ts'],
    environment: 'node',
  },
});
