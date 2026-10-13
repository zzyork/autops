import type { ConnectionTargetType, ConnectionTest, ConnectionTestInput } from '@/types/api'
import { get, request } from './http'

export const startConnectionTest = (body: ConnectionTestInput) =>
  request<ConnectionTest>('/ssh/connection-tests', { method: 'POST', body })

export const getConnectionTest = (id: string) => get<ConnectionTest>(`/ssh/connection-tests/${id}`)

export function listConnectionTests(targetType: ConnectionTargetType, targetId: number) {
  const params = new URLSearchParams({ target_type: targetType, target_id: String(targetId) })
  return get<ConnectionTest[]>(`/ssh/connection-tests?${params}`)
}

export const trustConnectionTest = (id: string) =>
  request<void>(`/ssh/connection-tests/${id}/trust`, { method: 'POST' })
