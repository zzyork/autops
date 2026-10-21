import { HttpError, request } from './http'
import { assertSSHRequestCurrent, withSSHIdentities } from './sshIdentity'
import type { Host } from '@/types/api'
import type { HostBasicInfo, HostBasicInfoAddress, HostBasicInfoUpdate } from '@/types/hostBasicInfo'
import type { SSHIdentityOptions } from '@/types/sshIdentity'

const COLLECT_TIMEOUT_MS = 75000
const MAX_ADDRESSES = 256

function isAddress(value: unknown): value is HostBasicInfoAddress {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const address = value as Record<string, unknown>
  return typeof address.interface === 'string' && address.interface.trim().length > 0
    && address.interface.length <= 253
    && typeof address.address === 'string' && address.address.length > 0
    && address.address.length <= 253 && address.address === address.address.trim()
    && !address.address.includes('/')
}

function validateCollection(value: unknown, host: Host): HostBasicInfo {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new HttpError()
  const result = value as Record<string, unknown>
  if (result.host_id !== host.id || result.version !== host.version
    || typeof result.name !== 'string' || !result.name.trim() || result.name.length > 100
    || !Array.isArray(result.addresses) || result.addresses.length > MAX_ADDRESSES
    || !result.addresses.every(isAddress)) {
    throw new HttpError()
  }
  return {
    host_id: host.id,
    version: host.version,
    name: result.name,
    addresses: result.addresses,
  }
}

export function collectHostBasicInfo(host: Host, options: SSHIdentityOptions = {}): Promise<HostBasicInfo> {
  return withSSHIdentities(
    [{ target_type: 'host', target_id: host.id, version: host.version }],
    async () => {
      const value = await request<unknown>(`/hosts/${host.id}/basic-info/collect`, {
        method: 'POST',
        body: { version: host.version },
        timeoutMs: COLLECT_TIMEOUT_MS,
        signal: options.signal,
      })
      assertSSHRequestCurrent(options)
      return validateCollection(value, host)
    },
    options,
  )
}

export function saveHostBasicInfo(id: number, body: HostBasicInfoUpdate): Promise<Host> {
  return request<Host>(`/hosts/${id}/basic-info`, { method: 'PATCH', body })
}
