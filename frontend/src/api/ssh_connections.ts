import type { ConnectionTargetType, ConnectionTest, ConnectionTestInput } from '@/types/api'
import { get, request } from './http'
import { withSSHIdentities } from './sshIdentity'
import type { SSHIdentityOptions } from '@/types/sshIdentity'

export const startConnectionTest = (body: ConnectionTestInput, options: SSHIdentityOptions = {}) =>
  withSSHIdentities([{ target_type: body.target_type, target_id: body.target_id, version: body.version }],
    () => request<ConnectionTest>('/ssh/connection-tests', { method: 'POST', body, signal: options.signal }), options)

export const getConnectionTest = (id: string) => get<ConnectionTest>(`/ssh/connection-tests/${id}`)

export function listConnectionTests(targetType: ConnectionTargetType, targetId: number) {
  const params = new URLSearchParams({ target_type: targetType, target_id: String(targetId) })
  return get<ConnectionTest[]>(`/ssh/connection-tests?${params}`)
}
