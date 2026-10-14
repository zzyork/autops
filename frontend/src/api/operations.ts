import type {
  OperationCatalog, OperationInspectInput, OperationInspection, OperationModuleId,
  OperationPlanInput, OperationResolveInput, OperationTask,
} from '@/types/operations'
import { get, request } from './http'
import { rememberSSHOperation, withSSHIdentities } from './sshIdentity'
import type { SSHIdentityOptions } from '@/types/sshIdentity'

// Preparing a plan performs synchronous remote prechecks across selected hosts.
const PLAN_TIMEOUT_MS = 20 * 60_000

export const getOperationCatalog = () => get<OperationCatalog>('/operations/catalog')
export const inspectOperation = (body: OperationInspectInput, options: SSHIdentityOptions = {}) =>
  withSSHIdentities([{ target_type: 'host', target_id: body.host_id }], () => request<OperationInspection>('/operations/inspect', { method: 'POST', body, timeoutMs: 90_000, signal: options.signal }), options)
export const prepareOperation = (body: OperationPlanInput, options: SSHIdentityOptions = {}) =>
  withSSHIdentities(body.host_ids.map((id) => ({ target_type: 'host', target_id: id })), () => request<OperationTask>('/operations/plans', { method: 'POST', body, timeoutMs: PLAN_TIMEOUT_MS, signal: options.signal }), options)
export async function confirmOperation(id: string, options: SSHIdentityOptions = {}) {
  const task = await getOperationTask(id)
  const confirmed = await withSSHIdentities(task.hosts.map((host) => ({ target_type: 'host', target_id: host.host_id })),
    () => request<OperationTask>(`/operations/tasks/${encodeURIComponent(id)}/confirm`, {
      method: 'POST', body: { confirmation: id, impact_ack: true }, timeoutMs: 60_000, signal: options.signal,
    }), options)
  rememberSSHOperation(confirmed.id)
  return confirmed
}
export const getOperationTask = (id: string) => get<OperationTask>(`/operations/tasks/${encodeURIComponent(id)}`)
export const resolveOperationHost = (id: string, hostId: number, note: string) => request<OperationTask>(`/operations/tasks/${encodeURIComponent(id)}/hosts/${encodeURIComponent(hostId)}/resolve`, {
  method: 'POST', body: { confirmation: id, remote_stopped: true, note } satisfies OperationResolveInput,
})
