<script setup lang="ts">
import { onUnmounted, ref, shallowRef } from 'vue'
import { ElAlert, ElButton, ElCheckbox, ElDialog } from 'element-plus'
import { trustSSHIdentity } from '@/api/ssh_identities'
import { RequestCancelledError } from '@/api/http'
import { showRequestError } from '@/components/feedback'
import { assertSSHRequestCurrent, registerSSHIdentityPrompt } from '@/api/sshIdentity'
import type { SSHIdentityChallenge, SSHIdentityOptions } from '@/types/sshIdentity'

const challenge = shallowRef<SSHIdentityChallenge | null>(null)
const saving = ref(false)
const verified = ref(false)
let pending: { options: SSHIdentityOptions; resolve: () => void; reject: (error: unknown) => void } | null = null
let validityTimer: ReturnType<typeof setInterval> | undefined
let closing = false
let closingError: unknown
const VALIDITY_CHECK_INTERVAL_MS = 200
function finish(error?: unknown) {
  if (!pending || closing) return
  clearInterval(validityTimer)
  // 等待 closed 解除模态滚动锁后再继续，避免后续路由被全局弹窗守卫阻止。
  closing = true
  closingError = error
  challenge.value = null
  verified.value = false
}
function settle(error?: unknown) {
  clearInterval(validityTimer)
  const current = pending
  pending = null
  closing = false
  closingError = undefined
  challenge.value = null
  verified.value = false
  if (error !== undefined) current?.reject(error)
  else current?.resolve()
}
function cancel() { if (!saving.value) finish(new RequestCancelledError()) }
const unregister = registerSSHIdentityPrompt((identity, options) => new Promise<void>((resolve, reject) => {
  challenge.value = identity
  pending = { options, resolve, reject }
  verified.value = false
  validityTimer = setInterval(() => {
    try { assertSSHRequestCurrent(options) } catch (error) { if (!saving.value) finish(error) }
  }, VALIDITY_CHECK_INTERVAL_MS)
}))
async function confirm() {
  if (!pending || !challenge.value || !verified.value || saving.value) return
  const current = pending
  const identity = challenge.value
  saving.value = true
  try {
    assertSSHRequestCurrent(current.options)
    await trustSSHIdentity(identity.id, current.options.signal)
    if (pending !== current) return
    current.options.onTrusted?.()
    assertSSHRequestCurrent(current.options)
    finish()
  } catch (error) {
    if (pending !== current) return
    if (error instanceof RequestCancelledError) finish(error)
    else { verified.value = false; showRequestError(error) }
  } finally { saving.value = false }
}
onUnmounted(() => { unregister(); settle(new RequestCancelledError()) })
</script>

<template>
  <ElDialog :model-value="challenge !== null" title="确认服务器身份" width="min(var(--ui-confirm-width), calc(100vw - 32px))" align-center append-to-body :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving" @update:model-value="!$event && cancel()" @closed="closing && settle(closingError)">
    <div v-if="challenge" class="ssh-identity-content">
      <ElAlert :title="challenge.previous_fingerprint === null ? '此服务器尚未信任，是否信任该身份？' : '服务器指纹已改变，是否信任新身份？'" type="warning" :closable="false" show-icon />
      <dl class="ssh-identity-details">
        <dt>服务器</dt><dd>{{ challenge.target_name }}（{{ challenge.target_type === 'jump_host' ? '跳板机' : '主机' }}）</dd>
        <dt>地址</dt><dd>{{ challenge.address }}:{{ challenge.port }}</dd>
        <template v-if="challenge.previous_fingerprint"><dt>原指纹</dt><dd>{{ challenge.previous_fingerprint }}</dd></template>
        <dt>新指纹</dt><dd>{{ challenge.fingerprint }}</dd>
      </dl>
      <p>信任后继续本次操作，取消则停止。</p>
      <ElCheckbox v-model="verified" :disabled="saving">我已独立核对上述服务器身份和指纹</ElCheckbox>
    </div>
    <template #footer><ElButton :disabled="saving" @click="cancel">取消操作</ElButton><ElButton type="primary" :loading="saving" :disabled="!verified" @click="confirm">信任并继续</ElButton></template>
  </ElDialog>
</template>

<style scoped>
.ssh-identity-content { display: grid; gap: var(--ui-space-4); }
.ssh-identity-content p { margin: 0; }
.ssh-identity-details { display: grid; grid-template-columns: 80px minmax(0, 1fr); gap: var(--ui-space-2); margin: 0; }
.ssh-identity-details dt { color: var(--ui-text-secondary); }
.ssh-identity-details dd { margin: 0; overflow-wrap: anywhere; }
.ssh-identity-content .el-checkbox { height: auto; white-space: normal; }
.ssh-identity-content :deep(.el-checkbox__label) { white-space: normal; }
</style>
