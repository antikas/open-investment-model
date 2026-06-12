/**
 * Crash-replay probe endpoint (the killable process for the real-process-crash
 * replay proof).
 *
 * This is a STANDALONE endpoint process that hosts ONE instrumented virtual
 * object, `crashReplayProbe`. It is started as a child by the crash-replay
 * controller, registered against the shared Restate, then SIGKILLed mid-operation
 * and restarted — to prove the durable-execution guarantee under a REAL process
 * crash (distinct from an in-process forced-throw):
 *
 *   1. `runWithSideEffectStep` journals ONE durable step via `ctx.run(...)`. The
 *      step's body appends a line to a side-effect log file and returns a UUID.
 *      Because the body ran, the log gains exactly one line and the UUID is
 *      recorded in the Restate journal.
 *   2. After journaling, the handler waits on a FILE-BASED gate (it polls for a
 *      "release" file) so the controller has a window to SIGKILL this process
 *      while the operation is mid-flight — step journaled, invocation NOT yet
 *      complete.
 *   3. The controller SIGKILLs this process, then restarts it (a fresh process)
 *      and re-registers. Restate, seeing an incomplete invocation, RESUMES it —
 *      replaying the journal. The `ctx.run` step is read back from the journal,
 *      NOT re-executed, so the side-effect log gains NO new line and the UUID is
 *      unchanged. The handler then sees the release file (written by the
 *      controller before restart) and completes, returning the journaled UUID.
 *
 * The proof of "the journaled step was NOT re-run" is the side-effect log: it
 * holds exactly ONE line across the whole crash-and-restart, even though the
 * handler body re-entered on the resumed process. The UUID returned after the
 * restart equals the one journaled before the crash.
 *
 * The side-effect log + the gate + release file paths are passed by env so the
 * controller and this process agree on them.
 */
import { appendFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http2';
import { endpoint as restateEndpoint, object, type ObjectContext } from '@restatedev/restate-sdk';
import {
  awaitAdminReady,
  isWindowsWsl2Host,
  registerDeployment,
  resolveDeployUrl,
} from '../substrate/restate-reach.js';

const PROBE_NAME = 'crashReplayProbe';
const PROBE_PORT = Number(process.env.AGENTINVEST_CRASH_PROBE_PORT ?? 9094);

const SIDE_EFFECT_LOG = required('CRASH_PROBE_SIDE_EFFECT_LOG');
const RELEASE_FILE = required('CRASH_PROBE_RELEASE_FILE');
const READY_FILE = required('CRASH_PROBE_READY_FILE');

function required(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`crash-replay-endpoint: missing required env ${name}`);
  return v;
}

interface RunResult {
  key: string;
  /** The UUID journaled by the side-effecting step (stable across replay). */
  stepId: string;
  /** How many lines the side-effect log holds when the handler returns. */
  sideEffectLines: number;
}

const crashReplayProbe = object({
  name: PROBE_NAME,
  handlers: {
    async runWithSideEffectStep(ctx: ObjectContext): Promise<RunResult> {
      // ONE durable step with a VISIBLE side effect. If Restate ever re-executes
      // this step (it must not, on replay), the log gains a second line.
      const stepId = await ctx.run('side-effecting-step', () => {
        const id = crypto.randomUUID();
        appendFileSync(SIDE_EFFECT_LOG, `step-ran ${id}\n`);
        return id;
      });

      // Wait on the file gate so the controller can SIGKILL mid-operation: the
      // step is journaled, but the invocation has not completed. After a restart
      // the controller writes the release file, and the resumed invocation
      // proceeds past this gate.
      while (!existsSync(RELEASE_FILE)) {
        await new Promise((res) => setTimeout(res, 200));
      }

      const lines = readFileSync(SIDE_EFFECT_LOG, 'utf8').split('\n').filter(Boolean).length;
      return { key: ctx.key, stepId, sideEffectLines: lines };
    },
  },
});

async function main(): Promise<void> {
  const e = restateEndpoint().bind(crashReplayProbe);
  const bind = isWindowsWsl2Host() ? '0.0.0.0' : '127.0.0.1';
  const server = createServer(e.http2Handler());
  await new Promise<void>((resolve, reject) => {
    const onError = (err: Error): void => {
      server.off('error', onError);
      reject(err);
    };
    server.once('error', onError);
    server.listen({ port: PROBE_PORT, host: bind }, () => {
      server.off('error', onError);
      resolve();
    });
  });
  process.stderr.write(`[crash-replay-endpoint] listening on ${bind}:${PROBE_PORT} (pid ${process.pid})\n`);

  await awaitAdminReady();
  const id = await registerDeployment(resolveDeployUrl(PROBE_PORT));
  process.stderr.write(`[crash-replay-endpoint] registered deployment ${id}\n`);

  // Signal readiness to the controller by writing the ready file. The controller
  // waits for it before invoking, on both the initial start and the restart.
  writeFileSync(READY_FILE, `${process.pid}\n`);
  process.stderr.write(`[crash-replay-endpoint] ready (wrote ${READY_FILE})\n`);

  // Hold the process open; the controller SIGKILLs it.
  await new Promise(() => {});
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  process.stderr.write(`[crash-replay-endpoint] ${msg}\n`);
  process.exit(1);
});
