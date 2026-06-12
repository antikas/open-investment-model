/**
 * The `NavCalculationWorkflow` — a multi-step, journaled Restate WORKFLOW that strikes a
 * fund's NAV, with the high-stakes approval gate at the irreversible PUBLISH step.
 *
 * This is the FIRST REAL wiring of the reusable `HighStakesApprovalGate` (the OIM-132
 * component) at an irreversible action: NAV publication is a regulated event. The OIM-132
 * gate was a MECHANISM proven by a forced-fire test (the read-only BD-09 tools never fire
 * it). Here the gate fires because the PUBLISH IS DECLARED HIGH-STAKES — the workflow
 * supplies a high riskScore at the gate, so the publish always pauses for an operator.
 *
 * THE STEPS (architecture §6.1), each a journaled durable checkpoint (`ctx.run`):
 *
 *   load-positions → price-positions → apply-fees → roll-up → [GATE] → publish
 *
 * Faithful to §6.1's `navCalculation` sketch. The COMPONENTS are READ FROM the OIM-111
 * marts via the `navData` Python service — the workflow does NOT re-implement pricing/NAV.
 * Each step is a durable CHECKPOINT over real data; the reconciliation is a GENUINE
 * CROSS-MART check, NOT a within-row tautology:
 *   - load-positions — rolls up the fund's gross market value INDEPENDENTLY from the HOLDINGS
 *                      mart (`mart_portfolio_holdings`: Σ each held position's
 *                      `market_value_usd`) — a different mart + SQL path from `mart_fund_nav`.
 *   - price-positions — the per-fund §A1 NAV components from `mart_fund_nav`
 *                      (gross_market_value, accrued_income, fees, the published nav_usd).
 *   - apply-fees      — the fees term (structurally present, zero on this synthetic seed).
 *   - roll-up         — the GENUINE CROSS-MART RECONCILIATION: the holdings-derived gross
 *                      (load-positions, from `mart_portfolio_holdings`) is asserted EQUAL to
 *                      `mart_fund_nav.gross_market_value` to the penny — two independent
 *                      marts / SQL paths (the OIM-111 `assert_marts_reconcile_holdings_to_nav`
 *                      invariant, here exercised live), so a divergence (a dropped position,
 *                      a double-counted book) FAILS. This is FALSIFIABLE, not X==X. Then
 *                      NAV = gross + accrued_income − fees is the §A1 identity (dbt-enforced
 *                      upstream by `assert_mart_fund_nav_invariant`), reconciled to the mart's
 *                      published nav_usd. A divergence is a TerminalError (no retry-storm).
 *   - [GATE]          — `highStakesApprovalGate` (REUSED from approval-gate.ts, NOT
 *                       re-implemented): a durable `ctx.awakeable` pause; approve → publish;
 *                       reject → terminal abort, NO publish; timeout → terminal abort, NO
 *                       publish. The gate precedes publish so a reject never half-publishes.
 *   - publish         — strike the NAV + write a journaled publish record. EXACTLY-ONCE: a
 *                       crash AFTER publish reads the journaled record back, it does NOT
 *                       re-publish.
 *
 * WHY A WORKFLOW (not the `investmentOperation` virtual object). A Restate WORKFLOW is keyed
 * by a one-shot workflow id (one strike per id), has the single `run` handler plus shared
 * query handlers, and is the natural shape for "a long-running, human-gated, journaled
 * fiduciary process with a terminal outcome" (ADR-0054: workflows are durable orchestrations
 * / playbooks, NOT agents, NOT new reasoning loops). The `WorkflowContext` extends
 * `ObjectContext`, so the OIM-132 gate (typed to `ObjectContext`) accepts the workflow's
 * context DIRECTLY — the gate is reused cross-API with no copy.
 *
 * THE LEGAL RESTATE SHAPE (the OIM-104 discipline). The marts-read RPC (`ctx.serviceClient
 * (NAV_DATA_SERVICE).getFundNavComponents`), every `ctx.run` checkpoint, the gate's
 * awakeable + notify + abort-trace, and the publish-record `ctx.run` are ALL top-level
 * context actions — none nested inside another `ctx.run` closure (a context action inside a
 * `ctx.run` body is the Restate determinism anti-pattern). Each `ctx.run` closure does a
 * plain side effect whose RESULT is journaled; it makes no further journaled call.
 *
 * HONEST BOUNDARY (v0.1). The NAV is SYNTHETIC (the §A1 marts, NOT a real struck production
 * NAV — oracle-anchored production, shadow-pipeline-matched + GIPS/CFA-calibrated behind a
 * production gate, is the named arc). NO SHARE CLASSES (the seed lacks them → a per-fund
 * single-class roll-up; the share_class column is carried for forward-compat). The gate
 * fires because the PUBLISH IS DECLARED HIGH-STAKES (the first real high-stakes wiring, vs
 * OIM-132's forced-fire test). PUBLISH is a journaled record, and EXACTLY-ONCE here is
 * exactly-once journaling of that INTERNAL record — there is no external system-of-record
 * write yet (the hash-chained audit export / downstream book is a forward item; once one is
 * wired, exactly-once must be re-proven at THAT boundary). PAST-AS-OF striking is BOUNDED
 * (the OIM-111 carry-forward — this workflow strikes the CURRENT NAV; a past-as-of strike
 * needs the as-of-holdings view, forward — the `navData` read refuses a past date on the wire
 * rather than strike an unsound NAV). The §A1 reconciliation is a GENUINE cross-mart check:
 * the gross is rolled up independently from `mart_portfolio_holdings` and reconciled against
 * `mart_fund_nav.gross_market_value` (two marts, two SQL paths — falsifiable), then the §A1
 * identity (NAV = gross + accruals − fees) ties to the mart's published nav_usd; the §A1
 * invariant itself is dbt-enforced upstream (`assert_mart_fund_nav_invariant`).
 * Supervised-autonomous; frontier-only (the strike is deterministic compute over the marts +
 * the gate — no LLM in this workflow).
 */
