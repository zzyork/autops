export interface HealthResponse {
  status: 'ok'
}

export interface PageResponse<T> {
  items: T[]
  total: number
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

export type SSHKeySummary = Omit<SSHKey, 'public_key'>

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
  lan_ip: string | null
  group_id: number
  username: string
  port: number
  auth_type: AuthType
  ssh_key_id: number | null
  vip: string | null
  jump_host_id: number | null
  remark: string
  has_password: boolean
  connection_status: SSHConnectionStatus
  created_at: string
  updated_at: string
  version: number
}

export type HostInput = Omit<Host, 'id' | 'name' | 'lan_ip' | 'has_password' | 'connection_status' | 'created_at' | 'updated_at' | 'version'> & {
  name?: string
  lan_ip?: string | null
  password?: string
}

export type HostUpdateInput = HostInput & { version: number }

export type ConnectionTargetType = 'host' | 'jump_host'
export type SSHConnectionStatus = 'untested' | 'running' | 'succeeded' | 'failed' | 'awaiting_trust' | 'interrupted'

export interface ConnectionTestInput {
  target_type: ConnectionTargetType
  target_id: number
  version: number
}

export interface ConnectionTestTarget {
  target_type: ConnectionTargetType
  target_id: number
  version: number
  name: string
}

export interface ConnectionTestResult {
  target_type: ConnectionTargetType
  target_id: number
  status: SSHConnectionStatus
}
