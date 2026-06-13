/**
 * The AGGREGATE (seam 4) + CLOSE (seam 5) seams — the orchestrator's coherent answer + its
 * journaled audit record.
 *
 * After the resolve step derives the concrete inputs and the dispatch step runs the tools, the
 * orchestrator has the RAW per-step results. AGGREGATE combines them into a coherent attribution
 * answer; CLOSE emits the journaled, well-formed audit record of the whole operation.
 *
 * AGGREGATE (seam 4) — `aggregateResults(stepResults, plan)`. For the performance-attribution task
 * the plan selects SO-09-01 (the fund's total return) + SO-09-05 (the per-sector contribution
 * breakdown). Aggregate combines them into one attribution answer: the total return + the
 * per-sector contributions, with the COHERENCE INVARIANT as the correctness check — the
 * per-sector contributions RECONCILE to the total return (both draw on one underlying per-segment
 * NAV-delta derivation, so they tie by construction; a divergence catches a wrong tool compute, a
 * misrouted dispatch, or an envelope pluck bug). HONEST PARTIAL-FAILURE:
 * if a step FAILED, the aggregate SURFACES it — it does NOT fabricate a number. A coherent answer
 * is produced ONLY when both tools fulfilled and reconcile; otherwise the aggregate is `coherent:
 * false` and names what is missing.
 *
 * CLOSE (seam 5) — `buildAuditRecord(...)`. A structured, queryable audit record of the whole
 * operation: the task, the plan, the resolved args, the step results, the aggregate, and the gate
 * decision (if any). The orchestrator writes it via a journaled `ctx.run("operation-closed", ...)`
 * so it is recorded exactly-once (replay reads it back, it is not re-emitted). A PLAIN journaled
 * record — the hash-chained S3 export (tamper-evidence, 7-year retention) is a forward item, NOT
 * built here.
 *
 * PURE LOGIC. Both functions are pure (no I/O, no clock, no context) — the orchestrator calls them
 * and journals their results. Money/rate figures stay exact via decimal-string arithmetic (no
 * binary float): the marts emit decimal strings, the tools round-trip them as strings, and the
 * reconciliation compares them with a tight tolerance.
 *
 * HONEST BOUNDARY (v0.1). The attribution is REAL (the resolved args make the plan executable) but
 * over SYNTHETIC marts data — not a production performance attribution. The coherence invariant is
 * a plumbing-consistency check (it catches a wrong compute / misrouted dispatch
 * / pluck bug; it is NOT an independent-methods cross-validation — both tools draw on one
 * per-segment NAV-delta set, so they reconcile exact-by-construction). The audit record is a
 * journaled record, not a tamper-evident export.
 */
import type { Plan } from './llm-service-contract.js';
import type { StepResult } from './dispatch.js';
import type { ResolvedStep } from './resolve.js';

/** The total-return tool (SO-09-01) and the contribution-breakdown tool (SO-09-05). */
export const TOTAL_RETURN_SO_ID = 'SO-09-01';
export const CONTRIBUTION_SO_ID = 'SO-09-05';

/**
 * The reconciliation tolerance — the coherence invariant's tolerance. The per-sector contributions
 * reconcile to the total return BY CONSTRUCTION (both derive from one per-segment NAV-delta set),
 * so the only gap is decimal rounding in the weight/return ratios. 1e-9 is far tighter than any
 * 1-bp (1e-4) reporting tolerance — exact-by-construction, not an approximation.
 */
export const RECONCILIATION_TOLERANCE = 1e-9;

/** One sector's contribution to the total return (the per-segment breakdown line). */
export interface SectorContribution {
  /** The sector / asset-class label. */
  sector: string;
  /** The sector's weight in the fund (the weights sum to 1). */
  weight: string;
  /** The sector's own return over the window. */
  sectorReturn: string;
  /** weight × sectorReturn — the contribution to the total return. */
  contribution: string;
}

/**
 * The coherent attribution answer (seam 4's output). `coherent` is true ONLY when both tools
 * fulfilled AND the per-sector contributions reconcile to the total return. On a partial failure
 * (a step failed) or a non-reconciling result it is false and `incoherenceReason` names why — the
 * aggregate surfaces the gap, it never fabricates a number.
 */