import { workflow, TerminalError, type WorkflowContext, type WorkflowSharedContext } from '@restatedev/restate-sdk';
import { highStakesApprovalGate, OperationAbortedError } from './approval-gate.js';
import { NAV_DATA_SERVICE, type FundNavComponents, type FundHoldingsGross } from './nav-data-contract.js';

export const NAV_CALCULATION_WORKFLOW_NAME = 'navCalculation';

/**
 * The riskScore the workflow declares for a NAV publish. NAV publication is a regulated,
 * irreversible event → it is HIGH-STAKES by declaration, so the gate FIRES (this is the
 * first REAL high-stakes wiring, distinct from OIM-132's forced-fire test). Fixed at 1.0:
 * the publish is unconditionally high-stakes, not a marginal riskScore. Override via env for
 * a proof that exercises the below-threshold no-op path (not the production behaviour).
 */
export const NAV_PUBLISH_RISK_SCORE = Number(process.env.AGENTINVEST_NAV_PUBLISH_RISK_SCORE ?? 1.0);

/** The input to a NAV strike — the fund to strike (current as-of). */
export interface NavStrikeInput {
  /** The fund to strike, e.g. "PF-0003". */
  fundId: string;
  /**
   * A past-as-of knowledge date. BOUNDED (OIM-111 carry-forward): the latest-holdings path
   * cannot soundly strike a PAST NAV, so a non-null value is REFUSED by the `navData` read
   * (a clean terminal abort), never silently struck. Omit for the current strike.
   */
  navKnowledgeDate?: string | null;
}

/** The HTTP-ish status a clean NAV abort (operator reject / timeout) surfaces as. */
export const NAV_ABORTED_CODE = 403;

/**
 * Raised when a NAV strike is ABORTED at the gate — the operator rejected the publish or the
 * approval timed out. It extends `TerminalError` (a deliberate, FINAL decision, NOT a
 * transient fault → Restate must not retry it, the ingress surfaces a 4xx). NO NAV is
 * published on an abort — the gate precedes the publish step, so a reject/timeout leaves the
 * strike with NO publish record at all.
 */
