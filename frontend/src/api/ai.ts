import type { ChatSession, FeatureModelsConfig, ModelConnection, ModelConnectionInput, SessionActivity, SessionSummary } from '@/types/ai'
import { get, HttpError, request, streamRequest } from './http'
import { assertSSHRequestCurrent, rememberSSHOperation, withSSHIdentities } from './sshIdentity'
import type { SSHIdentityOptions } from '@/types/sshIdentity'
import type { PageResponse } from '@/types/api'

const connectionPath = (id: number) => `/ai/connections/${encodeURIComponent(id)}`
const sessionPath = (id: string) => `/ai/sessions/${encodeURIComponent(id)}`
const isRecord = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)

function featureModelsConfig(value: unknown): FeatureModelsConfig {
  if (!isRecord(value) || !('chat_connection_id' in value) || !('inspection_report_connection_id' in value)
    || ![value.chat_connection_id, value.inspection_report_connection_id].every((id) =>
      id === null || typeof id === 'number' && Number.isSafeInteger(id) && id > 0)) throw new HttpError()
  return value as unknown as FeatureModelsConfig
}

function isChatSession(value: unknown): value is ChatSession {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.title !== 'string'
    || typeof value.connection_id !== 'number' || typeof value.created_at !== 'string'
    || typeof value.updated_at !== 'string' || !Array.isArray(value.messages) || !Array.isArray(value.proposals)) return false
  return value.messages.every((message: unknown) => isRecord(message) && typeof message.id === 'string'
    && (message.role === 'user' || message.role === 'assistant') && typeof message.content === 'string'
    && typeof message.created_at === 'string'
    && (message.status === 'completed' || message.status === 'failed' || message.status === 'interrupted'))
    && value.proposals.every((proposal: unknown) => isRecord(proposal) && typeof proposal.id === 'string'
      && typeof proposal.name === 'string' && Array.isArray(proposal.hosts)
      && proposal.hosts.every((host: unknown) => isRecord(host) && typeof host.id === 'number'
        && typeof host.version === 'number' && typeof host.name === 'string' && typeof host.address === 'string')
      && Array.isArray(proposal.checks) && proposal.checks.every((check: unknown) =>
        check === 'server_info' || check === 'system_resources' || check === 'service_status' || check === 'network_info'
        || check === 'log_error')
      && (proposal.status === 'pending' || proposal.status === 'confirmed' || proposal.status === 'cancelled')
      && (proposal.task_id === null || typeof proposal.task_id === 'string'))
}

function sessionActivity(value: unknown): SessionActivity {
  if (!isRecord(value) || typeof value.running !== 'boolean' || typeof value.stopping !== 'boolean'
    || value.stopping && !value.running) {
    throw new HttpError()
  }
  return { running: value.running, stopping: value.stopping }
}

export const listConnections = () => get<ModelConnection[]>('/ai/connections')
export const listConnectionsPage = (page: number, pageSize: number) => get<PageResponse<ModelConnection>>(`/ai/connections?page=${page}&page_size=${pageSize}`)
export const getFeatureModels = async () => featureModelsConfig(await get<unknown>('/ai/feature-models'))
export const updateFeatureModels = async (body: FeatureModelsConfig) => featureModelsConfig(await request<unknown>('/ai/feature-models', { method: 'PUT', body }))
export const createConnection = (body: ModelConnectionInput) => request<ModelConnection>('/ai/connections', { method: 'POST', body })
export const updateConnection = (id: number, body: ModelConnectionInput) => request<ModelConnection>(connectionPath(id), { method: 'PUT', body })
export const deleteConnection = (id: number) => request<void>(connectionPath(id), { method: 'DELETE' })
export const testConnection = (id: number) => request<ModelConnection>(`${connectionPath(id)}/test`, { method: 'POST', timeoutMs: 150000 })
export const listSessions = () => get<SessionSummary[]>('/ai/sessions')
export const listSessionsPage = (page: number, pageSize: number) => get<PageResponse<SessionSummary>>(`/ai/sessions?page=${page}&page_size=${pageSize}`)
export const createSession = () => request<SessionSummary>('/ai/sessions', { method: 'POST' })
export const getSession = (id: string) => get<ChatSession>(sessionPath(id))
export const getSessionActivity = async (id: string, signal: AbortSignal) => sessionActivity(await request<unknown>(`${sessionPath(id)}/activity`, { signal }))
export const stopSession = async (id: string, signal: AbortSignal) => sessionActivity(await request<unknown>(`${sessionPath(id)}/stop`, { method: 'POST', signal }))
export const deleteSession = (id: string) => request<void>(sessionPath(id), { method: 'DELETE' })
export async function registerOperation(id: string, signal?: AbortSignal): Promise<string> {
  const result = await request<unknown>(`${sessionPath(id)}/operations`, { method: 'POST', signal })
  if (!isRecord(result) || typeof result.operation_id !== 'string'
    || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(result.operation_id)) {
    throw new HttpError()
  }
  return result.operation_id
}
export async function decideProposal(sessionId: string, proposalId: string, approve: boolean, options: SSHIdentityOptions & {
  onRegister?: (pending: Promise<string>) => void
} = {}) {
  const execute = async () => {
    assertSSHRequestCurrent(options)
    const pending = registerOperation(sessionId, options.signal)
    options.onRegister?.(pending)
    const operationId = await pending
    assertSSHRequestCurrent(options)
    return request<ChatSession>(`${sessionPath(sessionId)}/proposals/${encodeURIComponent(proposalId)}/decision`, {
      method: 'POST', body: { approve, operation_id: operationId }, timeoutMs: 120000, signal: options.signal,
    })
  }
  if (!approve) return execute()
  const session = await request<ChatSession>(sessionPath(sessionId), { signal: options.signal })
  const proposal = session.proposals.find((item) => item.id === proposalId)
  if (!proposal) throw new HttpError()
  const result = await withSSHIdentities(proposal.hosts.map((host) => ({ target_type: 'host', target_id: host.id, version: host.version })), execute, options)
  const taskId = result.proposals.find((item) => item.id === proposalId)?.task_id
  if (taskId) rememberSSHOperation(taskId)
  return result
}
export const sendMessage = (id: string, content: string, signal: AbortSignal, onToken: (text: string) => void, operationId?: string) => streamRequest<ChatSession>(`${sessionPath(id)}/messages`, { body: { content, operation_id: operationId }, signal, timeoutMs: 300000, onToken, validateResult: isChatSession })
