export type OperationModuleId = 'hostname' | 'packages' | 'firewall' | 'kernel' | 'system' | 'disk'
export type OperationFieldKind = 'text' | 'textarea' | 'number' | 'boolean' | 'select'
export type OperationValue = string | number | boolean | null

export interface OperationField {
  key: string
  label: string
  kind: OperationFieldKind
  required: boolean
  description?: string
  options?: { label: string; value: string | number | boolean }[]
  default?: OperationValue
}

export interface OperationAction {
  id: string
  title: string
  description: string
  destructive: boolean
  fields: OperationField[]
}

export interface OperationModule {
  id: OperationModuleId
  title: string
  actions: OperationAction[]
}

export interface OperationCatalog { modules: OperationModule[] }
export interface OperationInspectInput { module: OperationModuleId; host_id: number }
export interface OperationInspection { host_id: number; host_name: string; module: OperationModuleId; output: string }
export interface OperationPlanInput {
  module: OperationModuleId
  action: string
  host_ids: number[]
  params: Record<string, OperationValue>
}

export type OperationTaskStatus = 'planned' | 'queued' | 'running' | 'succeeded' | 'failed' | 'partial' | 'unknown' | 'interrupted' | 'expired'
export type OperationHostStatus = 'planned' | 'queued' | 'running' | 'succeeded' | 'failed' | 'unknown' | 'interrupted'
export type OperationStepStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'unknown'

export interface OperationStep {
  title: string
  status: OperationStepStatus
  stdout: string | null
  stderr: string | null
  exit_status: number | null
}

export interface OperationTaskHost {
  host_id: number
  host_name: string
  address: string
  status: OperationHostStatus
  before: string | null
  after: string | null
  error: string | null
  identity_required: boolean
  resolved_at: string | null
  resolution_note: string | null
  steps: OperationStep[]
}

export interface OperationResolveInput { confirmation: string; remote_stopped: true; note: string }

export interface OperationTask {
  id: string
  module: OperationModuleId
  action: string
  title: string
  status: OperationTaskStatus
  created_at: string
  confirmed_at: string | null
  completed_at: string | null
  params: Record<string, OperationValue>
  hosts: OperationTaskHost[]
}

export interface OperationTaskSummary { id: string; module: OperationModuleId; action: string; title: string; status: OperationTaskStatus }
export interface OperationBlocker { task_id: string; module: OperationModuleId; action: string; title: string; confirmed_at: string; status: OperationHostStatus }
export interface OperationEventStep { position: number; title: string; status: OperationStepStatus; stdout: string; stderr: string; exit_status: number | null }
export interface OperationEventHost { host_id: number; status: OperationHostStatus; identity_required: boolean; resolved_at: string | null; steps: OperationEventStep[] }
export interface OperationSnapshot { task_id: string; status: OperationTaskStatus; hosts: OperationEventHost[] }
