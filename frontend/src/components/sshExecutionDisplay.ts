import type { ExecutionStatus, StepStatus } from '@/types/sshExecutions'

export function executionLabel(status: ExecutionStatus | StepStatus): string {
  return { queued: '等待中', running: '执行中', succeeded: '成功', failed: '失败', unknown: '结果未知', skipped: '已跳过' }[status]
}
export function executionTag(status: ExecutionStatus | StepStatus): 'info' | 'warning' | 'success' | 'danger' {
  return status === 'succeeded' ? 'success' : status === 'failed' ? 'danger' : status === 'unknown' ? 'warning' : 'info'
}
const failureLabels: Record<string, string> = {
  exit_status: '命令退出码未满足步骤要求',
  timeout: '达到执行时限',
  connection: 'SSH 连接中断或未能建立',
  authentication: 'SSH 认证未通过',
  configuration: '连接配置无效',
  output_limit: '命令输出达到上限',
  host_key_required: '服务器身份需要重新确认',
  asset_changed: '主机、凭据或服务器信任已变更',
  interrupted: '服务关闭导致执行中断',
  dispatch_failed: '执行任务未能启动',
  internal: '命令结果采集异常',
  unknown: '未取得有效的命令退出结果',
}
export function executionFailure(code: string | null): string | undefined {
  return code === null ? undefined : failureLabels[code]
}
export function executionTime(value: string | null): string { return value ? new Date(value).toLocaleString('zh-CN') : '—' }
