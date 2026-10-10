import { ElMessage } from 'element-plus'
import { SYSTEM_ERROR_MESSAGE } from '@/api/http'

let systemErrorVisible = false

export function showSystemError(): void {
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
