/**
 * The PENDING-APPROVALS REGISTRY — a thin, ADDITIVE read-surface over the
 * high-stakes approval gate (seam 3, OIM-132), built so a human surface (the
 * Operator UI's Approvals queue) can ENUMERATE the live approvals awaiting a
 * decision WITHOUT the raw Restate CLI/awakeable API.
 *
 * WHY THIS EXISTS. The gate's operator-notify is a JOURNALED LOG RECORD (the
 * `approval-notify` ctx.run in approval-gate.ts) — it carries the operationId,
 * the awakeable id, the plan summary and the riskScore, but it is only readable
 * by tailing the handler log, not queryable. The Restate admin API can list
 * SUSPENDED invocations, but it does not carry the plan summary / riskScore /
 * awakeable-id correlation a human needs to make the call. This registry is the
 * missing READ INDEX: the gate ALSO records each notice here (a fire-and-forget
 * send), and a resolution marks it resolved — so a surface can list exactly the
 * pending approvals, with the fields the operator reads, from one query.
 *
 * ADDITIVE — THE GATE'S SEMANTICS ARE FROZEN (the OIM-142 constraint). The gate's
 * pause/resolve/timeout behaviour is UNCHANGED: the registry write is a top-level
 * FIRE-AND-FORGET send (`ctx.objectSendClient(...).register(...)`) that the gate
 * does not await and whose outcome the gate does not depend on. The gate still
 * pauses on the SAME durable awakeable, still resolves via the SAME ingress
 * awakeable path, still aborts on the SAME durable timeout. The registry is a
 * passive mirror of the gate's already-journaled notice — never a second control
 * path, never a second source of truth for the decision (the awakeable IS the
 * decision; this is only the list of WHAT is awaiting one). If the registry write
 * is lost, the gate is unaffected; the awakeable id in the log is still the
 * resolve path of record.
 *
 * THE DECISION STILL HAPPENS AT THE AWAKEABLE. Approving/rejecting is STILL the
 * `POST {ingress}/restate/awakeables/{id}/resolve|reject` call — the registry does
 * NOT resolve the gate. The Operator UI reads the pending list HERE, then resolves
 * the AWAKEABLE on the ingress (the gate's own path), then marks this entry
 * resolved so the list reflects the new state. The registry is a list, not a lock.
 *
 * KEYING. A virtual object keyed by operationId (one approval per operation in
 * flight at a time — the gate fires once per operation). Single-writer-per-key
 * serialises a register racing a resolve for the same operation. A service-level
 * reader (`listPending`) is hosted by a sibling SERVICE so a surface can read the
 * whole pending set in one call without a key.
 */
import {
  object,
  service,
  type ObjectContext,
  type Context,
  type VirtualObjectDefinition,
  type WorkflowDefinition,
} from '@restatedev/restate-sdk';

export const APPROVAL_REGISTRY_OBJECT = 'approvalRegistry';
export const APPROVAL_REGISTRY_READER = 'approvalRegistryReader';

/** The state held under the SET key — the index of every operationId the gate has notified about. */
const PENDING_INDEX_KEY = 'index';
/** The well-known SET key the reader/index live under (one shared object key for the whole index). */
export const APPROVAL_INDEX_KEY = '__index__';

/**
 * One pending-approval entry — the human-readable view of a gate notice, plus its
 * lifecycle status. Mirrors the gate's `ApprovalNotice` (approval-gate.ts) with the
 * status the surface needs to show pending vs resolved.
 */
export interface PendingApproval {
  /** The operation/workflow id the gate paused (the VO/workflow key). */
  operationId: string;
  /** The awakeable id the operator resolves via the ingress (the resolve path of record). */
  awakeableId: string;
  /** The plan's riskScore that fired the gate. */
  riskScore: number;
  /** The high-stakes threshold the riskScore crossed. */
  threshold: number;
  /** A one-line human summary of what is awaiting approval. */
  summary: string | null;
  /** How many steps the gated plan has. */
  stepCount: number;
  /** The tool soIds the plan selected. */
  selectedSoIds: string[];
  /** Which surface raised it (e.g. the orchestrator vs the NAV workflow). */
  origin: string;
  /** ISO timestamp the gate raised the approval. */
  raisedAt: string;
  /** pending → awaiting an operator decision; resolved → a decision was recorded. */
  status: 'pending' | 'resolved';
  /** How a resolved entry was decided (null while pending). */
  decision?: 'approved' | 'rejected' | 'aborted' | null;
  /** ISO timestamp the entry was marked resolved (null while pending). */
  resolvedAt?: string | null;
}

