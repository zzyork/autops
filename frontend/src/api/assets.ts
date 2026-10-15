import type { GroupInput, Host, HostGroup, HostInput, HostUpdateInput, PageResponse } from '@/types/api'
import { get, request } from './http'

export const listGroups = () => get<HostGroup[]>('/host-groups')
export const listGroupsPage = (page: number, pageSize: number) =>
  get<PageResponse<HostGroup>>(`/host-groups?page=${page}&page_size=${pageSize}`)
export const createGroup = (body: GroupInput) => request<HostGroup>('/host-groups', { method: 'POST', body })
export const updateGroup = (id: number, body: GroupInput) => request<HostGroup>(`/host-groups/${id}`, { method: 'PUT', body })
export const deleteGroup = (id: number) => request<void>(`/host-groups/${id}`, { method: 'DELETE' })

export function listHosts(q: string, groupId: number | null) {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (groupId !== null) params.set('group_id', String(groupId))
  const query = params.toString()
  return get<Host[]>(`/hosts${query ? `?${query}` : ''}`)
}
export function listHostsPage(q: string, groupId: number | null, page: number, pageSize: number) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (q) params.set('q', q)
  if (groupId !== null) params.set('group_id', String(groupId))
  return get<PageResponse<Host>>(`/hosts?${params}`)
}
export const getHost = (id: number) => get<Host>(`/hosts/${id}`)
export const createHost = (body: HostInput) => request<Host>('/hosts', { method: 'POST', body })
export const updateHost = (id: number, body: HostUpdateInput) => request<Host>(`/hosts/${id}`, { method: 'PUT', body })
export const deleteHost = (id: number) => request<void>(`/hosts/${id}`, { method: 'DELETE' })
