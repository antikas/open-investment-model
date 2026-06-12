/**
 * `parsePlan` — a thin, dependency-free defensive parse of a returned plan.
 *
 * The Python `PlanSchema` (Pydantic) is the schema SSOT: the `agentinvestPlanner` returns
 * an ALREADY-VALIDATED plan. This parser is the orchestrator's defensive check
 * before it trusts that JSON — it confirms the structural shape (`steps` is a
 * non-empty array of `{soId, args}`; `riskScore` is a number in [0,1]) and throws
 * a `TerminalError` on a malformed plan (a deterministic failure re-running cannot
 * fix — never a retry storm). No zod / new dependency: a hand-written structural
 * check, the cheapest thing that meets "the TS side parses the returned plan".
 *
 * It does NOT re-implement the Python validation (that is the SSOT); it guards the
 * orchestrator against a contract drift / a non-conforming response surfacing as a
 * silent bad plan downstream.
 */
import { TerminalError } from '@restatedev/restate-sdk';
import type { Plan, PlanStep } from './llm-service-contract.js';

function fail(detail: string): never {
  // A malformed plan is a deterministic contract failure — TerminalError so
  // Restate does not retry it (a re-call returns the same malformed shape).
  throw new TerminalError(`planTask returned a malformed plan: ${detail}`, { errorCode: 422 });
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/**
 * Structurally validate a returned plan (the Python schema is the SSOT; this is
 * the orchestrator's defensive parse). Returns the typed `Plan` or throws a
 * `TerminalError`.
 */
export function parsePlan(raw: unknown): Plan {
  if (!isObject(raw)) fail(`expected an object, got ${typeof raw}`);
  const steps = raw.steps;
  if (!Array.isArray(steps) || steps.length === 0) {
    fail('steps must be a non-empty array');
  }
  const parsedSteps: PlanStep[] = steps.map((s, i) => {
    if (!isObject(s)) fail(`step[${i}] is not an object`);
    if (typeof s.soId !== 'string' || s.soId.length === 0) {
      fail(`step[${i}].soId must be a non-empty string`);
    }
    const args = s.args;
    if (args !== undefined && !isObject(args)) {
      fail(`step[${i}].args must be an object when present`);
    }
    const rationale = s.rationale;
    if (rationale !== undefined && rationale !== null && typeof rationale !== 'string') {
      fail(`step[${i}].rationale must be a string when present`);
    }
    return {
      soId: s.soId,
      args: (args as Record<string, unknown>) ?? {},
      rationale: (rationale as string | null | undefined) ?? null,
    };
  });

  const riskScore = raw.riskScore;
  if (typeof riskScore !== 'number' || Number.isNaN(riskScore) || riskScore < 0 || riskScore > 1) {
    fail('riskScore must be a number in [0,1]');
  }

  const summary = raw.summary;
  if (summary !== undefined && summary !== null && typeof summary !== 'string') {
    fail('summary must be a string when present');
  }

  return {
    steps: parsedSteps,
    riskScore,
    summary: (summary as string | null | undefined) ?? null,
  };
}