export class NavAbortedError extends TerminalError {
  readonly abortKind: 'aborted-by-operator' | 'aborted-by-timeout';
  constructor(abortKind: 'aborted-by-operator' | 'aborted-by-timeout', detail?: string) {
    super(
      abortKind === 'aborted-by-operator'
        ? `NAV strike aborted by the operator${detail ? `: ${detail}` : '.'} — NO NAV published.`
        : `NAV strike aborted: no operator decision within the approval timeout${
            detail ? ` (${detail})` : '.'
          } — NO NAV published.`,
      { errorCode: NAV_ABORTED_CODE },
    );
    this.name = 'NavAbortedError';
    this.abortKind = abortKind;
  }
}

/** A journaled NAV step checkpoint — what each durable step recorded. */
export interface NavStepCheckpoint {
  step: 'load-positions' | 'price-positions' | 'apply-fees' | 'roll-up';
  /** A human description of what this checkpoint captured. */
  detail: string;
}

/** The journaled PUBLISH record — the struck NAV. Written exactly-once at the publish step. */
export interface NavPublishRecord {
  kind: 'nav-published';
  workflowId: string;
  fundId: string;
  fundName: string;
  shareClass: string | null;
  nPositions: number;
  /** The struck NAV components (exact decimal strings — no float). */
  grossMarketValue: string;
  accruedIncome: string;
  fees: string;
  /** The struck NAV = gross_market_value + accrued_income − fees (the §A1 identity). */
  navUsd: string;
  /** The mart's published nav_usd this strike reconciled to (equal to navUsd, to the penny). */
  martNavUsd: string;
  /** The awakeable id the operator approved (the audit link from approval → publish). */
  approvedAwakeableId: string;
  struckAt: string;
}

/** The terminal result of a NAV strike. */
export interface NavStrikeResult {
  workflowId: string;
  fundId: string;
  status: 'published';
  /** The struck + published NAV (the §A1 identity value). */
  navUsd: string;
  /** The mart's nav_usd the strike reconciled to (equal to navUsd). */
  martNavUsd: string;
  /** The journaled publish record. */
  publishRecord: NavPublishRecord;
  workflow: typeof NAV_CALCULATION_WORKFLOW_NAME;
}

/** The strike's lifecycle state, queryable via the `status` shared handler. */
export interface NavStrikeState {
  status: 'striking' | 'published' | 'aborted';
  fundId: string;
  /** The ordered step checkpoints recorded so far. */
  checkpoints: NavStepCheckpoint[];
  /** The publish record once published (null until then; null on an abort). */
  publishRecord: NavPublishRecord | null;
  /** Set when the gate aborted the strike (operator reject / timeout). Null otherwise. */
  abort: { kind: 'aborted-by-operator' | 'aborted-by-timeout'; reason: string | null } | null;
}

/** Exact 2-dp money string → integer cents (no binary-float drift). The marts emit decimal(18,2). */
function moneyCents(s: string): bigint {
  const m = /^(-?)(\d+)\.(\d{2})$/.exec(s.trim());
  if (!m) throw new TerminalError(`nav reconcile: non-2dp money value "${s}"`, { errorCode: 422 });
  const sign = m[1] === '-' ? -1n : 1n;
  return sign * (BigInt(m[2]) * 100n + BigInt(m[3]));
}

/** Integer cents → a 2-dp money string. */
function fmtCents(v: bigint): string {
  const neg = v < 0n;
  const a = neg ? -v : v;
  return `${neg ? '-' : ''}${a / 100n}.${(a % 100n).toString().padStart(2, '0')}`;
}

