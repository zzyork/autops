<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElLoading } from 'element-plus'
import { listHosts } from '@/api/assets'
import { RequestCancelledError } from '@/api/http'
import { confirmOperation, getOperationCatalog, getOperationTask, inspectOperation, prepareOperation, resolveOperationHost } from '@/api/operations'
import { showRequestError } from '@/components/feedback'
import { isRunningOperation } from '@/components/operationDisplay'
import OperationSetup from '@/components/OperationSetup.vue'
import OperationTaskDetail from '@/components/OperationTaskDetail.vue'
import type { Host } from '@/types/api'
import type { OperationCatalog, OperationInspectInput, OperationInspection, OperationModuleId, OperationPlanInput, OperationTask } from '@/types/operations'
import '@/styles/operations.css'

const props = defineProps<{ module: OperationModuleId; fixedHost?: Host; initialAction?: string; allowedActions?: string[]; embedded?: boolean }>()
const emit = defineEmits<{ busy: [value: boolean] }>()
const vLoading = ElLoading.directive
const catalog = ref<OperationCatalog | null>(null)
const hosts = ref<Host[]>([])
const ready = ref(false)
const loading = ref(false)
const inspection = ref<OperationInspection | null>(null)
const lastInspectInput = ref<OperationInspectInput | null>(null)
const inspecting = ref(false)
const inspectFailed = ref(false)
const prepared = ref<OperationTask | null>(null)
const preparedLoaded = ref(false)
const planning = ref(false)
const planFailed = ref(false)
const confirming = ref(false)
const resolving = ref<{ taskId: string; hostId: number } | null>(null)
const pendingRequests = ref(0)
const preparedDialogOpen = ref(false)
const preparedDetailBusy = ref(false)
const busy = computed(() => pendingRequests.value > 0 || loading.value || inspecting.value || planning.value || confirming.value || resolving.value !== null || preparedDialogOpen.value || preparedDetailBusy.value)
watch(busy, (value) => emit('busy', value), { immediate: true, flush: 'sync' })
const moduleInfo = computed(() => {
  const source = catalog.value?.modules.find((item) => item.id === props.module)
  if (!source || !props.allowedActions) return source
  return { ...source, actions: source.actions.filter((item) => props.allowedActions?.includes(item.id)) }
})
const preparedAction = computed(() => moduleInfo.value?.actions.find((item) => item.id === prepared.value?.action))
const POLL_MS = 2000
let active = true
let optionsRequest = 0
let inspectRequest = 0
let planRequest = 0
let planTimer: ReturnType<typeof setTimeout> | undefined

async function loadOptions() {
  const current = ++optionsRequest
  loading.value = true
  ready.value = false
  pendingRequests.value++
  try {
    const [nextCatalog, nextHosts] = await Promise.all([getOperationCatalog(), props.fixedHost ? Promise.resolve([props.fixedHost]) : listHosts('', null)])
    if (!active || current !== optionsRequest) return
    catalog.value = nextCatalog
    hosts.value = nextHosts
    ready.value = true
  } catch {
    if (active && current === optionsRequest) showRequestError()
  } finally {
    pendingRequests.value--
    if (active && current === optionsRequest) loading.value = false
  }
}

function changed() {
  inspectRequest++
  inspection.value = null
  lastInspectInput.value = null
  inspecting.value = false
  inspectFailed.value = false
  if (prepared.value?.status === 'planned') {
    planRequest++
    prepared.value = null
    preparedLoaded.value = false
  }
  planFailed.value = false
}

async function inspect(input: OperationInspectInput) {
  if (props.fixedHost && (input.host_id !== props.fixedHost.id || input.module !== props.module)) return
  const current = ++inspectRequest
  lastInspectInput.value = input
  inspecting.value = true
  inspectFailed.value = false
  inspection.value = null
  pendingRequests.value++
  try {
    const result = await inspectOperation(input, { isCurrent: () => active && current === inspectRequest })
    if (active && current === inspectRequest) inspection.value = result
  } catch (error) {
    if (active && current === inspectRequest) { inspectFailed.value = !(error instanceof RequestCancelledError); showRequestError(error) }
  } finally {
    pendingRequests.value--
    if (active && current === inspectRequest) inspecting.value = false
  }
}

async function prepare(input: OperationPlanInput) {
  if (!moduleInfo.value?.actions.some((item) => item.id === input.action)) return
  if (props.fixedHost && (input.module !== props.module || props.initialAction !== undefined && input.action !== props.initialAction || input.host_ids.length !== 1 || input.host_ids[0] !== props.fixedHost.id)) return
  clearTimeout(planTimer)
  const current = ++planRequest
  planning.value = true
  planFailed.value = false
  pendingRequests.value++
  try {
    const task = await prepareOperation(input, { isCurrent: () => active && current === planRequest })
    if (!active || current !== planRequest) return
    prepared.value = task
    preparedLoaded.value = true
  } catch (error) {
    if (active && current === planRequest) { planFailed.value = !(error instanceof RequestCancelledError); showRequestError(error) }
  } finally {
    pendingRequests.value--
    if (active && current === planRequest) {
      planning.value = false
      schedulePlan()
    }
  }
}

