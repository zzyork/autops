import type { SSHIdentityCheck, SSHIdentityTarget } from '@/types/sshIdentity'
import { HttpError, request } from './http'

const isRecord = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const IDENTITY_TIMEOUT_MS = 45000

export async function checkSSHIdentity(target: SSHIdentityTarget, signal?: AbortSignal): Promise<SSHIdentityCheck> {
  const result = await request<unknown>('/ssh/identities/check', { method: 'POST', body: target, timeoutMs: IDENTITY_TIMEOUT_MS, signal })
  if (!isRecord(result)) throw new HttpError()
  if (result.trusted === true && result.challenge === null) return { trusted: true, challenge: null }
  const item = result.challenge
  if (result.trusted !== false || !isRecord(item)
    || item.target_type !== 'host' && item.target_type !== 'jump_host'
    || typeof item.port !== 'number' || !Number.isInteger(item.port) || item.port < 1 || item.port > 65535
    || !['id', 'target_name', 'address', 'fingerprint'].every((key) => typeof item[key] === 'string' && item[key] !== '')
    || !(item.previous_fingerprint === null || typeof item.previous_fingerprint === 'string')) throw new HttpError()
  return result as unknown as SSHIdentityCheck
}
export async function trustSSHIdentity(id: string, signal?: AbortSignal): Promise<void> {
  const result = await request<unknown>(`/ssh/identities/${encodeURIComponent(id)}/trust`, {
    method: 'POST', body: { confirmed: true }, timeoutMs: IDENTITY_TIMEOUT_MS, signal,
  })
  if (!isRecord(result) || result.trusted !== true) throw new HttpError()
}