/** The payload the gate sends to register a new pending approval (status defaulted to pending). */
export type RegisterApprovalInput = Omit<PendingApproval, 'status' | 'decision' | 'resolvedAt'>;

/**
 * The per-operation registry object. Holds this operation's current approval entry
 * (or null) and maintains membership in the shared pending index so the reader can
 * enumerate the set. Keyed by operationId.
 */
export const approvalRegistry = object({
  name: APPROVAL_REGISTRY_OBJECT,
  handlers: {
    /**
     * Record (or refresh) the pending approval for this operationId — called by the
     * gate as a FIRE-AND-FORGET send right after it journals its operator-notify. Stores
     * the entry as pending and adds the operationId to the shared pending index. The gate
     * does not await this; a failure here never affects the gate.
     */
    async register(ctx: ObjectContext, input: RegisterApprovalInput): Promise<void> {
      const entry: PendingApproval = { ...input, status: 'pending', decision: null, resolvedAt: null };
      ctx.set<PendingApproval>('entry', entry);
      // Maintain membership in the shared index object (a different key on the same VO type).
      ctx.objectSendClient<typeof approvalRegistry>({ name: APPROVAL_REGISTRY_OBJECT }, APPROVAL_INDEX_KEY).addToIndex(
        input.operationId,
      );
      ctx.console.log(`[approval-registry] registered pending approval ${input.operationId} (awakeable ${input.awakeableId}).`);
    },

    /**
     * Mark this operation's approval resolved with a decision. Two writers can race on the
     * same entry for the same operation: the gate's own terminal-path mark
     * (`markRegistryResolved`, fire-and-forget on approve/reject/timeout) and the Operator
     * UI's post-resolve mark. The single-writer-per-key VO serialises them in ISSUE order.
     *
     * TERMINAL-TRUTH-WINS (OIM-142 cycle-4, fold P-MINOR-1 residual). The recorded decision must
     * be the operation's TERMINAL TRUTH regardless of the order in which the two writers arrive —
     * NOT merely the first writer (cycle-3's first-writer-wins was order-based, and order is not
     * guaranteed across two fire-and-forget issuers). The two writers are NOT symmetric: the gate's
     * `'aborted'` mark (issued ONLY by the durable-timeout path, approval-gate.ts) is the
     * operation's terminal ground truth; the UI's `'approved'`/`'rejected'` mark is the operator's
     * intent, which a decide/timeout race can make stale. So `'aborted'` DOMINATES — it wins the
     * label whenever it arrives, even on an already-`resolved` entry; a non-`'aborted'` decision
     * never overrides an already-recorded `'aborted'`:
     *   - no entry → no-op (never fabricates a decision; the awakeable is the decision path);
     *   - entry still `pending` → apply the decision (the first terminal write);
     *   - SAME decision as recorded → idempotent no-op (a duplicate/late send changes nothing);
     *   - incoming `'aborted'` on a recorded non-`'aborted'` (`approved`/`rejected`) → OVERRIDE to
     *     `'aborted'` and log the correction. This closes BOTH orderings of the decide/timeout race:
     *       • gate-marks-first → entry is `aborted`; a late UI `approved` does not override it (next
     *         bullet) → label `aborted` (the cycle-3 forward case, unregressed);
     *       • UI-marks-first → entry is `approved`/`rejected` on a pending row; the gate's later
     *         `aborted` mark THEN overrides it → label `aborted` (the cycle-3 residual, now closed).
     *   - incoming non-`'aborted'` on a recorded `'aborted'` → IGNORE-with-log (a late UI mark after
     *     the gate already recorded the terminal `aborted` stays ignored — keeps a genuine timeout
     *     abort honest);
     *   - incoming non-`'aborted'` differing from a recorded non-`'aborted'` (e.g. `approved` then
     *     `rejected`) → not a reachable gate/UI conflict (one operator decision per awakeable; the
     *     gate marks `approved` XOR `rejected` XOR `aborted` per outcome) → first-writer-wins, log
     *     the ignored late write (defensive only). The ONLY override allowed is non-`aborted` → `aborted`.
     *
     * SAFETY — the override cannot corrupt a GENUINE decision. An `'aborted'` mark is produced by
     * exactly ONE source: the gate's durable-timeout path (approval-gate.ts `markRegistryResolved(
     * ...,'aborted')`). The UI never sends `'aborted'` (it sends `approved`/`rejected` only). A
     * genuine approve/reject never issues an `'aborted'` mark, so the operator's label always stands.
     *
     * We do NOT throw on a conflicting late write: the gate's mark is fire-and-forget, and a throw
     * would surface as a failed invocation on the gate's notify path — keep it a clean
     * reconcile-with-log. The awakeable remains the SOLE decision-of-record; this is only the
     * read-mirror's resolved-trail label.
     */
    async resolve(ctx: ObjectContext, input: { decision: 'approved' | 'rejected' | 'aborted'; at?: string }): Promise<void> {
      const entry = await ctx.get<PendingApproval>('entry');
      if (!entry) return;
      // Already resolved: terminal-truth-wins — the gate's `aborted` dominates whatever order it arrives.
      if (entry.status === 'resolved') {
        if (entry.decision === input.decision) return; // same decision → idempotent no-op
        if (input.decision === 'aborted' && entry.decision !== 'aborted') {
          // The gate's terminal `aborted` (timeout path) arrived AFTER a recorded non-`aborted`
          // decision (the UI-marks-first race). It is the ground truth — OVERRIDE the label.
          const was = entry.decision;
          entry.decision = 'aborted';
          entry.resolvedAt = input.at ?? new Date(await ctx.date.now()).toISOString();
          ctx.set<PendingApproval>('entry', entry);
          ctx.console.log(
            `[approval-registry] overrode-with-terminal for ${entry.operationId}: ` +
              `recorded-was=${was} now=aborted operationId=${entry.operationId}.`,
          );
          return;
        }
        // A non-`aborted` late write that does NOT carry the terminal truth (a late UI mark after a
        // recorded `aborted`, or the defensive approved-vs-rejected pair). Keep the recorded decision; log it.
        ctx.console.log(
          `[approval-registry] reconciled conflicting late decision for ${entry.operationId}: ` +
            `recorded=${entry.decision} ignored-late=${input.decision} operationId=${entry.operationId}.`,
        );
        return;
      }
      // First terminal write on a still-pending entry — record it.
      entry.status = 'resolved';
      entry.decision = input.decision;
      entry.resolvedAt = input.at ?? new Date(await ctx.date.now()).toISOString();
      ctx.set<PendingApproval>('entry', entry);
      ctx.console.log(`[approval-registry] resolved ${entry.operationId} as ${input.decision}.`);
    },

    /** Read this operation's approval entry (or null). */
    async get(ctx: ObjectContext): Promise<PendingApproval | null> {
      return (await ctx.get<PendingApproval>('entry')) ?? null;
    },

    /** Index maintenance — add an operationId to the shared membership set (called on the __index__ key). */
    async addToIndex(ctx: ObjectContext, operationId: string): Promise<void> {
      const idx = (await ctx.get<string[]>(PENDING_INDEX_KEY)) ?? [];
      if (!idx.includes(operationId)) {
        idx.push(operationId);
        ctx.set<string[]>(PENDING_INDEX_KEY, idx);
      }
    },

    /** Read the shared membership set of every operationId the gate has notified about. */
    async readIndex(ctx: ObjectContext): Promise<string[]> {
      return (await ctx.get<string[]>(PENDING_INDEX_KEY)) ?? [];
    },
  },
});

