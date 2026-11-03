import { ElMessage } from 'element-plus'
import { RequestCancelledError, SSHConnectionFailedError, SYSTEM_ERROR_MESSAGE } from '@/api/http'

const visibleErrors = new Set<string>()

export function showRequestError(error?: unknown): void {
  if (error instanceof RequestCancelledError) return
  const message = error instanceof SSHConnectionFailedError ? error.message : SYSTEM_ERROR_MESSAGE
  if (visibleErrors.has(message)) return
  visibleErrors.add(message)
  ElMessage({
    message,
    type: 'error',
    placement: 'top',
    offset: 16,
    duration: error instanceof SSHConnectionFailedError ? 6000 : 3000,
    onClose: () => { visibleErrors.delete(message) },
  })
}

export const showSystemError = showRequestError

export function showNavigationBlocked(): void {
  ElMessage({ message: '请先完成或关闭当前弹窗。', type: 'warning', placement: 'top', offset: 16, duration: 3000, grouping: true })
}
