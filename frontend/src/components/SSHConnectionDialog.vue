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
  <ElDialog :model-value="modelValue" align-center :title="`SSH 连接测试：${target?.name ?? ''}`" width="min(720px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!submitting && !trusting" :show-close="!submitting && !trusting" @update:model-value="updateVisible">
    <div class="ssh-test-dialog">
      <ElButton type="primary" :loading="submitting" :disabled="!target || trusting" @click="startTest">开始测试</ElButton>
      <span v-if="requestFailed" class="ssh-test-status"><TestStatus :status="SSH_RESULT_UNAVAILABLE.status" :description="SSH_RESULT_UNAVAILABLE.description" />{{ SSH_RESULT_UNAVAILABLE.label }}</span>
      <span v-if="confirmed" class="ssh-test-status"><TestStatus :status="SSH_RETEST_REQUIRED.status" :description="SSH_RETEST_REQUIRED.description" />{{ SSH_RETEST_REQUIRED.label }}</span>
      <section v-if="result && appearance" aria-label="本次测试结果" class="ssh-test-result">
        <h2>本次测试结果 <span class="ssh-test-status"><TestStatus :status="appearance.status" :description="`${target?.name ?? ''}：${appearance.description}`" />{{ appearance.label }}</span></h2>
        <ElAlert v-if="result.status === 'awaiting_trust'" title="待确认主机密钥，请确认后重新测试。" type="warning" :closable="false" show-icon />
        <ElButton v-if="result.status === 'awaiting_trust'" :loading="trusting" :disabled="submitting" @click="confirmIdentity(session)">确认身份</ElButton>
      </section>
    </div>
    <template #footer><ElButton :disabled="submitting || trusting" @click="updateVisible(false)">关闭</ElButton></template>
  </ElDialog>
</template>

<style scoped>
.ssh-test-dialog { display: grid; justify-items: start; gap: 16px; min-height: 80px; }
.ssh-test-result { display: grid; justify-items: start; gap: 12px; width: 100%; border-top: 1px solid var(--ui-border); padding-top: 16px; }
.ssh-test-result h2 { display: flex; align-items: center; gap: 8px; margin: 0; font-size: 14px; }
.ssh-test-status { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 400; }
</style>