function schedulePlan() {
  clearTimeout(planTimer)
  if (active && prepared.value && isRunningOperation(prepared.value.status)) {
    planTimer = setTimeout(() => { if (prepared.value) void loadPrepared(prepared.value.id) }, POLL_MS)
  }
}

async function loadPrepared(id: string) {
  clearTimeout(planTimer)
  const current = ++planRequest
  pendingRequests.value++
  try {
    const task = await getOperationTask(id)
    if (!active || current !== planRequest || prepared.value?.id !== id) return
    prepared.value = task
    preparedLoaded.value = true
    schedulePlan()
  } catch {
    if (!active || current !== planRequest || prepared.value?.id !== id) return
    preparedLoaded.value = false
    showRequestError()
  } finally {
    pendingRequests.value--
  }
}

function canConfirmTarget(task: OperationTask) {
  return !props.fixedHost || task.module === props.module && (props.initialAction === undefined || task.action === props.initialAction) && task.hosts.length === 1 && task.hosts[0]?.host_id === props.fixedHost.id
}

async function confirm(id: string) {
  const selected = preparedLoaded.value && prepared.value?.id === id ? prepared.value : null
  if (!selected || selected.status !== 'planned' || !canConfirmTarget(selected) || confirming.value || planning.value) return
  prepared.value = selected
  preparedLoaded.value = true
  const current = ++planRequest
  confirming.value = true
  pendingRequests.value++
  try {
    const task = await confirmOperation(id, { isCurrent: () => active && current === planRequest })
    if (!active || current !== planRequest) return
    prepared.value = task
    preparedLoaded.value = true
    schedulePlan()
  } catch (error) {
    if (active && current === planRequest) {
      preparedLoaded.value = false
      showRequestError(error)
    }
  } finally {
    pendingRequests.value--
    if (active && current === planRequest) confirming.value = false
  }
}

async function resolve(id: string, hostId: number, note: string) {
  if (resolving.value || !prepared.value || props.fixedHost && (hostId !== props.fixedHost.id || prepared.value.module !== props.module) ||
    prepared.value.id !== id || !prepared.value.hosts.some((host) =>
      host.host_id === hostId && host.status === 'unknown' && !host.resolved_at)) return
  resolving.value = { taskId: id, hostId }
  pendingRequests.value++
  try {
    const task = await resolveOperationHost(id, hostId, note)
    if (!active) return
    if (prepared.value?.id === id) {
      planRequest++
      clearTimeout(planTimer)
      prepared.value = task
      preparedLoaded.value = true
    }
  } catch {
    if (active) showRequestError()
  } finally {
    pendingRequests.value--
    resolving.value = null
  }
}

onMounted(() => { void loadOptions() })
onUnmounted(() => {
  active = false
  optionsRequest++
  inspectRequest++
  planRequest++
  clearTimeout(planTimer)
})
</script>

<template>
  <component :is="embedded ? 'section' : 'main'" class="assets-main operations-main" :class="{ 'operations-embedded': embedded }">
    <div v-if="!embedded" class="assets-heading"><h1>{{ moduleInfo?.title ?? '服务器运维' }}</h1></div>
    <div v-loading="loading" class="operation-options">
      <template v-if="ready && catalog && moduleInfo">
        <OperationSetup :module="module" :actions="moduleInfo.actions" :hosts="hosts" :fixed-host="fixedHost" :initial-action="initialAction" :hosts-ready="ready" :busy="planning || confirming" :inspecting="inspecting" @changed="changed" @inspect="inspect" @prepare="prepare" />
        <section v-if="inspection || inspectFailed" class="host-section operation-section" aria-label="主机现状"><template v-if="inspection"><div class="section-header"><h2>主机现状 · {{ inspection.host_name }}</h2></div><div class="operation-output"><pre>{{ inspection.output }}</pre></div></template><ElButton v-else :loading="inspecting" :disabled="!lastInspectInput" @click="lastInspectInput && inspect(lastInspectInput)">重试读取</ElButton></section>
        <OperationTaskDetail v-if="prepared && preparedLoaded" :task="prepared" :action="preparedAction" :allowed-host-id="fixedHost?.id" :can-confirm="!!preparedAction && prepared.status === 'planned' && canConfirmTarget(prepared)" :confirming="confirming || planning" :resolving-host-id="resolving?.taskId === prepared.id ? resolving.hostId : null" @dialog-open="preparedDialogOpen = $event" @busy="preparedDetailBusy = $event" @confirm="confirm" @resolve="resolve" />
        <section v-else-if="prepared && !preparedLoaded" class="host-section operation-section"><ElButton @click="loadPrepared(prepared.id)">重试加载任务详情</ElButton></section>
      </template>
      <section v-else-if="!loading" class="host-section operation-section">{{ ready ? '当前模块不在操作目录中。' : '' }}<ElButton v-if="!ready" @click="loadOptions">重试加载</ElButton></section>
    </div>
  </component>
</template>