export interface AttributionAggregate {
  kind: 'performance-attribution';
  /** True only when both tools fulfilled and the contributions reconcile to the total return. */
  coherent: boolean;
  /** The fund's total return over the window (from SO-09-01), or null if that step failed. */
  totalReturn: string | null;
  /** The per-sector contributions (from SO-09-05), or null if that step failed. */
  contributions: SectorContribution[] | null;
  /** The sum of the per-sector contributions (the reconciliation LHS), or null. */
  contributionSum: string | null;
  /** Whether the contributions reconcile to the total return within tolerance (the coherence check). */
  reconciles: boolean;
  /** |contributionSum − totalReturn| (the reconciliation diff), or null if a step failed. */
  reconciliationDiff: string | null;
  /** When not coherent, the human reason (a partial failure, a non-reconciliation) — never fabricated. */
  incoherenceReason: string | null;
}

/** The fulfilled variant of a StepResult (carrying the tool result). */
type FulfilledStep = Extract<StepResult, { status: 'fulfilled' }>;

/** Find a fulfilled step result by soId; null if absent or that step was rejected. */
function fulfilledFor(stepResults: StepResult[], soId: string): FulfilledStep | null {
  const r = stepResults.find((s) => s.soId === soId);
  return r && r.status === 'fulfilled' ? r : null;
}

/** Read a decimal-string field off a tool result envelope; null if missing/non-string-or-number. */
function readDecimalField(result: Record<string, unknown>, key: string): string | null {
  const v = result[key];
  if (typeof v === 'string') return v;
  if (typeof v === 'number') return String(v);
  return null;
}

/**
 * Aggregate the dispatched step results into a coherent performance-attribution answer (seam 4).
 *
 * Combines SO-09-01 (total return) + SO-09-05 (per-sector contributions) into one answer, with the
 * coherence invariant (the contributions reconcile to the total return) as the correctness
 * check. HONEST PARTIAL-FAILURE: if either tool's step failed, the aggregate is NOT coherent and
 * `incoherenceReason` names the failed step — no fabricated number. Pure logic.
 *
 * @param stepResults the dispatched per-step outcomes (fulfilled or rejected).
 * @param plan        the journaled plan (its selected soIds frame the expected attribution shape).
 * @returns the coherent attribution answer, or a non-coherent answer naming the gap.
 */
export function aggregateResults(stepResults: StepResult[], plan: Plan): AttributionAggregate {
  const totalReturnStep = fulfilledFor(stepResults, TOTAL_RETURN_SO_ID);
  const contributionStep = fulfilledFor(stepResults, CONTRIBUTION_SO_ID);

  // HONEST PARTIAL-FAILURE — surface a missing/failed step; never fabricate the answer. A step is
  // "missing" if the plan did not select that tool OR its dispatch did not fulfil — either way the
  // attribution cannot be coherently formed and the gap is named (not fabricated away).
  const missing: string[] = [];
  if (!totalReturnStep) missing.push(`${TOTAL_RETURN_SO_ID} (total return)`);
  if (!contributionStep) missing.push(`${CONTRIBUTION_SO_ID} (contribution breakdown)`);

  const totalReturn = totalReturnStep
    ? readDecimalField(totalReturnStep.result.result, 'total_return')
    : null;

  let contributions: SectorContribution[] | null = null;
  let contributionSum: string | null = null;
  if (contributionStep) {
    const raw = contributionStep.result.result.contributions;
    if (Array.isArray(raw)) {
      contributions = raw.map((c) => {
        const seg = c as Record<string, unknown>;
        return {
          sector: String(seg.segment ?? ''),
          weight: readDecimalField(seg, 'weight') ?? '0',
          sectorReturn: readDecimalField(seg, 'segment_return') ?? '0',
          contribution: readDecimalField(seg, 'contribution') ?? '0',
        };
      });
    }
    // SO-09-05's own output carries the total it sums to (`total_return`) — the contribution sum.
    contributionSum = readDecimalField(contributionStep.result.result, 'total_return');
  }

  // The COHERENCE INVARIANT — the contributions reconcile to the total return. Computed
  // only when BOTH tools fulfilled; a partial failure makes the answer non-coherent (surfaced).
  let reconciles = false;
  let reconciliationDiff: string | null = null;
  let incoherenceReason: string | null = null;

  if (missing.length > 0) {
    const planned = plan.steps.map((s) => s.soId).join(', ');
    incoherenceReason =
      `partial failure — the attribution needs both the total return and the contribution ` +
      `breakdown, but ${missing.join(' and ')} did not complete (plan selected: [${planned}]); ` +
      `surfaced, not fabricated.`;
  } else if (totalReturn === null || contributionSum === null) {
    incoherenceReason = `a tool result was missing its expected field (total_return); surfaced, not fabricated.`;
  } else {
    const diff = Math.abs(Number(contributionSum) - Number(totalReturn));
    reconciliationDiff = diff.toExponential(2);
    reconciles = diff <= RECONCILIATION_TOLERANCE;
    if (!reconciles) {
      incoherenceReason =
        `the per-sector contributions (${contributionSum}) do not reconcile to the total return ` +
        `(${totalReturn}); diff ${reconciliationDiff} exceeds tolerance ${RECONCILIATION_TOLERANCE.toExponential(0)}. ` +
        `Surfaced — a wrong tool compute / misrouted dispatch / envelope pluck bug, NOT fabricated away.`;
    }
  }

  const coherent = missing.length === 0 && reconciles;

  return {
    kind: 'performance-attribution',
    coherent,
    totalReturn,
    contributions,
    contributionSum,
    reconciles,
    reconciliationDiff,
    incoherenceReason,
  };
}

