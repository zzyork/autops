import type { CheckStatus, Conclusion, RunStatus } from '@/types/inspections'

export const isActiveRun = (status: RunStatus) => status === 'queued' || status === 'running'

export function runLabel(status: RunStatus): string {
  return { queued: '排队中', running: '执行中', completed: '已完成', partial: '部分完成', failed: '执行失败', interrupted: '已中断' }[status]
}
export function checkLabel(status: CheckStatus): string {
  return { queued: '未开始', running: '执行中', completed: '已完成', failed: '执行失败', skipped: '已跳过', interrupted: '已中断' }[status]
}
export function conclusionLabel(value: Conclusion): string {
  return { normal: '正常', warning: '警告', critical: '严重', not_applicable: '不适用', unknown: '无法判定' }[value]
}
export function runType(status: RunStatus): 'info' | 'success' | 'warning' | 'danger' {
  if (status === 'completed') return 'success'
  if (status === 'partial') return 'warning'
  if (status === 'failed' || status === 'interrupted') return 'danger'
  return 'info'
}
export function conclusionType(value: Conclusion): 'info' | 'success' | 'warning' | 'danger' {
  if (value === 'normal') return 'success'
  if (value === 'warning') return 'warning'
  if (value === 'critical') return 'danger'
  return 'info'
}
export function timeLabel(value: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '未记录'
}
