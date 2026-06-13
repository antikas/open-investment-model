/**
 * Typed cross-language RPC contract for the `navData` service — the NAV-strike workflow's
 * marts-read seam.
 *
 * The `navCalculation` workflow (TS) reads the per-fund §A1 NAV components from the
 * `mart_fund_nav` mart. The mart lives in the Python data layer (duckdb), so the workflow
 * calls the Python `navData.getFundNavComponents` handler over Restate's typed RPC (the same
 * `ctx.serviceClient(...)` path the `bd09` / `pyTools` / planner contracts use). The TS side
 * does NOT import Python — it declares a type-only service-definition handle describing the
 * service name + the handler's typed I/O, and `ctx.serviceClient(NAV_DATA_SERVICE)` gives a
 * typed client routed to the Python service.
 *
 * REUSE, NOT RE-IMPLEMENTATION. The NAV is computed by the dbt marts (`mart_fund_nav`: NAV =
 * Σ gross_market_value + accruals − fees, §A1). This seam READS those components; the
 * workflow checkpoints them and reconciles its roll-up to the mart's published `navUsd`. The
 * workflow does NOT re-price or re-compute the NAV.
 *
 * Handler name discipline. The wire routing key is the name the Python side REGISTERS the
 * handler under: `nav_data_service.py` registers it as
 * `@navData.handler(name="getFundNavComponents")`, so the routed call is
 * `.getFundNavComponents(...)` (camelCase, as registered — matching the `pyTools`
 * camelCase-handler convention, distinct from `bd09`'s snake_case `execute_so`).
 *
 * Topology: `navData` is a model-free Restate *service* — a data tool boundary.
 * It carries NO reasoning loop.
 *
 * Schema SSOT: the Python `nav_data_service.py` (`FundNavComponentsResult`) is the authority;
 * this file mirrors its shape as TS types for the caller. Every money figure is an exact
 * decimal STRING (no float drift across the boundary).
 */
import type { Context, ServiceDefinition } from '@restatedev/restate-sdk';

/** The Python navData service name — the routing key shared by both sides. */
export const NAV_DATA_SERVICE_NAME = 'navData';

/** The `getFundNavComponents` request — the fund to strike (current as-of). */
export interface FundNavComponentsRequest {
  /** The fund to strike, e.g. 'PF-0003'. */
  fundId: string;
  /**
   * A past-as-of knowledge date. BOUNDED: a non-null value is REFUSED
   * by the Python read (the latest-holdings path cannot soundly strike a past NAV) — a clean
   * terminal error, never a silently-struck unsound NAV. Null/omitted → the current strike.
   */
  navKnowledgeDate?: string | null;
}

/**
 * The per-fund NAV components read from `mart_fund_nav`. Every money figure is an exact
 * decimal string (no float). `grossMarketValue + accruedIncome − fees` recomputes `navUsd`
 * to the penny — the §A1 identity the workflow asserts at roll-up.
 */
export interface FundNavComponents {
  fundId: string;
  fundName: string;
  shareClass: string | null;
  nPositions: number;
  grossMarketValue: string;
  accruedIncome: string;
  fees: string;
  /** The mart's PUBLISHED nav_usd — what the workflow's roll-up reconciles to. */
  navUsd: string;
  /** Which language + service read it (e.g. `python:navData`). */
  computedBy: string;
}

/** The `getFundHoldingsGross` request — the fund whose held positions to roll up. */
export interface FundHoldingsGrossRequest {
  /** The fund to roll up, e.g. 'PF-0003'. */
  fundId: string;
}

/**
 * The fund's gross market value rolled up INDEPENDENTLY from `mart_portfolio_holdings` —
 * Σ each held position's `market_value_usd` from the HOLDINGS mart (a different mart + SQL
 * path from `mart_fund_nav`'s gross). The workflow's load-positions step reads this and
 * reconciles it against `mart_fund_nav.gross_market_value` — the genuine, falsifiable
 * cross-mart check (two marts, two paths), NOT a within-row re-read of one row.
 */
export interface FundHoldingsGross {
  fundId: string;
  fundName: string;
  nPositions: number;
  /** Σ the holdings mart's `market_value_usd` over the fund (the independently-derived gross). */
  holdingsGrossMarketValue: string;
  /** Which language + service read it (e.g. `python:navData`). */
  computedBy: string;
}

/**
 * The Python `navData` handlers, expressed in TS so the caller is typed. The keys are the
 * REGISTERED wire names (camelCase), so the routed calls are `.getFundNavComponents(...)` and
 * `.getFundHoldingsGross(...)`.
 */
export type NavDataHandlers = {
  getFundNavComponents: (ctx: Context, req: FundNavComponentsRequest) => Promise<FundNavComponents>;
  getFundHoldingsGross: (ctx: Context, req: FundHoldingsGrossRequest) => Promise<FundHoldingsGross>;
};

/**
 * The type-only service-definition handle passed to `ctx.serviceClient(...)`. The `name` is
 * the runtime routing key; the generic gives the TS caller compile-time types on the request
 * and response. The implementation lives behind the wire (in Python).
 */
export const NAV_DATA_SERVICE: ServiceDefinition<typeof NAV_DATA_SERVICE_NAME, NavDataHandlers> = {
  name: NAV_DATA_SERVICE_NAME,
};
