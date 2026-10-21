import { computed, inject, onUnmounted, ref, watch } from 'vue'
import { RequestCancelledError } from '@/api/http'
import { ensureSSHIdentities } from '@/api/sshIdentity'
import { startConnectionTest } from '@/api/ssh_connections'
import { showSystemError } from '@/components/feedback'
import { SSH_RESULT_UNAVAILABLE, SSH_RETEST_REQUIRED, sshTestDisplay } from '@/components/sshTestDisplay'
import { workspaceVisibleKey } from '@/components/workspace'
import type { ConnectionTestResult, ConnectionTestTarget, SSHConnectionStatus } from '@/types/api'

interface TestAsset {
  id: number
  version: number
}

export function useSSHConnectionTest(onStatusChanged?: () => void | Promise<void>) {
  const visible = inject(workspaceVisibleKey, ref(true))
  const target = ref<ConnectionTestTarget | null>(null)
  const result = ref<ConnectionTestResult | null>(null)
  const testing = ref(false)
  const requestFailed = ref(false)
  const confirmed = ref(false)
  let generation = 0
  let controller: AbortController | null = null

  const appearance = computed(() => {
    if (testing.value) {
      return { status: 'pending' as const, label: '请求处理中', description: 'SSH 连接测试请求处理中，结果尚未确认' }
    }
    if (requestFailed.value) return SSH_RESULT_UNAVAILABLE
    if (confirmed.value) return SSH_RETEST_REQUIRED
    return result.value ? sshTestDisplay(result.value.status) : null
  })

  function isTestTarget(asset: TestAsset) {
    return target.value?.target_id === asset.id && target.value.version === asset.version
  }

  function connectionTestDisplay(asset: TestAsset, storedStatus?: SSHConnectionStatus) {
    // 主机的已完成结果以刷新后的服务端状态为准，避免覆盖后续批量测试的结果。
    if (isTestTarget(asset) && appearance.value &&
      (testing.value || requestFailed.value || confirmed.value || storedStatus === undefined)) {
      return appearance.value
    }
    if (storedStatus === undefined) {
      return { status: 'untested' as const, label: '暂无结果', description: '暂无本次 SSH 连接测试结果' }
    }
    return sshTestDisplay(storedStatus)
  }

  function clearConnectionTest() {
    if (testing.value) return
    target.value = null
    result.value = null
    requestFailed.value = false
    confirmed.value = false
  }

  function invalidate() {
    generation++
    controller?.abort()
    controller = null
    if (testing.value) {
      testing.value = false
      result.value = null
      requestFailed.value = true
      confirmed.value = false
    }
  }

  async function testConnection(selected: ConnectionTestTarget) {
    if (testing.value || !visible.value) return
    const current = ++generation
    const pending = new AbortController()
    controller = pending
    const isCurrent = () => current === generation && visible.value
    const options = { signal: pending.signal, isCurrent }
    const input = {
      target_type: selected.target_type,
      target_id: selected.target_id,
      version: selected.version,
    }
    target.value = { ...selected }
    result.value = null
    requestFailed.value = false
    confirmed.value = false
    testing.value = true
    try {
      const value = await startConnectionTest(input, options)
      if (!isCurrent()) return
      result.value = value
      if (value.status === 'awaiting_trust') {
        await ensureSSHIdentities([input], options)
        if (!isCurrent()) return
        result.value = null
        confirmed.value = true
      }
    } catch (error) {
      if (!isCurrent()) return
      if (!(error instanceof RequestCancelledError)) requestFailed.value = true
      showSystemError(error)
    } finally {
      if (isCurrent()) {
        testing.value = false
        controller = null
        // 身份确认和测试收尾后再刷新，列表加载不影响当前操作的有效性。
        void onStatusChanged?.()
      }
    }
  }

  watch(visible, (active) => {
    if (!active) {
      // 跳板机无持久化测试状态，离开页面后清除已结束的临时结果。
      if (target.value?.target_type === 'jump_host' && !testing.value) clearConnectionTest()
      invalidate()
    }
  }, { flush: 'sync' })
  onUnmounted(invalidate)

  return { testing, testConnection, isTestTarget, connectionTestDisplay, clearConnectionTest }
}
