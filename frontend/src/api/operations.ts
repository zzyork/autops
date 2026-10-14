import type {
  OperationCatalog, OperationInspectInput, OperationInspection, OperationModuleId,
  OperationPlanInput, OperationResolveInput, OperationTask, OperationTaskPage,
} from '@/types/operations'
import { get, request } from './http'

// Preparing a plan performs synchronous remote prechecks across selected hosts.
const PLAN_TIMEOUT_MS = 20 * 60_000

export const getOperationCatalog = () => get<OperationCatalog>('/operations/catalog')
export const inspectOperation = (body: OperationInspectInput) => request<OperationInspection>('/operations/inspect', { method: 'POST', body, timeoutMs: 90_000 })
export const prepareOperation = (body: OperationPlanInput) => request<OperationTask>('/operations/plans', { method: 'POST', body, timeoutMs: PLAN_TIMEOUT_MS })
export const confirmOperation = (id: string) => request<OperationTask>(`/operations/tasks/${encodeURIComponent(id)}/confirm`, {
  method: 'POST', body: { confirmation: id, impact_ack: true }, timeoutMs: 60_000,
})
export const getOperationTask = (id: string) => get<OperationTask>(`/operations/tasks/${encodeURIComponent(id)}`)
export const resolveOperationHost = (id: string, hostId: number, note: string) => request<OperationTask>(`/operations/tasks/${encodeURIComponent(id)}/hosts/${encodeURIComponent(hostId)}/resolve`, {
  method: 'POST', body: { confirmation: id, remote_stopped: true, note } satisfies OperationResolveInput,
})
export function listOperationTasks(module: OperationModuleId | null, page: number, pageSize: number) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (module) params.set('module', module)
  return get<OperationTaskPage>(`/operations/tasks?${params}`)
}
