export interface HealthResponse {
  status: 'ok'
}

export interface HostGroup {
  id: number
  name: string
  remark: string
  host_count: number
}

export interface GroupInput {
  name: string
  remark: string
}

export type AuthType = 'password' | 'key'

export interface SSHKey {
  id: number
  name: string
  remark: string
  key_type: string
  fingerprint: string
  public_key: string | null
  created_at: string
  updated_at: string
  version: number
  host_count: number
  jump_host_count: number
}

export interface SSHKeyReferences {
  hosts: { id: number; name: string }[]
  jump_hosts: { id: number; name: string }[]
}

export interface SSHKeyInput {
  name: string
  remark: string
  private_key: string
  public_key: string
}

export interface SSHKeyUpdateInput {
  name: string
  remark: string
  version: number
  private_key?: string
  public_key?: string
}

export interface JumpHost {
  id: number
  name: string
  address: string
  username: string
  port: number
  auth_type: AuthType
  ssh_key_id: number | null
  remark: string
  has_password: boolean
  created_at: string
  updated_at: string
  version: number
  host_count: number
}

export interface JumpHostInput {
  name: string
  address: string
  username: string
  port: number
  auth_type: AuthType
  ssh_key_id: number | null
  remark: string
  password?: string
}

export type JumpHostUpdateInput = JumpHostInput & { version: number }

export interface Host {
  id: number
  name: string
  address: string
  group_id: number
  username: string
  port: number
  auth_type: AuthType
  ssh_key_id: number | null
  vip: string | null
  jump_host_id: number | null
  remark: string
  has_password: boolean
  created_at: string
  updated_at: string
  version: number
}

export type HostInput = Omit<Host, 'id' | 'has_password' | 'created_at' | 'updated_at' | 'version'> & {
  password?: string
}

export type HostUpdateInput = HostInput & { version: number }

export type ConnectionTargetType = 'host' | 'jump_host'
export type HostKeyPolicy = 'strict' | 'accept_new'

export interface ConnectionTestInput {
  target_type: ConnectionTargetType
  target_id: number
  version: number
  host_key_policy?: 'accept_new'
}

export interface ConnectionTestTarget {
  target_type: ConnectionTargetType
  target_id: number
  version: number
  name: string
}

export interface ConnectionTestChallenge {
  target_type: ConnectionTargetType
  target_id: number
  address: string
  port: number
  key_type: string
  fingerprint: string
  previous_fingerprint: string | null
}

export interface ConnectionTest {
  id: string
  target_type: ConnectionTargetType
  target_id: number
  target_name: string
  address: string
  port: number
  username: string
  via_jump_host: string | null
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'awaiting_trust' | 'interrupted' | 'trusted'
  stage: 'target' | 'jump_host' | null
  failure_code: 'authentication' | 'timeout' | 'connection' | 'configuration' | 'internal' | null
  failure_message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  challenge: ConnectionTestChallenge | null
  host_key_policy: HostKeyPolicy
  auto_trusted_keys: ConnectionTestChallenge[]
}
