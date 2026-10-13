import type { AnalysisResponse, InspectionCatalog, InspectionConfig, InspectionInput, ReportResponse, TaskDetail, TaskPage } from '@/types/inspections'
import { get, request } from './http'

export const getInspectionCatalog = () => get<InspectionCatalog>('/inspections/catalog')
export const updateInspectionCatalog = (body: InspectionConfig) => request<InspectionCatalog>('/inspections/catalog', { method: 'PUT', body })
export const createInspectionTask = (body: InspectionInput) => request<TaskDetail>('/inspections/tasks', { method: 'POST', body })
export function listInspectionTasks(limit: number, offset: number, recordsOnly = false) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (recordsOnly) params.set('records_only', 'true')
  return get<TaskPage>(`/inspections/tasks?${params}`)
}
export const getInspectionTask = (id: string) => get<TaskDetail>(`/inspections/tasks/${encodeURIComponent(id)}`)
export const deleteInspectionTask = (id: string) => request<void>(`/inspections/tasks/${encodeURIComponent(id)}`, { method: 'DELETE' })
export const getInspectionReport = (id: string) => get<ReportResponse>(`/inspections/tasks/${encodeURIComponent(id)}/report`)
export const getInspectionAnalysis = (id: string) => get<AnalysisResponse>(`/inspections/tasks/${encodeURIComponent(id)}/analysis`)
export const generateInspectionAnalysis = (id: string) => request<AnalysisResponse>(`/inspections/tasks/${encodeURIComponent(id)}/analysis`, { method: 'POST' })
