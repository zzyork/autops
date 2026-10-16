import type { ConnectionTestInput, ConnectionTestResult } from '@/types/api'
import { request } from './http'
import { withSSHIdentities } from './sshIdentity'
import type { SSHIdentityOptions } from '@/types/sshIdentity'

const CONNECTION_TEST_TIMEOUT_MS = 45000

export const startConnectionTest = (body: ConnectionTestInput, options: SSHIdentityOptions = {}) =>
  withSSHIdentities([{ target_type: body.target_type, target_id: body.target_id, version: body.version }],
    () => request<ConnectionTestResult>('/ssh/connection-tests', { method: 'POST', body, signal: options.signal, timeoutMs: CONNECTION_TEST_TIMEOUT_MS }), options)
