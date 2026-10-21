<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElAlert, ElButton, ElDialog } from 'element-plus'
import { startConnectionTest } from '@/api/ssh_connections'
import { ensureSSHIdentities } from '@/api/sshIdentity'
import { showSystemError } from '@/components/feedback'
import { SSH_RESULT_UNAVAILABLE, SSH_RETEST_REQUIRED, sshTestDisplay } from '@/components/sshTestDisplay'
import TestStatus from '@/components/TestStatus.vue'
import type { ConnectionTestResult, ConnectionTestTarget } from '@/types/api'

const props = defineProps<{ target: ConnectionTestTarget | null; modelValue: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'status-changed': []
}>()
const result = ref<ConnectionTestResult | null>(null)
const requestFailed = ref(false)
const submitting = ref(false)
const trusting = ref(false)
const confirmed = ref(false)
const appearance = computed(() => result.value ? sshTestDisplay(result.value.status) : null)
let session = 0

watch(() => [props.modelValue, props.target] as const, () => {
  session++
  result.value = null
  requestFailed.value = false
  submitting.value = false
  trusting.value = false
  confirmed.value = false
}, { flush: 'sync' })

function updateVisible(visible: boolean) {
  if (!visible && (submitting.value || trusting.value)) return
  emit('update:modelValue', visible)
}

async function confirmIdentity(current: number) {
  const target = props.target
  if (!target || !props.modelValue || trusting.value || result.value?.status !== 'awaiting_trust') return
  trusting.value = true
  try {
    await ensureSSHIdentities([{ target_type: target.target_type, target_id: target.target_id, version: target.version }], {
      isCurrent: () => current === session && props.modelValue,
      onTrusted: () => {
        emit('status-changed')
        if (current === session) {
          result.value = null
          confirmed.value = true
        }
      },
    })
    if (current === session) {
      result.value = null
      confirmed.value = true
    }
  } catch (error) {
    if (current === session) {
      showSystemError(error)
      emit('status-changed')
    }
  } finally {
    if (current === session) trusting.value = false
  }
}

async function startTest() {
  const target = props.target
  if (!props.modelValue || !target || submitting.value || trusting.value) return
  const current = session
  submitting.value = true
  result.value = null
  requestFailed.value = false
  confirmed.value = false
  try {
    const value = await startConnectionTest({ target_type: target.target_type, target_id: target.target_id, version: target.version }, {
      isCurrent: () => current === session && props.modelValue,
      onTrusted: () => emit('status-changed'),
    })
    if (current !== session) return
    result.value = value
    if (value.status === 'awaiting_trust') void confirmIdentity(current)
  } catch (error) {
    if (current === session) {
      requestFailed.value = true
      showSystemError(error)
    }
  } finally {
    if (current === session) submitting.value = false
    emit('status-changed')
  }
}
</script>

<template>
  <ElDialog :model-value="modelValue" align-center :title="`SSH 连接测试：${target?.name ?? ''}`" width="min(var(--ui-confirm-width), calc(100vw - 32px))" :close-on-click-modal="false" :close-on-press-escape="!submitting && !trusting" :show-close="!submitting && !trusting" @update:model-value="updateVisible">
    <div class="ssh-test-dialog">
      <ElButton type="primary" :loading="submitting" :disabled="!target || trusting" @click="startTest">开始测试</ElButton>
      <TestStatus v-if="submitting" status="pending" label="测试请求处理中" description="SSH 连接测试请求处理中，结果尚未确认" />
      <TestStatus v-if="requestFailed" :status="SSH_RESULT_UNAVAILABLE.status" :description="SSH_RESULT_UNAVAILABLE.description" :label="SSH_RESULT_UNAVAILABLE.label" />
      <TestStatus v-if="confirmed" :status="SSH_RETEST_REQUIRED.status" :description="SSH_RETEST_REQUIRED.description" :label="SSH_RETEST_REQUIRED.label" />
      <section v-if="result && appearance" aria-label="本次测试结果" class="ssh-test-result">
        <h2>
          本次测试结果
          <TestStatus :status="appearance.status" :description="`${target?.name ?? ''}：${appearance.description}`" :label="appearance.label" />
        </h2>
        <ElAlert v-if="result.status === 'awaiting_trust'" title="待确认主机密钥，请确认后重新测试。" type="warning" :closable="false" show-icon />
        <ElButton v-if="result.status === 'awaiting_trust'" :loading="trusting" :disabled="submitting" @click="confirmIdentity(session)">确认身份</ElButton>
      </section>
    </div>
    <template #footer><ElButton :disabled="submitting || trusting" @click="updateVisible(false)">关闭</ElButton></template>
  </ElDialog>
</template>

<style scoped>
.ssh-test-dialog { display: grid; justify-items: start; gap: var(--ui-space-4); min-height: 80px; }
.ssh-test-result { display: grid; justify-items: start; gap: var(--ui-space-3); width: 100%; border-top: 1px solid var(--ui-border); padding-top: var(--ui-space-4); }
.ssh-test-result h2 { display: flex; align-items: center; flex-wrap: wrap; gap: var(--ui-space-2); margin: 0; font-size: var(--ui-font-size-section); line-height: var(--ui-line-height-section); }
</style>
