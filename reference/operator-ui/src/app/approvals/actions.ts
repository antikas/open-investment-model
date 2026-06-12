'use server';

/**
 * Server actions for the Approvals queue. These run ON THE SERVER (the `'use server'`
 * boundary) — the browser posts the form, the server resolves the awakeable on the
 * ingress. No Restate URL or secret crosses to the client; the action is the whole
 * trust boundary.
 *
 * The decision is recorded at the AWAKEABLE (the OIM-132 gate's path of record):
 * approve → the paused workflow proceeds; reject → it aborts (`aborted-by-operator`,
 * no publish). The registry entry is then marked resolved so the queue refreshes.
 */
import { revalidatePath } from 'next/cache';
import { decideApproval } from '@/lib/restate';

export async function approve(formData: FormData): Promise<void> {
  const operationId = String(formData.get('operationId') ?? '');
  const awakeableId = String(formData.get('awakeableId') ?? '');
  const origin = String(formData.get('origin') ?? '');
  const reason = String(formData.get('reason') ?? '').trim() || null;
  if (!operationId || !awakeableId) throw new Error('approve: missing operationId/awakeableId');
  await decideApproval(operationId, awakeableId, true, reason, origin);
  revalidatePath('/approvals');
}

export async function reject(formData: FormData): Promise<void> {
  const operationId = String(formData.get('operationId') ?? '');
  const awakeableId = String(formData.get('awakeableId') ?? '');
  const origin = String(formData.get('origin') ?? '');
  const reason = String(formData.get('reason') ?? '').trim() || null;
  if (!operationId || !awakeableId) throw new Error('reject: missing operationId/awakeableId');
  await decideApproval(operationId, awakeableId, false, reason, origin);
  revalidatePath('/approvals');
}
