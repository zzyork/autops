import type { CheckId } from './inspections'

export type CapabilityStatus = 'untested' | 'passed' | 'failed'
export type ModelProtocol = 'openai_compatible' | 'anthropic'

export interface ModelConnectionInput {
  name: string
  protocol: ModelProtocol
  base_url: string
  model: string
  api_key: string
  is_default: boolean
}
export interface ModelConnection extends Omit<ModelConnectionInput, 'api_key'> {
  id: number
  has_api_key: boolean
  chat_status: CapabilityStatus
  tool_status: CapabilityStatus
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
export interface InspectionProposal {
  id: string
  name: string
  hosts: { id: number; version: number; name: string; address: string }[]
  checks: CheckId[]
  status: 'pending' | 'confirmed' | 'cancelled'
  task_id: string | null
}
export interface ChatSession extends SessionSummary {
  messages: ChatMessage[]
  proposals: InspectionProposal[]
}
