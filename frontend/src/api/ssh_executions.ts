import { HttpError, request, streamEvents } from './http'
import { withSSHIdentities } from './sshIdentity'
import type { SSHIdentityOptions } from '@/types/sshIdentity'
import type { PageResponse } from '@/types/api'
import type { ExecutionDetail, ExecutionEvent, ExecutionInput, ExecutionState, ExecutionStep, ExecutionSummary, StepState } from '@/types/sshExecutions'

const PATH = '/ssh/executions'
const isRecord = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const integer = (value: unknown, min: number, max = Number.MAX_SAFE_INTEGER): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= min && value <= max
const text = (value: unknown): value is string => typeof value === 'string'
const nullableText = (value: unknown): value is string | null => value === null || text(value)
const executionStatus = (value: unknown) => value === 'queued' || value === 'running' || value === 'succeeded' || value === 'failed' || value === 'unknown'
const stepStatus = (value: unknown) => executionStatus(value) || value === 'skipped'

function executionState(value: unknown): value is ExecutionState {
  return isRecord(value) && text(value.id) && executionStatus(value.status) && nullableText(value.error_code)
    && nullableText(value.started_at) && nullableText(value.finished_at)
}
function stepState(value: unknown): value is StepState {
  return isRecord(value) && integer(value.id, 1) && stepStatus(value.status)
    && (value.exit_status === null || integer(value.exit_status, 0, 0xffffffff))
    && nullableText(value.error_code) && nullableText(value.started_at) && nullableText(value.finished_at)
}
function summary(value: unknown): value is ExecutionSummary {
  return executionState(value) && isRecord(value) && text(value.name) && integer(value.host_id, 1)
    && text(value.host_name) && text(value.address) && integer(value.step_count, 1, 20) && text(value.created_at)
}
function step(value: unknown): value is ExecutionStep {
  return stepState(value) && isRecord(value) && integer(value.position, 0, 19)
    && text(value.name) && text(value.command) && Array.isArray(value.success_exit_codes)
    && value.success_exit_codes.length >= 1 && value.success_exit_codes.length <= 16
    && value.success_exit_codes.every((code: unknown) => integer(code, 0, 255))
    && new Set(value.success_exit_codes).size === value.success_exit_codes.length
    && integer(value.timeout_seconds, 1, 600) && text(value.stdout) && text(value.stderr)
}
function detail(value: unknown): value is ExecutionDetail {
  return summary(value) && isRecord(value) && integer(value.timeout_seconds, 10, 1800)
    && integer(value.sequence, 0) && Array.isArray(value.steps) && value.steps.length === value.step_count
    && value.steps.every(step) && value.steps.every((item: ExecutionStep, index: number) => item.position === index)
    && new Set(value.steps.map((item: ExecutionStep) => item.id)).size === value.steps.length
}
function requireDetail(value: unknown): ExecutionDetail {
  if (!detail(value)) throw new HttpError()
  return value
}

export async function listExecutions(page: number, size: number): Promise<PageResponse<ExecutionSummary>> {
  const value = await request<unknown>(`${PATH}?page=${page}&page_size=${size}`)
  if (!isRecord(value) || !Array.isArray(value.items) || !integer(value.total, 0) || !value.items.every(summary)) throw new HttpError()
  return { items: value.items, total: value.total }
}
export async function getExecution(id: string, signal?: AbortSignal): Promise<ExecutionDetail> {
  return requireDetail(await request<unknown>(`${PATH}/${encodeURIComponent(id)}`, { signal }))
}
export async function createExecution(body: ExecutionInput, options: SSHIdentityOptions = {}): Promise<ExecutionDetail> {
  const value = await withSSHIdentities([{ target_type: 'host', target_id: body.host.id, version: body.host.version }],
    () => request<unknown>(PATH, { method: 'POST', body, signal: options.signal }), options)
  const result = requireDetail(value)
  if (result.id !== body.id) throw new HttpError()
  return result
}
export async function deleteExecution(id: string): Promise<void> {
  await request<unknown>(`${PATH}/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function subscribeExecution(id: string, after: number, signal: AbortSignal, onEvent: (event: ExecutionEvent) => void): Promise<void> {
  return streamEvents(`${PATH}/${encodeURIComponent(id)}/events?after=${after}`, {
    method: 'GET', signal, connectTimeoutMs: 8000, idleTimeoutMs: 45000,
    onEvent: (kind, value) => {
      if (kind === 'error') throw new HttpError()
      if (!isRecord(value) || !integer(value.sequence, 1)) throw new HttpError()
      if (kind === 'state' && executionState(value.execution) && Array.isArray(value.steps) && value.steps.every(stepState)) {
        onEvent({ kind, sequence: value.sequence, execution: value.execution, steps: value.steps })
        return false
      }
      if (kind === 'output' && integer(value.step_id, 1) && (value.stream === 'stdout' || value.stream === 'stderr') && text(value.text)) {
        onEvent({ kind, sequence: value.sequence, step_id: value.step_id, stream: value.stream, text: value.text })
        return false
      }
      if (kind === 'done' && executionState(value.execution) && ['succeeded', 'failed', 'unknown'].includes(value.execution.status)) {
        onEvent({ kind, sequence: value.sequence, execution: value.execution })
        return true
      }
      throw new HttpError()
    },
  })
}
