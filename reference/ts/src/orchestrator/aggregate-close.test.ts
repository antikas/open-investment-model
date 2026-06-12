/**
 * Unit proof of the AGGREGATE (seam 4) + CLOSE (seam 5) seams (OIM-134) — the coherent attribution
 * answer + the well-formed journaled audit record, isolated as pure logic.
 *
 * Pins:
 *  - the coherent attribution (the OIM-115 coherence invariant — the per-sector contributions
 *    reconcile to the total return);
 *  - the HONEST PARTIAL-FAILURE (a failed step → coherent:false + a surfaced reason, NEVER a
 *    fabricated number);
 *  - a non-reconciling result is surfaced (not fabricated away);
 *  - the audit record is well-formed + queryable (every field present + structured).
 */
import { describe, expect, it } from 'vitest';
import {
  aggregateResults,
  buildAuditRecord,
  type GateDecisionRecord,
} from './aggregate-close.js';
import type { StepResult } from './dispatch.js';
import type { ResolvedStep } from './resolve.js';
import type { Plan } from './llm-service-contract.js';

function attributionPlan(): Plan {
  return {
    steps: [
      { soId: 'SO-09-01', args: { fund: 'PF-0003' }, rationale: 'total return' },
      { soId: 'SO-09-05', args: { fund: 'PF-0003' }, rationale: 'contribution breakdown by sector' },
    ],
    riskScore: 0.05,
    summary: 'Performance attribution for PF-0003 by sector.',
  };
}

function totalReturnStep(totalReturn: string): StepResult {
  return {
    index: 0,
    soId: 'SO-09-01',
    status: 'fulfilled',
    result: {
      result: { total_return: totalReturn, average_capital: '1000000', net_external_flow: '0', methodology: 'modified-dietz' },
      provenance: { soId: 'SO-09-01', tool: 'compute_total_return', methodology: 'modified-dietz' },
      computedBy: 'python:bd09',
    },
  };
}

function contributionStep(contributionTotal: string): StepResult {
  return {
    index: 1,
    soId: 'SO-09-05',
    status: 'fulfilled',
    result: {
      result: {
        contributions: [
          { segment: 'Public equity', weight: '0.6', segment_return: '0.15', contribution: '0.09' },
          { segment: 'Fixed income', weight: '0.4', segment_return: '0.025', contribution: '0.01' },
        ],
        total_return: contributionTotal,
        methodology: 'contribution-weight-times-return',
      },
      provenance: { soId: 'SO-09-05', tool: 'compute_contribution_breakdown', methodology: 'contribution-weight-times-return' },
      computedBy: 'python:bd09',
    },
  };
}

describe('aggregateResults — seam 4 (the coherent attribution + the OIM-115 coherence invariant)', () => {
  it('produces a coherent attribution when both tools fulfil and the contributions reconcile', () => {
    const agg = aggregateResults([totalReturnStep('0.10'), contributionStep('0.10')], attributionPlan());
    expect(agg.kind).toBe('performance-attribution');
    expect(agg.coherent).toBe(true);
    expect(agg.totalReturn).toBe('0.10');
    expect(agg.contributionSum).toBe('0.10');
    expect(agg.reconciles).toBe(true);
    expect(agg.contributions).toHaveLength(2);
    expect(agg.contributions?.[0]).toMatchObject({ sector: 'Public equity', contribution: '0.09' });
    expect(agg.incoherenceReason).toBeNull();
  });

  it('SURFACES a non-reconciliation (a wrong compute) — coherent:false, NOT fabricated away', () => {
    // The contribution sum (0.99) does NOT match the total return (0.10) — the OIM-115 invariant
    // FIRES. The aggregate must surface it (coherent:false, reconciles:false, a reason), never
    // silently report a coherent number.
    const agg = aggregateResults([totalReturnStep('0.10'), contributionStep('0.99')], attributionPlan());
    expect(agg.coherent).toBe(false);
    expect(agg.reconciles).toBe(false);
    expect(agg.totalReturn).toBe('0.10');
    expect(agg.contributionSum).toBe('0.99');
    expect(agg.incoherenceReason).toContain('do not reconcile');
  });

  it('HONEST PARTIAL-FAILURE: a failed step → coherent:false + surfaced reason, NO fabricated number', () => {
    // SO-09-05 surfaced a clean dispatch failure; the aggregate must NOT fabricate the breakdown —
    // it surfaces the partial failure (the OIM-131 honesty).
    const failedContribution: StepResult = {
      index: 1,
      soId: 'SO-09-05',
      status: 'rejected',
      error: "SO-09-05 (compute_contribution_breakdown): invalid arguments — segment weights sum to 0.5, not 1",
    };
    const agg = aggregateResults([totalReturnStep('0.10'), failedContribution], attributionPlan());
    expect(agg.coherent).toBe(false);
    expect(agg.totalReturn).toBe('0.10'); // the fulfilled step's figure is still carried
    expect(agg.contributions).toBeNull(); // the failed step's breakdown is NOT fabricated
    expect(agg.reconciles).toBe(false);
    expect(agg.incoherenceReason).toContain('SO-09-05');
    expect(agg.incoherenceReason).toContain('partial failure');
  });

  it('surfaces a fully-failed operation (both steps rejected) without inventing an answer', () => {
    const failed = (soId: string, index: number): StepResult => ({ index, soId, status: 'rejected', error: `${soId} failed` });
    const agg = aggregateResults([failed('SO-09-01', 0), failed('SO-09-05', 1)], attributionPlan());
    expect(agg.coherent).toBe(false);
    expect(agg.totalReturn).toBeNull();
    expect(agg.contributions).toBeNull();
    expect(agg.incoherenceReason).toContain('SO-09-01');
    expect(agg.incoherenceReason).toContain('SO-09-05');
  });
});

