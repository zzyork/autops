import type { CheckId } from './inspections'

export type CapabilityStatus = 'untested' | 'passed' | 'failed'
export type ModelProtocol = 'openai_compatible' | 'anthropic'

export const MIN_OUTPUT_TOKENS = 1024
export const MAX_OUTPUT_TOKENS = 65_535

export interface ModelConnectionInput {
  name: string
  protocol: ModelProtocol
  base_url: string
  model: string
  api_key: string
  is_default: boolean
  is_backup: boolean
}
export interface ModelConnection extends Omit<ModelConnectionInput, 'api_key'> {
  id: number
  has_api_key: boolean
  chat_status: CapabilityStatus
  tool_status: CapabilityStatus
}
export interface FeatureModelsConfig {
  chat_connection_id: number | null
  inspection_report_connection_id: number | null
  chat_max_tokens: number
  inspection_report_max_tokens: number
}
export interface SessionSummary {
  id: string
  title: string
  connection_id: number
  created_at: string
  updated_at: string
}
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  status: 'completed' | 'failed' | 'interrupted'
}
export interface MessageBranchInput {
  include_message: boolean
}
export interface MessageRegenerationInput {
  content: string
  expected_updated_at: string
  operation_id?: string
}
export type OperationStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'unknown' | 'interrupted'
export type OperationResultStatus = Exclude<OperationStatus, 'interrupted'> | 'skipped'
export interface OperationExecution {
  status: OperationStatus
  error_code: string | null
  hosts: {
    id: number
    name: string
    address: string
    status: OperationResultStatus
    error_code: string | null
    steps: {
      name: string
      status: OperationResultStatus
      exit_status: number | null
      error_code: string | null
      stdout: string
      stderr: string
    }[]
  }[]
}
export interface InspectionProposal {
  id: string
  kind: 'inspection' | 'operation'
  name: string
  hosts: { id: number; version: number; name: string; address: string }[]
  checks: CheckId[]
  status: 'pending' | 'confirmed' | 'cancelled'
  task_id: string | null
  commands: { name: string; command: string; timeout_seconds: number }[]
  execution: OperationExecution | null
}
export interface ChatSession extends SessionSummary {
  messages: ChatMessage[]
  proposals: InspectionProposal[]
  proposal_message_ids: Record<string, string>
}

export interface SessionActivity {
  running: boolean
  stopping: boolean
}
