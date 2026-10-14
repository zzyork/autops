import type { OperationHostStatus, OperationStepStatus, OperationTaskStatus } from '@/types/operations'

export const taskLabels: Record<OperationTaskStatus, string> = {
  planned: '待确认', queued: '排队中', running: '执行中', succeeded: '成功', failed: '失败',
  partial: '部分成功', unknown: '结果未知', interrupted: '已中断', expired: '已过期',
}
export const hostLabels: Record<OperationHostStatus, string> = {
  planned: '待确认', queued: '排队中', running: '执行中', succeeded: '成功',
  failed: '失败', unknown: '结果未知', interrupted: '已中断',
}
export const stepLabels: Record<OperationStepStatus, string> = {
  pending: '待执行', running: '执行中', succeeded: '成功', failed: '失败', unknown: '结果未知',
}
export function statusType(status: OperationTaskStatus | OperationHostStatus | OperationStepStatus) {
  if (status === 'succeeded') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'partial' || status === 'unknown' || status === 'interrupted' || status === 'expired') return 'warning'
  return 'info'
}
export const isRunningOperation = (status: OperationTaskStatus) => status === 'queued' || status === 'running'
export function operationTime(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '—'
}