/** A pending approval enriched with its entry detail — what the reader returns to a surface. */
export type ApprovalListItem = PendingApproval;

/**
 * LIVENESS RECONCILE (OIM-142 cycle-2, fix #2) — the read-only liveness contract.
 *
 * A `pending` row must correspond to a GENUINELY-SUSPENDED workflow. The gate's
 * terminal-path resolve-marks (approval-gate.ts) keep the registry true to the world
 * for every path the gate itself processes; this is the DEFENCE-IN-DEPTH that covers
 * the one residual edge the gate-mark cannot (a crash AFTER the awakeable resolves but
 * BEFORE the gate's fire-and-forget resolve-mark send journals). The reader cross-checks
 * each pending entry against the operation's ACTUAL recorded state and DROPS (ages out)
 * any whose operation is terminal or gone — exactly as the Operations dashboard already
 * self-heals against stale registry ids. READ-ONLY: it filters the list it returns; it
 * NEVER mutates the registry entry (the gate-mark is the writer; the awakeable is the
 * decision of record).
 *
 * The op's recorded `status` is the liveness signal: a workflow paused AT the gate is
 * still in-flight — `running` (investmentOperation, written before the gate fires) or
 * `striking` (navCalculation, written at strike start). A TERMINAL op reads
 * `completed`/`aborted`/`published`; a GONE op reads `null`. So a pending entry is
 * "genuinely live" iff its op status is non-terminal-and-present; anything terminal or
 * gone is aged out of the pending list. A transient/unreadable status is treated as
 * LIVE (kept) — never hide a genuinely-pending approval on a read hiccup.
 */
/** TERMINAL op states — an entry whose op is in one of these is aged out of `pending`. */
const TERMINAL_STATUSES = new Set(['completed', 'aborted', 'published']);

