import type {
  OperationCatalog, OperationInspectInput, OperationInspection, OperationModuleId,
  OperationPlanInput, OperationResolveInput, OperationTask, OperationTaskSummary, OperationBlocker, OperationSnapshot,
} from '@/types/operations'
import type { PageResponse } from '@/types/api'
import { get, HttpError, request, streamEvents } from './http'
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
export const recoverOperation = (hostId: number, module: OperationModuleId, actions: string[], scope: 'attention' | 'latest') =>
  get<{ task: OperationTaskSummary | null }>(`/operations/tasks?${new URLSearchParams([
    ['host_id', String(hostId)], ['module', module], ['scope', scope], ...actions.map((action): [string, string] => ['actions', action]),
  ]).toString()}`)
export const getOperationBlockers = (hostId: number, page: number, pageSize: number) =>
  get<PageResponse<OperationBlocker>>(`/operations/hosts/${hostId}/blockers?page=${page}&page_size=${pageSize}`)

const statuses = ['planned', 'queued', 'running', 'succeeded', 'failed', 'partial', 'unknown', 'interrupted', 'expired']
const hostStatuses = ['planned', 'queued', 'running', 'succeeded', 'failed', 'unknown', 'interrupted']
const stepStatuses = ['pending', 'running', 'succeeded', 'failed', 'unknown']
const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
function snapshot(value: unknown, id: string, hostId: number): value is OperationSnapshot {
  return record(value) && value.task_id === id && typeof value.status === 'string' && statuses.includes(value.status)
    && Array.isArray(value.hosts) && value.hosts.length === 1 && value.hosts.every((host: unknown) => record(host)
      && host.host_id === hostId && typeof host.status === 'string' && hostStatuses.includes(host.status)
      && typeof host.identity_required === 'boolean' && (host.resolved_at === null || typeof host.resolved_at === 'string')
      && Array.isArray(host.steps) && host.steps.every((step: unknown) => record(step)
        && Number.isSafeInteger(step.position) && typeof step.position === 'number' && step.position >= 0
        && typeof step.title === 'string' && typeof step.status === 'string' && stepStatuses.includes(step.status)
        && typeof step.stdout === 'string' && step.stdout.length <= 8192 && typeof step.stderr === 'string' && step.stderr.length <= 8192
        && (step.exit_status === null || typeof step.exit_status === 'number' && Number.isSafeInteger(step.exit_status))))
}
export const watchOperation = (id: string, hostId: number, signal: AbortSignal, onSnapshot: (value: OperationSnapshot, done: boolean) => void) =>
  streamEvents(`/operations/tasks/${encodeURIComponent(id)}/events?host_id=${hostId}`, {
    method: 'GET', signal, connectTimeoutMs: 10_000, idleTimeoutMs: 45_000,
    onEvent: (event, value) => {
      if (event === 'error' || (event !== 'snapshot' && event !== 'done') || !snapshot(value, id, hostId)) throw new HttpError()
      onSnapshot(value, event === 'done')
      return event === 'done'
    },
  })
export const resolveOperationHost = (id: string, hostId: number, note: string) => request<OperationTask>(`/operations/tasks/${encodeURIComponent(id)}/hosts/${encodeURIComponent(hostId)}/resolve`, {
  method: 'POST', body: { confirmation: id, remote_stopped: true, note } satisfies OperationResolveInput,
})
