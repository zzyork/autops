import type { JumpHost, JumpHostInput, JumpHostUpdateInput, PageResponse } from '@/types/api'
import { get, request } from './http'

export function listJumpHosts(q = '') {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  const query = params.toString()
  return get<JumpHost[]>(`/jump-hosts${query ? `?${query}` : ''}`)
}

export function listJumpHostsPage(q: string, page: number, pageSize: number) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (q) params.set('q', q)
  return get<PageResponse<JumpHost>>(`/jump-hosts?${params}`)
}

export const getJumpHost = (id: number) => get<JumpHost>(`/jump-hosts/${id}`)
export const createJumpHost = (body: JumpHostInput) => request<JumpHost>('/jump-hosts', { method: 'POST', body })
export const updateJumpHost = (id: number, body: JumpHostUpdateInput) => request<JumpHost>(`/jump-hosts/${id}`, { method: 'PUT', body })
export const deleteJumpHost = (id: number) => request<void>(`/jump-hosts/${id}`, { method: 'DELETE' })