/**
 * Type-only handles for the two gated VOs' read-only `status` handlers — declared
 * locally (the established `*-contract.ts` pattern) so the reader can cross-check an
 * operation's live state WITHOUT importing the heavy workflow/VO modules (which import
 * the gate, which imports this registry — a cycle). Each carries only the `status`
 * shape the reconcile reads.
 */
type StatusView = { status?: string | null } | null;
/** The minimal handler map the reconcile calls — only the read-only `status` handler. */
type StatusHandlers = { status: (ctx: Context) => Promise<StatusView> };
const INVESTMENT_OPERATION_STATUS: VirtualObjectDefinition<'investmentOperation', StatusHandlers> = {
  name: 'investmentOperation',
};
const NAV_CALCULATION_STATUS: WorkflowDefinition<'navCalculation', StatusHandlers> = {
  name: 'navCalculation',
};

/**
 * Read one gated operation's live recorded status (read-only), dispatching on the
 * entry's `origin` (the surface that raised it). Returns the status string, `null` if
 * the op is gone, or `undefined` if the read failed (transient) — the caller treats
 * `undefined` as LIVE (keep the entry) so a read hiccup never hides a live approval.
 */
async function readOperationStatus(ctx: Context, entry: PendingApproval): Promise<string | null | undefined> {
  try {
    if (entry.origin === 'navCalculation') {
      const state = await ctx.workflowClient(NAV_CALCULATION_STATUS, entry.operationId).status();
      return state?.status ?? null;
    }
    const state = await ctx.objectClient(INVESTMENT_OPERATION_STATUS, entry.operationId).status();
    return state?.status ?? null;
  } catch {
    return undefined; // transient/unreadable — treat as live (do not hide a pending approval)
  }
}

/**
 * The registry READER service — a keyless surface so a UI can enumerate the whole
 * approval set in one call. It reads the shared membership index, then fans out a
 * read of each operation's entry, and returns them split into pending vs resolved.
 * Read-only; it never resolves anything (the awakeable is the decision path).
 */
export const approvalRegistryReader = service({
  name: APPROVAL_REGISTRY_READER,
  handlers: {
    /**
     * List every approval the gate has recorded, newest first, split into pending
     * (awaiting an operator decision) and resolved (a decision recorded). The Approvals
     * queue renders `pending`; `resolved` is the recent-decisions trail.
     *
     * Before returning, the pending set is reconciled for LIVENESS (OIM-142 cycle-2):
     * any pending entry whose operation is TERMINAL (resolved out-of-band — a crash
     * between the awakeable resolve and the gate's resolve-mark) or GONE is aged out, so
     * a pending row is always a genuinely-suspended workflow. Read-only filtering — the
     * registry entry is not mutated (the gate marks it; the awakeable decides).
     */
    async list(ctx: Context): Promise<{ pending: ApprovalListItem[]; resolved: ApprovalListItem[] }> {
      const index = await ctx
        .objectClient<typeof approvalRegistry>({ name: APPROVAL_REGISTRY_OBJECT }, APPROVAL_INDEX_KEY)
        .readIndex();
      const entries = await Promise.all(
        index.map((operationId) =>
          ctx.objectClient<typeof approvalRegistry>({ name: APPROVAL_REGISTRY_OBJECT }, operationId).get(),
        ),
      );
      const all = entries.filter((e): e is PendingApproval => e !== null);
      all.sort((a, b) => (a.raisedAt < b.raisedAt ? 1 : -1));

      const registryPending = all.filter((e) => e.status === 'pending');
      const resolved = all.filter((e) => e.status === 'resolved');

      // Liveness reconcile (read-only): cross-check each registry-pending entry against its
      // op's actual recorded state; keep only entries whose op is genuinely live-at-the-gate.
      // The reads fan out in parallel (each a journaled request-response RPC to the op's
      // read-only `status` handler) and the registry-pending set is small in steady state
      // (resolved entries leave via the gate's terminal-path mark, so they are not re-read
      // here). A transient/unreadable status keeps the entry — never hide a live approval.
      const liveness = await Promise.all(registryPending.map((e) => readOperationStatus(ctx, e)));
      const pending = registryPending.filter((_, i) => {
        const st = liveness[i];
        if (st === undefined) return true; // transient read — keep (never hide a live approval)
        if (st === null) return false; // op gone — age out
        if (TERMINAL_STATUSES.has(st)) return false; // op terminal — age out (resolved out-of-band)
        return true; // live/in-flight (running/striking) — keep
      });

      return { pending, resolved };
    },
  },
});