/** A compact projection of one resolved step for the audit record (the marts-derived window). */
export interface ResolvedArgRecord {
  soId: string;
  status: 'resolved' | 'unresolved';
  /** The resolved window provenance (fund, window, begin/end NAV), present on a resolved step. */
  window: {
    fundId: string;
    fundName: string;
    beginDate: string;
    endDate: string;
    periodDays: number;
    beginNav: string;
    endNav: string;
    computedBy: string;
  } | null;
  /** The surfaced resolution error, present on an unresolved step. */
  error: string | null;
}

/** The gate decision recorded in the audit record (a no-op for read-only analytics). */
export interface GateDecisionRecord {
  /** Whether the high-stakes gate fired (paused for an operator). False for read-only analytics. */
  gated: boolean;
  /** The plan's riskScore the gate evaluated. */
  riskScore: number;
  /** The awakeable id an operator approved, when gated; null when the gate was a no-op. */
  approvedAwakeableId: string | null;
}

/**
 * The journaled, well-formed, structured audit record of the whole operation (seam 5's payload).
 * Queryable (a structured object, not free text): the task, the plan, the resolved args, the step
 * results, the aggregate, and the gate decision. A PLAIN journaled record — the hash-chained
 * tamper-evident export is a forward item, NOT built here.
 */
export interface OperationAuditRecord {
  kind: 'operation-closed';
  operationId: string;
  /** The natural-language analyst task this operation carried out. */
  task: string;
  /** The plan the `.plan()` step produced (the selected tools + riskScore + summary). */
  plan: Plan;
  /** The resolve step's per-step outcomes (the marts-derived window per step). */
  resolvedArgs: ResolvedArgRecord[];
  /** The dispatch step's per-step outcomes (fulfilled tool results / surfaced failures). */
  stepResults: StepResult[];
  /** The aggregate (seam 4) — the coherent attribution answer (or the surfaced partial failure). */
  aggregated: AttributionAggregate;
  /** The gate decision (seam 3) — a no-op for this read-only analytics task. */
  gateDecision: GateDecisionRecord;
  /** Terminal status of the operation. */
  status: 'completed';
}

/** Project the resolve step's outcomes into the audit record's `resolvedArgs` shape. */
export function recordResolvedArgs(resolvedSteps: ResolvedStep[]): ResolvedArgRecord[] {
  return resolvedSteps.map((r) =>
    r.status === 'resolved'
      ? {
          soId: r.soId,
          status: 'resolved',
          window: {
            fundId: r.resolution.fundId,
            fundName: r.resolution.fundName,
            beginDate: r.resolution.beginDate,
            endDate: r.resolution.endDate,
            periodDays: r.resolution.periodDays,
            beginNav: r.resolution.beginNav,
            endNav: r.resolution.endNav,
            computedBy: r.resolution.computedBy,
          },
          error: null,
        }
      : { soId: r.soId, status: 'unresolved', window: null, error: r.error },
  );
}

/**
 * Build the structured audit record of the whole operation (seam 5). Pure logic; the orchestrator
 * writes the returned record via a journaled `ctx.run("operation-closed", ...)` (recorded
 * exactly-once). Well-formed + queryable: every field the fiduciary record needs (task, plan,
 * resolved args, step results, aggregate, gate decision) is present and structured.
 */
export function buildAuditRecord(args: {
  operationId: string;
  task: string;
  plan: Plan;
  resolvedSteps: ResolvedStep[];
  stepResults: StepResult[];
  aggregated: AttributionAggregate;
  gateDecision: GateDecisionRecord;
}): OperationAuditRecord {
  return {
    kind: 'operation-closed',
    operationId: args.operationId,
    task: args.task,
    plan: args.plan,
    resolvedArgs: recordResolvedArgs(args.resolvedSteps),
    stepResults: args.stepResults,
    aggregated: args.aggregated,
    gateDecision: args.gateDecision,
    status: 'completed',
  };
}
