<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCheckbox, ElDialog, ElInput, ElTag } from 'element-plus'
import { showRequestError } from './feedback'
import { ensureSSHIdentities, wasSSHOperationStarted } from '@/api/sshIdentity'
import { hostLabels, operationTime, preflightEvidence, statusType, stepLabels, taskLabels } from './operationDisplay'
import DisclosurePanel from './DisclosurePanel.vue'
import type { OperationTask } from '@/types/operations'

const props = defineProps<{ task: OperationTask; resolvingHostId?: number | null; allowedHostId?: number; showStepEvidence?: boolean }>()
const emit = defineEmits<{ resolve: [id: string, hostId: number, note: string]; dialogOpen: [open: boolean]; busy: [value: boolean] }>()
const resolveHostId = ref<number | null>(null)
const resolutionNote = ref('')
const remoteStopped = ref(false)
const resolving = computed(() => resolveHostId.value !== null && props.resolvingHostId === resolveHostId.value)
const noteValid = computed(() => resolutionNote.value.trim().length >= 5 && resolutionNote.value.trim().length <= 500)
const visibleHosts = computed(() => props.allowedHostId === undefined ? props.task.hosts : props.task.hosts.filter((host) => host.host_id === props.allowedHostId))
let session = 0
let observedRunning = false
const promptedOperationHosts = new Set<string>()
const checkingIdentity = ref<number | null>(null)
const identityRequests = ref(0)
watch(identityRequests, (count) => emit('busy', count > 0), { immediate: true })
async function checkIdentity(hostId: number) {
  if (checkingIdentity.value !== null || props.allowedHostId !== undefined && hostId !== props.allowedHostId) return
  const current = session
  checkingIdentity.value = hostId
  identityRequests.value++
  try { await ensureSSHIdentities([{ target_type: 'host', target_id: hostId }], { isCurrent: () => current === session }) }
  catch (error) { if (current === session) showRequestError(error) }
  finally { identityRequests.value--; if (current === session) checkingIdentity.value = null }
}
onUnmounted(() => { session++; emit('dialogOpen', false); emit('busy', false) })
watch(() => props.task, (task, previous) => {
  if (task.id !== previous?.id) { session++; observedRunning = false; promptedOperationHosts.clear(); checkingIdentity.value = null }
  if (wasSSHOperationStarted(task.id) || task.status === 'queued' || task.status === 'running') observedRunning = true
  if (!observedRunning) return
  for (const host of visibleHosts.value) {
    const key = `${task.id}:${host.host_id}`
    if (!host.identity_required || props.allowedHostId !== undefined && host.host_id !== props.allowedHostId || promptedOperationHosts.has(key)) continue
    promptedOperationHosts.add(key)
    const current = session
    identityRequests.value++
    void ensureSSHIdentities([{ target_type: 'host', target_id: host.host_id }], {
      isCurrent: () => current === session && props.task.id === task.id,
    }).catch((error: unknown) => { if (current === session) showRequestError(error) }).finally(() => { identityRequests.value-- })
  }
}, { immediate: true })
watch(() => props.task.id, () => { resolveHostId.value = null })
watch(() => props.task.hosts.find((host) => host.host_id === resolveHostId.value)?.resolved_at, (resolved) => { if (resolved) resolveHostId.value = null })
watch(resolveHostId, (id) => { emit('dialogOpen', id !== null); if (id === null) { resolutionNote.value = ''; remoteStopped.value = false } }, { immediate: true })
function submitResolution() {
  if (resolveHostId.value === null || props.allowedHostId !== undefined && resolveHostId.value !== props.allowedHostId || resolving.value || !remoteStopped.value || !noteValid.value) return
  emit('resolve', props.task.id, resolveHostId.value, resolutionNote.value.trim())
}
</script>