/**
 * The genuine §A1 reconciliation — a FALSIFIABLE cross-mart check, NOT a within-row tautology.
 *
 * Two INDEPENDENT marts / SQL paths:
 *  1. CROSS-MART GROSS — the holdings-derived gross (Σ `mart_portfolio_holdings.market_value_usd`,
 *     `load-positions`) is asserted EQUAL to `mart_fund_nav.gross_market_value` (`price-positions`)
 *     to the penny. The two marts are built by different SQL (the holdings mart ships each
 *     position's abor market value; the NAV mart sums a window-selected E-07 mark rolled to the
 *     fund), so a divergence — a dropped position, a double-counted book, a mis-selected mark —
 *     FAILS here. This is the OIM-111 `assert_marts_reconcile_holdings_to_nav` invariant,
 *     exercised LIVE in the workflow. It can fail on real data — it is not `X == X`.
 *  2. §A1 IDENTITY — NAV = gross + accrued_income − fees, reconciled to the fund-NAV mart's
 *     published `nav_usd`. The §A1 invariant itself (independent NAV re-derivation from source)
 *     is dbt-enforced upstream by `assert_mart_fund_nav_invariant`; this read-consistency check
 *     confirms the read row is internally consistent before the irreversible publish.
 *
 * Any divergence is a TerminalError (the strike aborts cleanly, no retry-storm) — never publish
 * a NAV whose gross does not reconcile across the two marts.
 */
function reconcileNav(
  c: FundNavComponents,
  holdings: FundHoldingsGross,
): { navUsd: string; martNavUsd: string; holdingsGross: string; navMartGross: string } {
  // (1) CROSS-MART GROSS — the independent holdings roll-up vs the NAV mart's gross. The A1
  // tolerance is $0.01 absolute (the ratified NAV-strike tolerance); here on the synthetic seed
  // the two marts tie to the cent, so an exact equality within $0.01 is required.
  const holdingsGross = moneyCents(holdings.holdingsGrossMarketValue);
  const navMartGross = moneyCents(c.grossMarketValue);
  const grossDiff = holdingsGross - navMartGross;
  const grossAbsDiff = grossDiff < 0n ? -grossDiff : grossDiff;
  if (grossAbsDiff > 1n) {
    // Two marts disagree on the fund's gross (|Δ| > $0.01) — the holdings roll-up does not tie
    // to the fund-NAV mart. A real cross-mart divergence: surface it, do not publish.
    throw new TerminalError(
      `nav reconcile FAILED for ${c.fundId}: holdings-mart gross ${fmtCents(holdingsGross)} ` +
        `(Σ mart_portfolio_holdings.market_value_usd) != mart_fund_nav.gross_market_value ` +
        `${fmtCents(navMartGross)} (|Δ| ${fmtCents(grossAbsDiff)} > $0.01). The two marts ` +
        `disagree on the fund's holdings — the struck NAV's gross is not reconciled.`,
      { errorCode: 422 },
    );
  }

  // (2) §A1 IDENTITY — NAV = gross + accruals − fees, reconciled to the mart's published nav_usd.
  const rolledUp = navMartGross + moneyCents(c.accruedIncome) - moneyCents(c.fees);
  const martNav = moneyCents(c.navUsd);
  if (rolledUp !== martNav) {
    throw new TerminalError(
      `nav reconcile FAILED for ${c.fundId}: §A1 identity ${fmtCents(rolledUp)} ` +
        `(gross + accruals − fees) != mart_fund_nav.nav_usd ${fmtCents(martNav)} ` +
        `(gross=${c.grossMarketValue} accruals=${c.accruedIncome} fees=${c.fees}). The struck ` +
        `NAV must BE the marts' §A1 NAV.`,
      { errorCode: 422 },
    );
  }
  return {
    navUsd: fmtCents(rolledUp),
    martNavUsd: fmtCents(martNav),
    holdingsGross: fmtCents(holdingsGross),
    navMartGross: fmtCents(navMartGross),
  };
}

