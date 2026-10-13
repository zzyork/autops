export type CheckId = 'server_info' | 'system_resources' | 'service_status' | 'network_info' | 'log_error'
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
export interface LogRules { days: number; lines: number; paths: string[] }
export interface InspectionConfig {
  thresholds: Thresholds
  services: ServiceSpec[]
  logs: LogRules
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

export type AnalysisStatus = 'not_generated' | 'unavailable' | 'queued' | 'running' | 'completed' | 'failed' | 'interrupted'
export type AnalysisSeverity = 'critical' | 'warning' | 'info'
export interface AnalysisIssue {
  title: string
  severity: AnalysisSeverity
  analysis: string
  recommendation: string
  evidence_ids: string[]
  log_source: string | null
  log_message: string | null
  diagnostic_group?: DiagnosticGroup | null
  diagnostic_groups?: DiagnosticGroup[]
}
export interface DiagnosticObservation {
  host_name: string
  address: string
  source: string
  occurrences: number
  first_time: string | null
  last_time: string | null
}
export interface DiagnosticGroup {
  id: string
  template: string
  service: string | null
  occurrences: number
  host_count: number
  observations: DiagnosticObservation[]
}
export interface AnalysisEvidence {
  id: string
  kind: 'host' | 'check' | 'finding' | 'log'
  host_name: string
  address: string
  check_title: string
  source: string
  content: string
  severity: AnalysisSeverity
  incomplete: boolean
  limited: boolean
  group_id: string | null
  original_lines?: string[]
  original_indices?: number[]
  source_table_index?: number | null
}
export interface AnalysisReport {
  task_name: string
  task_status: RunStatus
  inspection_started_at: string | null
  inspection_finished_at: string | null
  check_ids: CheckId[]
  summary: string
  issues: AnalysisIssue[]
  evidence: AnalysisEvidence[]
  host_count: number
  finding_count: number
  log_count: number
  incomplete_count: number
  unassessed_count: number
  generated_at: string
  model_name: string
  model_version: number
}
export interface AnalysisResponse {
  task_id: string
  status: AnalysisStatus
  model_name: string | null
  model_version: number | null
  started_at: string | null
  finished_at: string | null
  error_code: string | null
  report: AnalysisReport | null
  can_generate: boolean
  progress: {
    phase: 'analyzing' | 'summarizing'
    completed_batches: number
    total_batches: number
    current_step: string
    step_started_at: string
  } | null
}
