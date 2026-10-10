import type { SSHKey, SSHKeyInput, SSHKeyReferences, SSHKeyUpdateInput } from '@/types/api'
import { get, request } from './http'

export function listSSHKeys(q = '') {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  const query = params.toString()
  return get<SSHKey[]>(`/ssh-keys${query ? `?${query}` : ''}`)
}

export const getSSHKey = (id: number) => get<SSHKey>(`/ssh-keys/${id}`)
export const getSSHKeyReferences = (id: number) => get<SSHKeyReferences>(`/ssh-keys/${id}/references`)
export const createSSHKey = (body: SSHKeyInput) => request<SSHKey>('/ssh-keys', { method: 'POST', body })
export const updateSSHKey = (id: number, body: SSHKeyUpdateInput) => request<SSHKey>(`/ssh-keys/${id}`, { method: 'PUT', body })
export const deleteSSHKey = (id: number) => request<void>(`/ssh-keys/${id}`, { method: 'DELETE' })
