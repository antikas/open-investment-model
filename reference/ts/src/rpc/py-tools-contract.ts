/**
 * Typed cross-language RPC contract — the TS↔Python seam.
 *
 * This is the load-bearing proof that a TypeScript handler invokes a
 * Python handler over Restate's typed RPC, payloads round-tripping as typed
 * structures. Every later cross-language call — a Python tool invoked from the
 * TS orchestrator — rides on exactly this seam.
 *
 * Topology: `pyTools` is a model-free Restate *service* — a
 * namespace + dispatch boundary in the Python tool+data layer — NOT an "agent".
 * It carries no reasoning loop.
 *
 * How the typing works across the language boundary:
 *  - The Python side (reference/python) registers a real Restate service named
 *    `pyTools` with a `computeSimpleReturn` handler. Restate serialises payloads
 *    as JSON over the wire.
 *  - The TS side does NOT import Python. It declares a *type-only* service
 *    definition handle (this file) describing the service name + each handler's
 *    typed input/output. `ctx.serviceClient(PY_TOOLS)` then gives a fully typed
 *    client: TS gets compile-time types on the request and the response, and
 *    Restate routes the call to the Python service. The shared contract IS the
 *    type boundary — drift between this file and the Python handler is a
 *    contract break the smoke test catches at runtime.
 *
 * This is genuine cross-language typed RPC over the durable substrate, not an
 * HTTP shim: the call goes through `ctx.serviceClient(...).handler(input)`,
 * Restate's own service-to-service path, journaled like any other step.
 */
import type { Context, ServiceDefinition } from '@restatedev/restate-sdk';

/** The Python tool service name, shared by both sides as the routing key. */
export const PY_TOOLS_SERVICE_NAME = 'pyTools';

/** Input to the Python `computeSimpleReturn` tool — typed on both sides. */
export interface SimpleReturnInput {
  /** Beginning market value. */
  beginningValue: number;
  /** Ending market value. */
  endingValue: number;
  /** External cash flow over the period (positive = contribution). */
  cashFlow: number;
}

/** Output of the Python `computeSimpleReturn` tool — typed on both sides. */
export interface SimpleReturnResult {
  /** The simple (Dietz-style) period return as a decimal fraction. */
  simpleReturn: number;
  /** Which language + service computed it — proves the boundary was crossed. */
  computedBy: 'python:pyTools';
  /** Echo of the inputs, so the round-trip is inspectable end-to-end. */
  echo: SimpleReturnInput;
}

/**
 * The shape of the Python service's handlers, expressed in TS so the TS caller
 * is typed. The handler signature mirrors the Restate TS service-definition
 * convention (a `Context` first arg, the typed input second, a Promise of the
 * typed output). The TS side never runs this code — it only uses the types.
 */
export type PyToolsHandlers = {
  computeSimpleReturn: (ctx: Context, input: SimpleReturnInput) => Promise<SimpleReturnResult>;
};

/**
 * The typed, type-only service-definition handle the TS side passes to
 * `ctx.serviceClient(...)`. `ServiceDefinition<name, handlers>` is `{ name }`
 * carrying the handler types in its generic — exactly what `serviceClient`
 * expects for a service whose implementation lives behind the wire (here: in
 * another language). `name` is the runtime routing key; the generic gives the
 * TS caller compile-time types on the request and response.
 */
export const PY_TOOLS: ServiceDefinition<typeof PY_TOOLS_SERVICE_NAME, PyToolsHandlers> = {
  name: PY_TOOLS_SERVICE_NAME,
};