export const navCalculation = workflow({
  name: NAV_CALCULATION_WORKFLOW_NAME,
  handlers: {
    /**
     * Strike a fund's NAV. The single `run` handler: the multi-step journaled strike with the
     * gate at publish. One strike per workflow id (`ctx.key`).
     */
    async run(ctx: WorkflowContext, input: NavStrikeInput): Promise<NavStrikeResult> {
      const workflowId = ctx.key;
      const fundId = input.fundId;
      ctx.console.log(`[nav-calculation] striking NAV for fund=${fundId} workflowId=${workflowId}`);

      const checkpoints: NavStepCheckpoint[] = [];
      ctx.set<NavStrikeState>('state', {
        status: 'striking',
        fundId,
        checkpoints,
        publishRecord: null,
        abort: null,
      });

      // ── READ THE MARTS — TWO INDEPENDENT MARTS for a genuine cross-mart reconcile ──
      // (a) the HOLDINGS mart (`mart_portfolio_holdings`) → the fund's gross rolled up from
      //     the held positions (Σ market_value_usd). The load-positions step's independent
      //     gross derivation.
      // (b) the fund-NAV mart (`mart_fund_nav`) → the per-fund §A1 components (gross, accruals,
      //     fees, the published nav_usd). The roll-up reconciles (a) against (b)'s gross — two
      //     marts, two SQL paths, a FALSIFIABLE cross-mart check (NOT X==X).
      // Both are DIRECT `ctx.serviceClient(...)` calls — the legal Restate journaling shape (the
      // RPC results are journaled; on replay they are read back, the marts NOT re-queried). A
      // past-as-of date is REFUSED on the wire (the OIM-111 bound, now forwarded by the navData
      // handler) — surfaced here as a clean terminal abort. The workflow does NOT compute the
      // NAV — it READS the marts and reconciles them.
      const navDataClient = ctx.serviceClient(NAV_DATA_SERVICE);
      const holdings = (await navDataClient.getFundHoldingsGross({ fundId })) as FundHoldingsGross;
      const components = (await navDataClient.getFundNavComponents({
        fundId,
        navKnowledgeDate: input.navKnowledgeDate ?? null,
      })) as FundNavComponents;
      ctx.console.log(
        `[nav-calculation] marts read: ${components.fundName} (${components.nPositions} positions); ` +
          `holdings_gross=${holdings.holdingsGrossMarketValue} (Σ mart_portfolio_holdings); ` +
          `nav_mart_gross=${components.grossMarketValue} accruals=${components.accruedIncome} ` +
          `fees=${components.fees} mart_nav=${components.navUsd} (computedBy=${components.computedBy}).`,
      );

      // ── STEP 1 — LOAD-POSITIONS (a journaled checkpoint) ──────────────────────
      // Rolls up the fund's gross market value INDEPENDENTLY from the HOLDINGS mart
      // (`mart_portfolio_holdings`) — the figure the roll-up reconciles against the fund-NAV
      // mart's gross (the genuine cross-mart check).
      const loadCp = await ctx.run('load-positions', (): NavStepCheckpoint => {
        const cp: NavStepCheckpoint = {
          step: 'load-positions',
          detail:
            `loaded ${holdings.nPositions} held position(s) for ${holdings.fundName} (${fundId}), ` +
            `current as-of; rolled up gross ${holdings.holdingsGrossMarketValue} USD ` +
            `independently from mart_portfolio_holdings (Σ market_value_usd)`,
        };
        ctx.console.log(`[nav-calculation] STEP load-positions: ${cp.detail}`);
        return cp;
      });
      checkpoints.push(loadCp);

      // ── STEP 2 — PRICE-POSITIONS (a journaled checkpoint) ─────────────────────
      // The fund-NAV mart's gross (the §A1 NAV mart's own gross_market_value), the other side
      // of the cross-mart reconciliation in roll-up.
      const priceCp = await ctx.run('price-positions', (): NavStepCheckpoint => {
        const cp: NavStepCheckpoint = {
          step: 'price-positions',
          detail: `priced positions: gross market value ${components.grossMarketValue} USD (mart_fund_nav.gross_market_value, Σ each holding's E-07 mark)`,
        };
        ctx.console.log(`[nav-calculation] STEP price-positions: ${cp.detail}`);
        return cp;
      });
      checkpoints.push(priceCp);

      // ── STEP 3 — APPLY-FEES (a journaled checkpoint) ──────────────────────────
      const feesCp = await ctx.run('apply-fees', (): NavStepCheckpoint => {
        const cp: NavStepCheckpoint = {
          step: 'apply-fees',
          detail: `applied fees: ${components.fees} USD (structurally present; zero on this synthetic seed — no fee source)`,
        };
        ctx.console.log(`[nav-calculation] STEP apply-fees: ${cp.detail}`);
        return cp;
      });
      checkpoints.push(feesCp);

      // ── STEP 4 — ROLL-UP + GENUINE CROSS-MART §A1 RECONCILE (a journaled checkpoint) ──
      // The FALSIFIABLE cross-mart reconciliation (two marts, two SQL paths): the
      // load-positions holdings-derived gross (Σ mart_portfolio_holdings) is asserted EQUAL to
      // mart_fund_nav.gross_market_value to the penny; then NAV = gross + accruals − fees is the
      // §A1 identity, reconciled to the mart's published nav_usd. Per-fund single-class (the
      // seed has no share classes). A divergence (the two marts disagree on the gross, or the
      // identity breaks) throws inside the closure (a TerminalError) → the strike aborts
      // cleanly, surfacing the divergence rather than publishing a non-reconciling NAV.
      const rollUp = await ctx.run('roll-up', () => {
        const recon = reconcileNav(components, holdings);
        ctx.console.log(
          `[nav-calculation] STEP roll-up: CROSS-MART gross reconcile — holdings ` +
            `${recon.holdingsGross} (Σ mart_portfolio_holdings) == mart_fund_nav.gross ` +
            `${recon.navMartGross} ✓; then NAV = ${recon.navMartGross} + ${components.accruedIncome} ` +
            `− ${components.fees} = ${recon.navUsd} USD; RECONCILES to mart_fund_nav.nav_usd ` +
            `${recon.martNavUsd} (§A1, per-fund single-class).`,
        );
        return recon;
      });
      checkpoints.push({
        step: 'roll-up',
        detail:
          `cross-mart reconcile: holdings gross ${rollUp.holdingsGross} == mart_fund_nav.gross ` +
          `${rollUp.navMartGross}; rolled up NAV ${rollUp.navUsd} USD; reconciles to ` +
          `mart_fund_nav.nav_usd ${rollUp.martNavUsd} (§A1)`,
      });
      ctx.set<NavStrikeState>('state', {
        status: 'striking',
        fundId,
        checkpoints,
        publishRecord: null,
        abort: null,
      });

      // ── [GATE] — HIGH-STAKES APPROVAL before the irreversible PUBLISH ─────────
      // The FIRST REAL wiring of the OIM-132 gate at an irreversible step (REUSED, NOT
      // re-implemented). NAV publication is high-stakes by DECLARATION → the gate FIRES (a
      // high riskScore). It PAUSES on a durable `ctx.awakeable`, notifies the operator (a
      // journaled record + the awakeable id, resolved via the Restate CLI/admin), and awaits
      // with a durable timeout. APPROVE → publish runs. REJECT → terminal abort, NO publish.
      // TIMEOUT → terminal abort, NO publish. The gate PRECEDES the publish step, so a
      // reject/timeout leaves the strike with NO publish record (never a half-published NAV).
      // The aborted state is journaled BEFORE re-throwing the terminal error, so `status`
      // surfaces the clean aborted outcome (replay reads it back; no retry-storm).
      let approvedAwakeableId: string;
      try {
        const outcome = await highStakesApprovalGate(
          ctx,
          workflowId,
          {
            riskScore: NAV_PUBLISH_RISK_SCORE,
            summary: `Publish NAV ${rollUp.navUsd} USD for ${components.fundName} (${fundId}) — irreversible, regulated.`,
            stepCount: checkpoints.length,
            selectedSoIds: ['nav-publish'],
          },
          NAV_CALCULATION_WORKFLOW_NAME,
        );
        // The gate fires (high-stakes by declaration), so an approve returns gated:true with
        // the awakeable id. (A defensive fallback keeps a below-threshold override — a
        // proof-only no-op path — from crashing; production always fires.)
        approvedAwakeableId = outcome.gated ? outcome.awakeableId : 'not-gated';
      } catch (err) {
        if (err instanceof OperationAbortedError) {
          ctx.set<NavStrikeState>('state', {
            status: 'aborted',
            fundId,
            checkpoints,
            publishRecord: null,
            abort: { kind: err.abortKind, reason: err.message },
          });
          ctx.console.warn(
            `[nav-calculation] ABORTED at the gate (${err.abortKind}) — NO NAV published for ${fundId}.`,
          );
          // Re-throw as a NAV-specific terminal abort — NO publish ran (the gate precedes it).
          throw new NavAbortedError(err.abortKind, err.message);
        }
        throw err;
      }

      // PROOF-ONLY SEAM — env-gated durable pause in the between-APPROVAL-and-PUBLISH window.
      // It exists SOLELY so the publish-exactly-once proof can SIGKILL the workflow AFTER the
      // operator approved (the decision journaled) but BEFORE the publish `ctx.run` records
      // the NAV. On resume the journaled decision is read back and the publish runs ONCE.
      // NO-OP in production: AGENTINVEST_NAV_PREPUBLISH_CRASH_DELAY_MS is unset everywhere
      // except the crash-proof harness → the `ctx.sleep` is never reached, no journal entry
      // added, the journal shape identical to production.
      const prePublishCrashDelayMs = Number(process.env.AGENTINVEST_NAV_PREPUBLISH_CRASH_DELAY_MS ?? 0);
      if (prePublishCrashDelayMs > 0) {
        ctx.console.warn(
          `[nav-calculation] PROOF-ONLY durable pause ${prePublishCrashDelayMs}ms ` +
            `(AGENTINVEST_NAV_PREPUBLISH_CRASH_DELAY_MS set) — crash window between the approved ` +
            `decision and the publish. Never set in production.`,
        );
        await ctx.sleep(prePublishCrashDelayMs);
      }

      // The strike timestamp — read as a TOP-LEVEL journaled action (NOT inside the publish
      // `ctx.run` closure: a context action nested in a `ctx.run` body is the Restate
      // determinism anti-pattern). On replay the journaled timestamp is read back, so the
      // published record's `struckAt` is stable across a crash (exactly-once).
      const struckAtMs = await ctx.date.now();

      // ── PUBLISH — strike the NAV + write the journaled publish record (EXACTLY-ONCE) ──
      // The publish is a single journaled `ctx.run`: a crash AFTER it reads the journaled
      // record back, it does NOT re-publish (exactly-once is the durable-execution guarantee
      // — the record's RESULT is journaled, replay returns it without re-running the body).
      const publishRecord = await ctx.run('publish', (): NavPublishRecord => {
        const record: NavPublishRecord = {
          kind: 'nav-published',
          workflowId,
          fundId,
          fundName: components.fundName,
          shareClass: components.shareClass,
          nPositions: components.nPositions,
          grossMarketValue: components.grossMarketValue,
          accruedIncome: components.accruedIncome,
          fees: components.fees,
          navUsd: rollUp.navUsd,
          martNavUsd: rollUp.martNavUsd,
          approvedAwakeableId,
          struckAt: new Date(struckAtMs).toISOString(),
        };
        ctx.console.warn(
          `[nav-calculation] PUBLISH (exactly-once): NAV ${record.navUsd} USD struck + journaled for ` +
            `${record.fundName} (${fundId}). ${JSON.stringify(record)}`,
        );
        return record;
      });

      ctx.set<NavStrikeState>('state', {
        status: 'published',
        fundId,
        checkpoints,
        publishRecord,
        abort: null,
      });

      return {
        workflowId,
        fundId,
        status: 'published',
        navUsd: publishRecord.navUsd,
        martNavUsd: publishRecord.martNavUsd,
        publishRecord,
        workflow: NAV_CALCULATION_WORKFLOW_NAME,
      };
    },

    /**
     * Read the recorded strike state for this workflow id — a shared (read-only) query
     * handler. Returns null if no strike has run under this id. Used by the proof to read the
     * published NAV back (the exactly-once + reconciliation evidence).
     */
    async status(ctx: WorkflowSharedContext): Promise<NavStrikeState | null> {
      return (await ctx.get<NavStrikeState>('state')) ?? null;
    },
  },
});
