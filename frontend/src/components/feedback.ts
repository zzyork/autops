import { ElMessage } from 'element-plus'
import { RequestCancelledError, SYSTEM_ERROR_MESSAGE } from '@/api/http'

let systemErrorVisible = false

export function showRequestError(error?: unknown): void {
  if (error instanceof RequestCancelledError) return
  if (systemErrorVisible) return
  systemErrorVisible = true
  ElMessage({
    message: SYSTEM_ERROR_MESSAGE,
    type: 'error',
    placement: 'top',
    offset: 16,
    duration: 3000,
    onClose: () => { systemErrorVisible = false },
  })
}

export const showSystemError = showRequestError

export function showNavigationBlocked(): void {
  ElMessage({ message: '请先完成或关闭当前弹窗。', type: 'warning', placement: 'top', offset: 16, duration: 3000, grouping: true })
}
