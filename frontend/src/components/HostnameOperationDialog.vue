<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCheckbox, ElDialog, ElForm, ElFormItem, ElInput, ElMessage } from 'element-plus'
import { confirmOperation, getOperationTask, inspectOperation, prepareOperation, resolveOperationHost } from '@/api/operations'
import { ensureSSHIdentities } from '@/api/sshIdentity'
import { showRequestError } from '@/components/feedback'
import { isRunningOperation } from '@/components/operationDisplay'
import type { Host } from '@/types/api'
import type { OperationTask } from '@/types/operations'
import '@/styles/operations.css'

const props = defineProps<{ modelValue: boolean; host: Host | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const currentHostname = ref('')
const newHostname = ref('')
const loaded = ref(false)
const loading = ref(false)
const saving = ref(false)
const resultFailed = ref(false)
const validationError = ref('')
const task = ref<OperationTask | null>(null)
const remoteStopped = ref(false)
const resolutionNote = ref('')
const POLL_MS = 1000
const HOSTNAME_PATTERN = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$/
const running = computed(() => !!task.value && isRunningOperation(task.value.status))
const busy = computed(() => loading.value || saving.value || running.value && !resultFailed.value)
const unknownHost = computed(() => task.value?.hosts.find((host) => host.status === 'unknown' && !host.resolved_at))
const ended = computed(() => !!task.value && task.value.status !== 'planned' && !running.value)
const pendingTasks = new Map<number, OperationTask>()
let selectedHostId: number | null = null
let session = 0
let timer: ReturnType<typeof setTimeout> | undefined

function isCurrent(current: number) { return current === session && props.modelValue }
function updateVisible(visible: boolean) {
  if (!visible && busy.value) return
  emit('update:modelValue', visible)
}

async function loadHostname() {
  const host = props.host
  if (!host || loading.value) return
  const current = session
  loading.value = true
  loaded.value = false
  try {
    const result = await inspectOperation({ module: 'hostname', host_id: host.id, sudo: false }, { isCurrent: () => isCurrent(current) })
    if (!isCurrent(current)) return
    currentHostname.value = result.output.trim()
    loaded.value = true
  } catch (error) {
    if (isCurrent(current)) showRequestError(error)
  } finally {
    if (isCurrent(current)) loading.value = false
  }
}

async function acceptResult(result: OperationTask, current: number) {
  if (!isCurrent(current)) return
  task.value = result
  resultFailed.value = false
  if (selectedHostId !== null) {
    if (isRunningOperation(result.status) || result.hosts.some((host) => host.status === 'unknown' && !host.resolved_at)) pendingTasks.set(selectedHostId, result)
    else pendingTasks.delete(selectedHostId)
  }
  if (result.status === 'succeeded') {
    ElMessage.success('主机名已更改')
    emit('update:modelValue', false)
  } else if (isRunningOperation(result.status)) {
    timer = setTimeout(() => { void readResult(current) }, POLL_MS)
  } else if (result.hosts.some((host) => host.identity_required)) {
    try {
      await ensureSSHIdentities(result.hosts.filter((host) => host.identity_required).map((host) => ({ target_type: 'host' as const, target_id: host.host_id })), { isCurrent: () => isCurrent(current) })
    } catch (error) {
      if (isCurrent(current)) showRequestError(error)
    }
  }
}

async function readResult(current: number) {
  const id = task.value?.id
  if (!id || !isCurrent(current)) return
  clearTimeout(timer)
  saving.value = true
  try {
    await acceptResult(await getOperationTask(id), current)
  } catch (error) {
    if (isCurrent(current)) { resultFailed.value = true; showRequestError(error) }
  } finally {
    if (isCurrent(current)) saving.value = false
  }
}

async function save() {
  const host = props.host
  if (!host || !loaded.value || busy.value || ended.value) return
  const hostname = newHostname.value.trim()
  validationError.value = !hostname ? '请输入新主机名' : hostname.length > 253 || !HOSTNAME_PATTERN.test(hostname)
    ? '主机名须由字母、数字、短横线和点组成，每段最多 63 个字符，且以字母或数字开头和结尾' : hostname === currentHostname.value ? '新主机名与当前主机名相同' : ''
  if (validationError.value) return
  const current = session
  saving.value = true
  try {
    if (!task.value) {
      const plan = await prepareOperation({ module: 'hostname', action: 'set', host_ids: [host.id], params: { hostname }, sudo: host.username !== 'root' }, { isCurrent: () => isCurrent(current) })
      if (!isCurrent(current)) return
      task.value = plan
    } else {
      // Confirmation may have reached the server before its response failed.
      const result = await getOperationTask(task.value.id)
      if (!isCurrent(current)) return
      task.value = result
    }
    const result = task.value.status === 'planned'
      ? await confirmOperation(task.value.id, { isCurrent: () => isCurrent(current) }) : task.value
    await acceptResult(result, current)
  } catch (error) {
    if (isCurrent(current)) { resultFailed.value = task.value !== null; showRequestError(error) }
  } finally {
    if (isCurrent(current)) saving.value = false
  }
}

async function resolveUnknown() {
  const selected = task.value
  const host = unknownHost.value
  const note = resolutionNote.value.trim()
  if (!selected || !host || busy.value || !remoteStopped.value || note.length < 5 || note.length > 500) return
  const current = session
  saving.value = true
  try {
    const result = await resolveOperationHost(selected.id, host.host_id, note)
    await acceptResult(result, current)
  } catch (error) {
    if (isCurrent(current)) { resultFailed.value = true; showRequestError(error) }
  } finally {
    if (isCurrent(current)) saving.value = false
  }
}

function reset() {
  if (selectedHostId !== null && task.value && (resultFailed.value || running.value || unknownHost.value)) pendingTasks.set(selectedHostId, task.value)
  session++
  clearTimeout(timer)
  currentHostname.value = ''
  newHostname.value = ''
  loaded.value = false
  loading.value = false
  saving.value = false
  resultFailed.value = false
  validationError.value = ''
  task.value = null
  remoteStopped.value = false
  resolutionNote.value = ''
}
watch(() => [props.modelValue, props.host?.id] as const, ([visible, hostId]) => {
  reset()
  selectedHostId = hostId ?? null
  if (visible && hostId) {
    const pending = pendingTasks.get(hostId)
    if (pending) {
      task.value = pending
      newHostname.value = typeof pending.params.hostname === 'string' ? pending.params.hostname : ''
      void readResult(session)
    }
    void loadHostname()
  }
}, { immediate: true })
onUnmounted(reset)
</script>

<template>
  <ElDialog :model-value="modelValue" append-to-body align-center :title="host ? `更改主机名 · ${host.address}` : '更改主机名'" width="min(440px, 94vw)" class="hostname-operation-dialog" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @update:model-value="updateVisible">
    <ElForm label-position="top" @submit.prevent="save">
      <ElFormItem label="当前主机名">
        <span v-if="loaded" class="hostname-current">{{ currentHostname }}</span>
        <span v-else-if="loading">读取中…</span>
        <ElButton v-else @click="loadHostname">重新读取</ElButton>
      </ElFormItem>
      <ElFormItem label="新主机名" label-for="new-hostname" required :error="validationError">
        <ElInput id="new-hostname" v-model="newHostname" :disabled="!loaded || busy || task !== null" :maxlength="253" :aria-invalid="!!validationError" @input="validationError = ''" @keydown.enter.prevent="save" />
      </ElFormItem>
      <ElAlert v-if="resultFailed" title="执行结果尚未确认，请查询结果后再操作。" type="warning" :closable="false" show-icon />
      <ElAlert v-else-if="ended" :title="unknownHost ? '更改结果未知，后续写操作已阻塞。请带外核对远端进程已停止后解除阻塞。' : task?.status === 'unknown' ? '写操作阻塞已解除，更改结果仍未知，请重新打开弹窗核对当前主机名。' : '更改未完成，请重新打开弹窗核对当前主机名。'" type="warning" :closable="false" show-icon />
      <template v-if="unknownHost">
        <ElFormItem label="核对说明" label-for="hostname-resolution">
          <ElInput id="hostname-resolution" v-model="resolutionNote" type="textarea" :rows="3" maxlength="500" :disabled="busy" />
        </ElFormItem>
        <ElCheckbox v-model="remoteStopped" :disabled="busy">我已带外核对远端进程已停止</ElCheckbox>
      </template>
    </ElForm>
    <template #footer>
      <ElButton :disabled="busy" @click="updateVisible(false)">取消</ElButton>
      <ElButton v-if="resultFailed && task" type="primary" :loading="saving" @click="readResult(session)">查询结果</ElButton>
      <ElButton v-else-if="unknownHost" type="primary" :loading="saving" :disabled="!remoteStopped || resolutionNote.trim().length < 5" @click="resolveUnknown">解除阻塞</ElButton>
      <ElButton v-else type="primary" :loading="saving || running" :disabled="!loaded || loading || ended" @click="save">保存</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.hostname-current { overflow-wrap: anywhere; }
</style>
