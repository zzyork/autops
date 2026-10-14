import type { AnalysisResponse, InspectionCatalog, InspectionConfig, InspectionInput, ReportResponse, TaskDetail, TaskPage } from '@/types/inspections'
import { get, getBlob, request } from './http'
import { rememberSSHOperation, withSSHIdentities } from './sshIdentity'
import type { SSHIdentityOptions } from '@/types/sshIdentity'

export const getInspectionCatalog = () => get<InspectionCatalog>('/inspections/catalog')
export const updateInspectionCatalog = (body: InspectionConfig) => request<InspectionCatalog>('/inspections/catalog', { method: 'PUT', body })
export async function createInspectionTask(body: InspectionInput, options: SSHIdentityOptions = {}) {
  const task = await withSSHIdentities(body.hosts.map((host) => ({ target_type: 'host', target_id: host.id, version: host.version })),
    () => request<TaskDetail>('/inspections/tasks', { method: 'POST', body, signal: options.signal }), options)
  rememberSSHOperation(task.id)
  return task
}
export function listInspectionTasks(limit: number, offset: number, recordsOnly = false) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (recordsOnly) params.set('records_only', 'true')
  return get<TaskPage>(`/inspections/tasks?${params}`)
}
export const getInspectionTask = (id: string) => get<TaskDetail>(`/inspections/tasks/${encodeURIComponent(id)}`)
export const deleteInspectionTask = (id: string) => request<void>(`/inspections/tasks/${encodeURIComponent(id)}`, { method: 'DELETE' })
export const getInspectionReport = (id: string) => get<ReportResponse>(`/inspections/tasks/${encodeURIComponent(id)}/report`)
export const getInspectionReportArchive = (id: string) => getBlob(`/inspections/tasks/${encodeURIComponent(id)}/reports/archive`, 'application/zip')
export const getInspectionAnalysis = (id: string) => get<AnalysisResponse>(`/inspections/tasks/${encodeURIComponent(id)}/analysis`)
export const generateInspectionAnalysis = (id: string) => request<AnalysisResponse>(`/inspections/tasks/${encodeURIComponent(id)}/analysis`, { method: 'POST' })
