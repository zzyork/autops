import type { SSHConnectionStatus } from '@/types/api'
import type { TestStatus } from '@/types/testStatus'

export const SSH_RESULT_UNAVAILABLE = { status: 'unavailable' as const, label: '状态未知', description: '本次 SSH 连接测试状态未知' }
export const SSH_RETEST_REQUIRED = { status: 'warning' as const, label: '待重新测试', description: 'SSH 连接状态已变更，需重新测试' }

const displays: Record<SSHConnectionStatus, { status: TestStatus; label: string; description: string }> = {
  untested: { status: 'untested', label: '未测试', description: 'SSH 尚未测试' },
  running: { status: 'pending', label: '测试中', description: 'SSH 连接测试中' },
  succeeded: { status: 'passed', label: '测试通过', description: 'SSH 连接测试通过' },
  failed: { status: 'failed', label: '测试未通过', description: 'SSH 连接测试未通过' },
  interrupted: { status: 'failed', label: '测试已中断', description: 'SSH 连接测试已中断' },
  awaiting_trust: { status: 'warning', label: '待核对主机密钥', description: 'SSH 待核对主机密钥' },
}

export function sshTestDisplay(status: SSHConnectionStatus) {
  return displays[status]
}
