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
  proxy_address: string | null
  proxy_username: string | null
  proxy_port: number | null
  proxy_auth_type: AuthType | null
  proxy_key_path: string | null
  remark: string
  has_password: boolean
  has_proxy_password: boolean
  created_at: string
  updated_at: string
  version: number
}

export type HostInput = Omit<Host, 'id' | 'has_password' | 'has_proxy_password' | 'created_at' | 'updated_at' | 'version'> & {
  version?: number
  password?: string
  proxy_password?: string | null
}
