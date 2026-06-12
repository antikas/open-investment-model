import { describe, expect, it } from 'vitest';
import {
  INVESTMENT_OPERATION_NAME,
  VersionSkewBlockedError,
  investmentOperation,
  type OperationResult,
} from './investment-operation.js';
import type { VersionSkewStatus } from '../substrate/restate-reach.js';

describe('InvestmentOperation virtual-object shell', () => {
  it('is a virtual object keyed by operationId, named investmentOperation', () => {
    expect(INVESTMENT_OPERATION_NAME).toBe('investmentOperation');
    // The runtime definition handle carries the routing name the ingress + the
    // endpoint bind use. (Restate keys a virtual object by the path segment after
    // the name — the operationId — so the keying is structural, not declared.)
    expect((investmentOperation as unknown as { name: string }).name).toBe(INVESTMENT_OPERATION_NAME);
  });

  it('exposes exactly the execute + status handlers (dispatch/approve still later)', () => {
    // The runtime definition handle exposes its handler set under `.object`.
    const handlers = (investmentOperation as unknown as { object: Record<string, unknown> }).object;
    expect(Object.keys(handlers).sort()).toEqual(['execute', 'status']);
  });

  it('OperationResult carries the plan, resolved args, step results, the aggregate + the audit record', () => {
    // Compile-time shape pin: the result the execute handler returns carries the full
    // plan → resolve → dispatch → aggregate → close chain — the journaled plan (replayed
    // stably, never re-planned), the resolve step's marts-derived concrete args, the
    // seam-2 dispatch stepResults, the seam-4 coherent aggregate, and the seam-5
    // journaled audit record.
    const sample: OperationResult = {
      operationId: 'op-123',
      plan: {
        steps: [
          { soId: 'SO-09-01', args: { fund: 'X' }, rationale: 'total return' },
          { soId: 'SO-09-05', args: { fund: 'X' }, rationale: 'contribution breakdown by sector' },
        ],
        riskScore: 0.05,
        summary: 'Performance attribution for fund X by sector.',
      },
      selectedSoIds: ['SO-09-01', 'SO-09-05'],
      resolvedSteps: [
        {
          index: 0,
          soId: 'SO-09-01',
          status: 'resolved',
          args: { beginning_value: '100', ending_value: '110', period_days: 365, cash_flows: [] },
          resolution: {
            soId: 'SO-09-01',
            fundId: 'X',
            fundName: 'Fund X',
            beginDate: '2025-03-31',
            endDate: '2026-03-31',
            periodDays: 365,
            beginNav: '100',
            endNav: '110',
            args: { beginning_value: '100', ending_value: '110', period_days: 365, cash_flows: [] },
            computedBy: 'python:argResolver',
          },
        },
      ],
      stepResults: [
        {
          index: 0,
          soId: 'SO-09-01',
          status: 'fulfilled',
          result: {
            result: { total_return: '0.10' },
            provenance: { soId: 'SO-09-01', tool: 'compute_total_return', methodology: 'modified-dietz' },
            computedBy: 'python:bd09',
          },
        },
      ],
      fulfilledCount: 1,
      rejectedCount: 0,
      aggregated: {
        kind: 'performance-attribution',
        coherent: true,
        totalReturn: '0.10',
        contributions: [{ sector: 'Equity', weight: '1', sectorReturn: '0.10', contribution: '0.10' }],
        contributionSum: '0.10',
        reconciles: true,
        reconciliationDiff: '0.00e+0',
        incoherenceReason: null,
      },
      auditRecord: {
        kind: 'operation-closed',
        operationId: 'op-123',
        task: 'Performance attribution for fund X by sector.',
        plan: {
          steps: [{ soId: 'SO-09-01', args: { fund: 'X' }, rationale: 'total return' }],
          riskScore: 0.05,
          summary: 'Performance attribution for fund X by sector.',
        },
        resolvedArgs: [{ soId: 'SO-09-01', status: 'resolved', window: null, error: null }],
        stepResults: [],
        aggregated: {
          kind: 'performance-attribution',
          coherent: true,
          totalReturn: '0.10',
          contributions: null,
          contributionSum: '0.10',
          reconciles: true,
          reconciliationDiff: '0.00e+0',
          incoherenceReason: null,
        },
        gateDecision: { gated: false, riskScore: 0.05, approvedAwakeableId: null },
        status: 'completed',
      },
      status: 'completed',
      kind: 'nav-strike',
      orchestrator: 'investmentOperation',
    };
    expect(sample.orchestrator).toBe(INVESTMENT_OPERATION_NAME);
    expect(sample.status).toBe('completed');
    expect(sample.selectedSoIds).toEqual(['SO-09-01', 'SO-09-05']);
    expect(sample.resolvedSteps[0].status).toBe('resolved');
    expect(sample.stepResults[0].status).toBe('fulfilled');
    expect(sample.aggregated.coherent).toBe(true);
    expect(sample.aggregated.reconciles).toBe(true);
    expect(sample.auditRecord.kind).toBe('operation-closed');
    expect(sample.auditRecord.gateDecision.gated).toBe(false);
  });
});

describe('VersionSkewBlockedError (block-new-ops gate)', () => {
  it('is a terminal refusal carrying the skew status', () => {
    const skew: VersionSkewStatus = {
      running: '1.7.0',
      pinned: '1.6.2',
      mismatch: true,
      indeterminate: false,
    };
    const err = new VersionSkewBlockedError(skew);
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe('VersionSkewBlockedError');
    expect(err.skew).toBe(skew);
    expect(err.message).toContain('1.7.0');
    expect(err.message).toContain('1.6.2');
    expect(err.message).toContain('blocked');
  });
});