describe('buildAuditRecord — seam 5 (the well-formed, queryable journaled audit record)', () => {
  const resolvedSteps: ResolvedStep[] = [
    {
      index: 0,
      soId: 'SO-09-01',
      status: 'resolved',
      args: { beginning_value: '1000000.00', ending_value: '1100000.00', period_days: 365, cash_flows: [] },
      resolution: {
        soId: 'SO-09-01',
        fundId: 'PF-0003',
        fundName: 'Polaris Multi-Asset',
        beginDate: '2025-03-31',
        endDate: '2026-03-31',
        periodDays: 365,
        beginNav: '1000000.00',
        endNav: '1100000.00',
        args: { beginning_value: '1000000.00', ending_value: '1100000.00', period_days: 365, cash_flows: [] },
        computedBy: 'python:argResolver',
      },
    },
  ];
  const gateDecision: GateDecisionRecord = { gated: false, riskScore: 0.05, approvedAwakeableId: null };

  it('captures the whole operation — task, plan, resolved args, step results, aggregate, gate decision', () => {
    const plan = attributionPlan();
    const stepResults = [totalReturnStep('0.10'), contributionStep('0.10')];
    const aggregated = aggregateResults(stepResults, plan);
    const record = buildAuditRecord({
      operationId: 'op-attr-1',
      task: 'calculate performance attribution for fund PF-0003 for the period, broken down by sector',
      plan,
      resolvedSteps,
      stepResults,
      aggregated,
      gateDecision,
    });

    // Well-formed: every field the fiduciary record needs is present + structured (queryable).
    expect(record.kind).toBe('operation-closed');
    expect(record.operationId).toBe('op-attr-1');
    expect(record.task).toContain('performance attribution');
    expect(record.plan.steps.map((s) => s.soId)).toEqual(['SO-09-01', 'SO-09-05']);
    expect(record.resolvedArgs).toHaveLength(1);
    expect(record.resolvedArgs[0]).toMatchObject({ soId: 'SO-09-01', status: 'resolved' });
    expect(record.resolvedArgs[0].window?.fundId).toBe('PF-0003');
    expect(record.stepResults).toHaveLength(2);
    expect(record.aggregated.coherent).toBe(true);
    expect(record.gateDecision.gated).toBe(false); // the no-op gate for read-only analytics
    expect(record.status).toBe('completed');
    // The record is JSON-serialisable (queryable, not free text).
    expect(() => JSON.stringify(record)).not.toThrow();
  });

  it('records an unresolved step honestly (the clean-failure window)', () => {
    const unresolved: ResolvedStep[] = [{ index: 0, soId: 'SO-09-02', status: 'unresolved', error: 'v0.1 cannot resolve SO-09-02' }];
    const plan = attributionPlan();
    const stepResults: StepResult[] = [{ index: 0, soId: 'SO-09-02', status: 'rejected', error: 'v0.1 cannot resolve SO-09-02' }];
    const aggregated = aggregateResults(stepResults, plan);
    const record = buildAuditRecord({
      operationId: 'op-unres',
      task: 'attribution',
      plan,
      resolvedSteps: unresolved,
      stepResults,
      aggregated,
      gateDecision,
    });
    expect(record.resolvedArgs[0]).toMatchObject({ soId: 'SO-09-02', status: 'unresolved', window: null });
    expect(record.resolvedArgs[0].error).toContain('cannot resolve');
    expect(record.aggregated.coherent).toBe(false);
  });
});
