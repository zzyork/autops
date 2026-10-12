import type { ChatSession, ModelConnection, ModelConnectionInput, SessionSummary } from '@/types/ai'
import { get, request, streamRequest } from './http'

const connectionPath = (id: number) => `/ai/connections/${encodeURIComponent(id)}`
const sessionPath = (id: string) => `/ai/sessions/${encodeURIComponent(id)}`
const isRecord = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)

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
        check === 'server_info' || check === 'system_resources' || check === 'service_status' || check === 'network_info')
      && (proposal.status === 'pending' || proposal.status === 'confirmed' || proposal.status === 'cancelled')
      && (proposal.task_id === null || typeof proposal.task_id === 'string'))
}

export const listConnections = () => get<ModelConnection[]>('/ai/connections')
export const createConnection = (body: ModelConnectionInput) => request<ModelConnection>('/ai/connections', { method: 'POST', body })
export const updateConnection = (id: number, body: ModelConnectionInput) => request<ModelConnection>(connectionPath(id), { method: 'PUT', body })
export const deleteConnection = (id: number) => request<void>(connectionPath(id), { method: 'DELETE' })
export const testConnection = (id: number) => request<ModelConnection>(`${connectionPath(id)}/test`, { method: 'POST', timeoutMs: 150000 })
export const listSessions = () => get<SessionSummary[]>('/ai/sessions')
export const createSession = (connectionId: number) => request<SessionSummary>('/ai/sessions', { method: 'POST', body: { connection_id: connectionId } })
export const getSession = (id: string) => get<ChatSession>(sessionPath(id))
export const deleteSession = (id: string) => request<void>(sessionPath(id), { method: 'DELETE' })
export const decideProposal = (sessionId: string, proposalId: string, approve: boolean) => request<ChatSession>(`${sessionPath(sessionId)}/proposals/${encodeURIComponent(proposalId)}/decision`, { method: 'POST', body: { approve }, timeoutMs: 120000 })
export const sendMessage = (id: string, content: string, signal: AbortSignal, onToken: (text: string) => void) => streamRequest<ChatSession>(`${sessionPath(id)}/messages`, { body: { content }, signal, timeoutMs: 300000, onToken, validateResult: isChatSession })
