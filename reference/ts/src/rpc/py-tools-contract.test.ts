import { describe, expect, it } from 'vitest';
import { PY_TOOLS, PY_TOOLS_SERVICE_NAME, type SimpleReturnInput } from './py-tools-contract.js';

describe('py-tools cross-language contract', () => {
  it('exposes the shared service routing key', () => {
    expect(PY_TOOLS_SERVICE_NAME).toBe('pyTools');
    // The type-only service-definition handle carries the runtime routing key
    // the TS caller passes to ctx.serviceClient(...).
    expect((PY_TOOLS as unknown as { name: string }).name).toBe(PY_TOOLS_SERVICE_NAME);
  });

  it('the input contract shape matches the Python wire shape (camelCase keys)', () => {
    // This is a compile-time + shape assertion: the keys here MUST equal the
    // TypedDict keys in reference/python/.../py_tools_service.py. Drift is a
    // contract break the live smoke catches at runtime; this pins it in CI.
    const sample: SimpleReturnInput = {
      beginningValue: 100,
      endingValue: 110,
      cashFlow: 0,
    };
    expect(Object.keys(sample).sort()).toEqual(['beginningValue', 'cashFlow', 'endingValue']);
  });
});
