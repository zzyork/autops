import type { ConnectionTest } from '@/types/api'
import type { TestStatus } from '@/types/testStatus'

export const SSH_STATUS_UNAVAILABLE = 'SSH 状态待刷新'

const displays: Record<ConnectionTest['status'], { status: TestStatus; label: string; description: string }> = {
  queued: { status: 'pending', label: '排队中', description: 'SSH 连接测试排队中' },
  running: { status: 'pending', label: '测试中', description: 'SSH 连接测试中' },
  succeeded: { status: 'passed', label: '测试通过', description: '最近一次 SSH 连接测试通过' },
  failed: { status: 'failed', label: '测试未通过', description: '最近一次 SSH 连接测试未通过' },
  interrupted: { status: 'failed', label: '测试已中断', description: '最近一次 SSH 连接测试已中断' },
  awaiting_trust: { status: 'warning', label: '待核对主机密钥', description: 'SSH 待核对主机密钥' },
  trusted: { status: 'warning', label: '已信任，需重新测试', description: 'SSH 主机密钥已信任，需重新测试' },
}

export function sshTestDisplay(status: ConnectionTest['status']) {
  return displays[status]
}
