import { describe, expect, it } from 'vitest';
import { TerminalError } from '@restatedev/restate-sdk';
import { parsePlan } from './plan-parse.js';

describe('parsePlan — the orchestrator defensive parse of a returned plan', () => {
  it('accepts a well-formed plan and returns the typed shape', () => {
    const plan = parsePlan({
      steps: [{ soId: 'SO-09-02', args: { fund: 'X' }, rationale: 'twr' }],
      riskScore: 0.1,
      summary: 'compute twr',
    });
    expect(plan.steps).toHaveLength(1);
    expect(plan.steps[0].soId).toBe('SO-09-02');
    expect(plan.riskScore).toBe(0.1);
  });

  it('defaults optional fields (args/rationale/summary) when absent', () => {
    const plan = parsePlan({ steps: [{ soId: 'SO-09-01' }], riskScore: 0 });
    expect(plan.steps[0].args).toEqual({});
    expect(plan.steps[0].rationale).toBeNull();
    expect(plan.summary).toBeNull();
  });

  // The deterministic-failure class: a malformed plan is a TerminalError (no retry
  // storm), NOT a silent bad plan passed downstream.
  it('rejects an empty steps array (TerminalError)', () => {
    expect(() => parsePlan({ steps: [], riskScore: 0.5 })).toThrow(TerminalError);
  });

  it('rejects a missing soId (TerminalError)', () => {
    expect(() => parsePlan({ steps: [{ args: {} }], riskScore: 0.5 })).toThrow(TerminalError);
  });

  it('rejects a riskScore out of [0,1] (TerminalError)', () => {
    expect(() => parsePlan({ steps: [{ soId: 'SO-09-01' }], riskScore: 1.5 })).toThrow(TerminalError);
    expect(() => parsePlan({ steps: [{ soId: 'SO-09-01' }], riskScore: -0.1 })).toThrow(TerminalError);
  });

  it('rejects a non-object plan (TerminalError)', () => {
    expect(() => parsePlan(null)).toThrow(TerminalError);
    expect(() => parsePlan('a plan')).toThrow(TerminalError);
    expect(() => parsePlan([])).toThrow(TerminalError);
  });
});
