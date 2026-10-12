export type CheckId = 'server_info' | 'system_resources' | 'service_status' | 'network_info'
export type RunStatus = 'queued' | 'running' | 'completed' | 'partial' | 'failed' | 'interrupted'
export type CheckStatus = 'queued' | 'running' | 'completed' | 'failed' | 'skipped' | 'interrupted'
export type Conclusion = 'normal' | 'warning' | 'critical' | 'not_applicable' | 'unknown'

export interface Thresholds {
  cpu_warning: number
  cpu_critical: number
  mem_warning: number
  mem_critical: number
  disk_warning: number
  disk_critical: number
  swap_warning: number
  swap_critical: number
}
export interface ServiceSpec { name: string; candidates: string[]; required: boolean }
export interface InspectionConfig {
  thresholds: Thresholds
  services: ServiceSpec[]
  command_timeout_seconds: number
  host_timeout_seconds: number
}
export interface HostSelection { id: number; version: number }
export interface InspectionInput {
  name: string
  hosts: HostSelection[]
  checks: CheckId[]
}
export interface Metric { name: string; value: string | number | null; unit: string | null }
export interface ResultTable { name: string; columns: string[]; rows: string[][] }
export interface Finding { severity: 'warning' | 'critical'; message: string }
export interface CheckPayload {
  conclusion: Conclusion
  metrics: Metric[]
  tables: ResultTable[]
  findings: Finding[]
}
export interface CheckResponse {
  check_id: CheckId
  title: string
  status: CheckStatus
  conclusion: Conclusion
  started_at: string | null
  finished_at: string | null
  error_code: string | null
  payload: CheckPayload
}
export interface HostRunResponse {
  id: string
  host_id: number
  host_name: string
  address: string
  port: number
  username: string
  group_name: string
  status: RunStatus
  failure_code: string | null
  started_at: string | null
  finished_at: string | null
  checks: CheckResponse[]
}
export interface TaskSummary {
  id: string
  name: string
  status: RunStatus
  check_ids: CheckId[]
  host_count: number
  completed_hosts: number
  failed_hosts: number
  created_at: string
  started_at: string | null
  finished_at: string | null
}
export interface TaskDetail extends TaskSummary {
  rule_version: string
  config: InspectionConfig
  hosts: HostRunResponse[]
}
export interface TaskPage { items: TaskSummary[]; total: number }
export interface CheckDefinition { id: CheckId; title: string; description: string }
export interface InspectionCatalog { checks: CheckDefinition[]; defaults: InspectionConfig }
export interface ReportResponse { filename: string; content: string }
