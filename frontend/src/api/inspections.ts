import type { InspectionCatalog, InspectionInput, ReportResponse, TaskDetail, TaskPage } from '@/types/inspections'
import { get, request } from './http'

export const getInspectionCatalog = () => get<InspectionCatalog>('/inspections/catalog')
export const createInspectionTask = (body: InspectionInput) => request<TaskDetail>('/inspections/tasks', { method: 'POST', body })
export function listInspectionTasks(limit: number, offset: number) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  return get<TaskPage>(`/inspections/tasks?${params}`)
}
export const getInspectionTask = (id: string) => get<TaskDetail>(`/inspections/tasks/${encodeURIComponent(id)}`)
export const getInspectionReport = (id: string) => get<ReportResponse>(`/inspections/tasks/${encodeURIComponent(id)}/report`)