<template>
  <section class="host-section operation-section" aria-label="任务详情">
    <div class="section-header"><h2>{{ task.title }}</h2><ElTag role="status" :type="statusType(task.status)">{{ taskLabels[task.status] }}</ElTag></div>
    <ElAlert v-if="task.status === 'unknown'" title="任务结果未知；人工解除写操作阻塞不代表本次操作成功，也不会自动重试。" type="warning" :closable="false" show-icon />
    <div v-for="host in visibleHosts" :key="host.host_id" class="operation-host-result">
      <div class="operation-host-head"><strong>{{ host.host_name }} · {{ host.address }}</strong><ElTag :type="statusType(host.status)" size="small">{{ hostLabels[host.status] }}</ElTag></div>
      <ElAlert v-if="host.identity_required" title="该主机需确认 SSH 身份；确认后本次任务不会自动重试。" type="warning" :closable="false" show-icon />
      <ElButton v-if="host.identity_required && (allowedHostId === undefined || allowedHostId === host.host_id)" :loading="checkingIdentity === host.host_id" :disabled="checkingIdentity !== null" @click="checkIdentity(host.host_id)">重新检查服务器身份</ElButton>
      <template v-if="host.status === 'unknown'">
        <ElAlert v-if="!host.resolved_at" title="该主机后续写操作已阻塞；须带外核对远端进程已停止。解除不表示执行成功。" type="warning" :closable="false" show-icon />
        <div v-else class="operation-resolution">{{ operationTime(host.resolved_at) }} 已解除阻塞；结果仍未知。<div class="operation-output"><span>核对说明</span><pre>{{ host.resolution_note }}</pre></div></div>
        <ElButton v-if="!host.resolved_at && task.status !== 'queued' && task.status !== 'running' && (allowedHostId === undefined || allowedHostId === host.host_id)" :disabled="resolvingHostId != null" @click="resolveHostId = host.host_id">带外核对并解除阻塞</ElButton>
      </template>
      <div v-if="host.error" class="operation-output operation-error"><span>失败阶段 / 结果</span><pre>{{ host.error }}</pre></div>
      <DisclosurePanel v-if="showStepEvidence && host.steps.length" label="步骤输出" :context="host.host_name">
        <div v-for="(step, index) in host.steps" :key="index" class="operation-output">
          <div class="operation-step-head"><strong>{{ step.title }}</strong><ElTag :type="statusType(step.status)" size="small">{{ stepLabels[step.status] }}</ElTag><span v-if="step.exit_status !== null">退出码 {{ step.exit_status }}</span></div>
          <div v-if="step.stdout" class="operation-output"><span>标准输出</span><pre>{{ step.stdout }}</pre></div>
          <div v-if="step.stderr" class="operation-output operation-error"><span>错误输出</span><pre>{{ step.stderr }}</pre></div>
        </div>
      </DisclosurePanel>
      <DisclosurePanel v-if="preflightEvidence(host.before) || host.after && !host.steps.some((step) => step.title.includes('核验'))" label="前置状态详情" :context="host.host_name">
        <div v-if="preflightEvidence(host.before)" class="operation-output"><span>前置状态</span><pre>{{ preflightEvidence(host.before) }}</pre></div>
        <div v-if="host.after && !host.steps.some((step) => step.title.includes('核验'))" class="operation-output"><span>执行后核验</span><pre>{{ host.after }}</pre></div>
      </DisclosurePanel>
    </div>
    <ElDialog :model-value="resolveHostId !== null" append-to-body align-center title="人工核对并解除写操作阻塞" width="min(440px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!resolving" :show-close="!resolving" @update:model-value="!$event && !resolving && (resolveHostId = null)">
      <div class="operation-confirm"><p>主机：{{ visibleHosts.find((host) => host.host_id === resolveHostId)?.host_name }}</p><p>仅在带外确认远端进程已停止后解除阻塞。本次结果仍未知，不会自动重试。</p><label class="field" :class="{ 'is-error': resolutionNote.length > 0 && !noteValid }"><span>核对说明 <em>*</em></span><ElInput v-model="resolutionNote" type="textarea" :rows="4" maxlength="500" show-word-limit :disabled="resolving" :aria-invalid="resolutionNote.length > 0 && !noteValid" /></label><span v-if="resolutionNote.length > 0 && !noteValid" class="operation-field-error">核对说明至少填写 5 个字符。</span><ElCheckbox v-model="remoteStopped" :disabled="resolving">我已带外核对该主机远端进程已停止</ElCheckbox></div>
      <template #footer><ElButton :disabled="resolving" @click="resolveHostId = null">取消</ElButton><ElButton type="primary" :loading="resolving" :disabled="!remoteStopped || !noteValid" @click="submitResolution">解除阻塞</ElButton></template>
    </ElDialog>
  </section>
</template>
