export type ExecutionStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'unknown'
export type StepStatus = ExecutionStatus | 'skipped'

export interface ExecutionState {
  id: string
  status: ExecutionStatus
  error_code: string | null
  started_at: string | null
  finished_at: string | null
}

export interface StepState {
  id: number
  status: StepStatus
  exit_status: number | null
  error_code: string | null
  started_at: string | null
  finished_at: string | null
}

export interface ExecutionSummary extends ExecutionState {
  name: string
  host_id: number
  host_name: string
  address: string
  step_count: number
  created_at: string
}

export interface ExecutionStep extends StepState {
  position: number
  name: string
  command: string
  success_exit_codes: number[]
  timeout_seconds: number
  stdout: string
  stderr: string
}

export interface ExecutionDetail extends ExecutionSummary {
  timeout_seconds: number
  sequence: number
  steps: ExecutionStep[]
}

export interface ExecutionInput {
  id: string
  name: string
  host: { id: number; version: number }
  timeout_seconds: number
  steps: { name: string; command: string; success_exit_codes: number[]; timeout_seconds: number }[]
}

export type ExecutionEvent =
  | { kind: 'state'; sequence: number; execution: ExecutionState; steps: StepState[] }
  | { kind: 'output'; sequence: number; step_id: number; stream: 'stdout' | 'stderr'; text: string }
  | { kind: 'done'; sequence: number; execution: ExecutionState }
