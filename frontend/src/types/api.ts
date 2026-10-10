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

export interface JumpHost {
  id: number
  name: string
  address: string
  username: string
  port: number
  auth_type: AuthType
  key_path: string | null
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
  key_path: string | null
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
  key_path: string | null
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
