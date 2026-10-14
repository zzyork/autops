import type { ConnectionTargetType } from './api'

export interface SSHIdentityTarget {
  target_type: ConnectionTargetType
  target_id: number
  version?: number
}
export interface SSHIdentityChallenge {
  id: string
  target_type: ConnectionTargetType
  target_name: string
  address: string
  port: number
  fingerprint: string
  previous_fingerprint: string | null
}
export type SSHIdentityCheck = { trusted: true; challenge: null } | { trusted: false; challenge: SSHIdentityChallenge }
export interface SSHIdentityOptions { signal?: AbortSignal; isCurrent?: () => boolean }
