import { checkSSHIdentity } from '@/api/ssh_identities'
import { HttpError, RequestCancelledError, SSHIdentityRequiredError } from '@/api/http'
import type { SSHIdentityChallenge, SSHIdentityOptions, SSHIdentityTarget } from '@/types/sshIdentity'

type IdentityPrompt = (challenge: SSHIdentityChallenge, options: SSHIdentityOptions) => Promise<void>
let promptIdentity: IdentityPrompt | null = null
let queue: Promise<void> = Promise.resolve()
const initiatedTasks = new Set<string>()
const MAX_REMEMBERED_TASKS = 128

export function rememberSSHOperation(id: string) {
  initiatedTasks.add(id)
  if (initiatedTasks.size > MAX_REMEMBERED_TASKS) {
    const oldest = initiatedTasks.values().next().value
    if (oldest) initiatedTasks.delete(oldest)
  }
}
export const wasSSHOperationStarted = (id: string) => initiatedTasks.has(id)

export function registerSSHIdentityPrompt(prompt: IdentityPrompt) {
  promptIdentity = prompt
  return () => { if (promptIdentity === prompt) promptIdentity = null }
}
export function assertSSHRequestCurrent(options: SSHIdentityOptions) {
  if (options.signal?.aborted || options.isCurrent && !options.isCurrent()) throw new RequestCancelledError()
}
export function ensureSSHIdentities(targets: SSHIdentityTarget[], options: SSHIdentityOptions = {}): Promise<void> {
  const selected = targets.map((target) => ({ ...target }))
  const execute = async () => {
    const checked = new Set<string>()
    for (const target of selected) {
      const key = `${target.target_type}:${target.target_id}:${target.version ?? ''}`
      if (checked.has(key)) continue
      while (true) {
        assertSSHRequestCurrent(options)
        const result = await checkSSHIdentity(target, options.signal)
        assertSSHRequestCurrent(options)
        if (result.trusted) break
        if (!promptIdentity) throw new HttpError()
        await promptIdentity(result.challenge, options)
      }
      checked.add(key)
    }
  }
  // 多入口共用一个确认弹窗；每个调用保留自己的取消和失效边界。
  const pending = queue.then(execute, execute)
  queue = pending.then(() => undefined, () => undefined)
  return pending
}
export async function withSSHIdentities<T>(targets: SSHIdentityTarget[], execute: () => Promise<T>, options: SSHIdentityOptions = {}): Promise<T> {
  await ensureSSHIdentities(targets, options)
  assertSSHRequestCurrent(options)
  try { return await execute() } catch (error) {
    if (!(error instanceof SSHIdentityRequiredError)) throw error
    await ensureSSHIdentities([error.target], options)
    assertSSHRequestCurrent(options)
    return execute()
  }
}
