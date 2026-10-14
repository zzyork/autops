<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElButton, ElLoading } from 'element-plus'
import { listHosts } from '@/api/assets'
import { confirmOperation, getOperationCatalog, getOperationTask, inspectOperation, prepareOperation, resolveOperationHost } from '@/api/operations'
import { showRequestError } from '@/components/feedback'
import { isRunningOperation } from '@/components/operationDisplay'
import OperationHistory from '@/components/OperationHistory.vue'
import OperationSetup from '@/components/OperationSetup.vue'
import OperationTaskDetail from '@/components/OperationTaskDetail.vue'
import type { Host } from '@/types/api'
import type { OperationCatalog, OperationInspectInput, OperationInspection, OperationModuleId, OperationPlanInput, OperationTask } from '@/types/operations'
import '@/styles/operations.css'

const props = defineProps<{ module: OperationModuleId }>()
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
const historyTask = ref<OperationTask | null>(null)
const historyId = ref<string | null>(null)
const historyLoaded = ref(false)
const historyLoading = ref(false)
const revision = ref(0)
const moduleInfo = computed(() => catalog.value?.modules.find((item) => item.id === props.module))
const preparedAction = computed(() => moduleInfo.value?.actions.find((item) => item.id === prepared.value?.action))
const historyAction = computed(() => catalog.value?.modules.find((item) => item.id === historyTask.value?.module)?.actions.find((item) => item.id === historyTask.value?.action))
const POLL_MS = 2000
let active = true
let optionsRequest = 0
let inspectRequest = 0
let planRequest = 0
let historyRequest = 0
let planTimer: ReturnType<typeof setTimeout> | undefined
let historyTimer: ReturnType<typeof setTimeout> | undefined

async function loadOptions() {
  const current = ++optionsRequest
  loading.value = true
  ready.value = false
  try {
    const [nextCatalog, nextHosts] = await Promise.all([getOperationCatalog(), listHosts('', null)])
    if (!active || current !== optionsRequest) return
    catalog.value = nextCatalog
    hosts.value = nextHosts
    ready.value = true
  } catch {
    if (active && current === optionsRequest) showRequestError()
  } finally {
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
  const current = ++inspectRequest
  lastInspectInput.value = input
  inspecting.value = true
  inspectFailed.value = false
  inspection.value = null
  try {
    const result = await inspectOperation(input)
    if (active && current === inspectRequest) inspection.value = result
  } catch {
    if (active && current === inspectRequest) { inspectFailed.value = true; showRequestError() }
  } finally {
    if (active && current === inspectRequest) inspecting.value = false
  }
}

async function prepare(input: OperationPlanInput) {
  clearTimeout(planTimer)
  const current = ++planRequest
  planning.value = true
  planFailed.value = false
  try {
    const task = await prepareOperation(input)
    if (!active || current !== planRequest) return
    prepared.value = task
    preparedLoaded.value = true
    revision.value++
  } catch {
    if (active && current === planRequest) { planFailed.value = true; showRequestError() }
  } finally {
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
  try {
    const task = await getOperationTask(id)
    if (!active || current !== planRequest || prepared.value?.id !== id) return
    const wasRunning = isRunningOperation(prepared.value.status)
    prepared.value = task
    preparedLoaded.value = true
    if (wasRunning && !isRunningOperation(task.status)) revision.value++
    schedulePlan()
  } catch {
    if (!active || current !== planRequest || prepared.value?.id !== id) return
    preparedLoaded.value = false
    showRequestError()
  }
}

async function confirm(id: string) {
  const selected = preparedLoaded.value && prepared.value?.id === id ? prepared.value
    : historyLoaded.value && historyTask.value?.id === id ? historyTask.value : null
  if (!selected || selected.status !== 'planned' || confirming.value || planning.value) return
  prepared.value = selected
  preparedLoaded.value = true
  const current = ++planRequest
  confirming.value = true
  try {
    const task = await confirmOperation(id)
    if (!active || current !== planRequest) return
    prepared.value = task
    preparedLoaded.value = true
    revision.value++
    if (historyId.value === id) {
      historyTask.value = task
      historyLoaded.value = true
      scheduleHistory()
    }
    schedulePlan()
  } catch {
    if (active && current === planRequest) {
      preparedLoaded.value = false
      if (historyId.value === id) historyLoaded.value = false
      showRequestError()
    }
  } finally {
    if (active && current === planRequest) confirming.value = false
  }
}

function scheduleHistory() {
  clearTimeout(historyTimer)
  if (active && historyTask.value && isRunningOperation(historyTask.value.status)) {
    historyTimer = setTimeout(() => { if (historyId.value) void loadHistory(historyId.value) }, POLL_MS)
  }
}

async function loadHistory(id: string) {
  clearTimeout(historyTimer)
  const current = ++historyRequest
  historyLoading.value = true
  try {
    const task = await getOperationTask(id)
    if (!active || current !== historyRequest || historyId.value !== id) return
    historyTask.value = task
    historyLoaded.value = true
    scheduleHistory()
  } catch {
    if (!active || current !== historyRequest || historyId.value !== id) return
    historyLoaded.value = false
    showRequestError()
  } finally {
    if (active && current === historyRequest) historyLoading.value = false
  }
}

function selectHistory(id: string) {
  historyId.value = id
  historyTask.value = null
  historyLoaded.value = false
  void loadHistory(id)
}
function closeHistory() {
  historyRequest++
  clearTimeout(historyTimer)
  historyId.value = null
  historyTask.value = null
  historyLoaded.value = false
  historyLoading.value = false
}

async function resolve(id: string, hostId: number, note: string) {
  if (resolving.value || ![prepared.value, historyTask.value].some((task) =>
    task?.id === id && task.hosts.some((host) => host.host_id === hostId && host.status === 'unknown' && !host.resolved_at))) return
  resolving.value = { taskId: id, hostId }
  try {
    const task = await resolveOperationHost(id, hostId, note)
    if (!active) return
    if (prepared.value?.id === id) {
      planRequest++
      clearTimeout(planTimer)
      prepared.value = task
      preparedLoaded.value = true
    }
    if (historyId.value === id) {
      historyRequest++
      clearTimeout(historyTimer)
      historyTask.value = task
      historyLoaded.value = true
      historyLoading.value = false
    }
    revision.value++
  } catch {
    if (active) showRequestError()
  } finally {
    resolving.value = null
  }
}

onMounted(() => { void loadOptions() })
onUnmounted(() => {
  active = false
  optionsRequest++
  inspectRequest++
  planRequest++
  historyRequest++
  clearTimeout(planTimer)
  clearTimeout(historyTimer)
})
</script>

<template>
  <main class="assets-main operations-main">
    <div class="assets-heading"><h1>{{ moduleInfo?.title ?? '服务器运维' }}</h1></div>
    <div v-loading="loading" class="operation-options">
      <template v-if="ready && catalog && moduleInfo">
        <OperationSetup :module="module" :actions="moduleInfo.actions" :hosts="hosts" :hosts-ready="ready" :busy="planning || confirming" :inspecting="inspecting" @changed="changed" @inspect="inspect" @prepare="prepare" />
        <section v-if="inspection || inspectFailed" class="host-section operation-section" aria-label="主机现状"><template v-if="inspection"><div class="section-header"><h2>主机现状 · {{ inspection.host_name }}</h2></div><div class="operation-output"><pre>{{ inspection.output }}</pre></div></template><ElButton v-else :loading="inspecting" :disabled="!lastInspectInput" @click="lastInspectInput && inspect(lastInspectInput)">重试读取</ElButton></section>
        <OperationTaskDetail v-if="prepared && preparedLoaded" :task="prepared" :action="preparedAction" :can-confirm="!!preparedAction && prepared.status === 'planned'" :confirming="confirming || planning" :resolving-host-id="resolving?.taskId === prepared.id ? resolving.hostId : null" @confirm="confirm" @resolve="resolve" />
        <section v-else-if="prepared && !preparedLoaded" class="host-section operation-section"><ElButton @click="loadPrepared(prepared.id)">重试加载任务详情</ElButton></section>
        <OperationHistory :module="module" :modules="catalog.modules" :revision="revision" @select="selectHistory" />
        <section v-if="historyId" class="operation-history-detail"><div class="operation-actions"><ElButton @click="closeHistory">关闭历史详情</ElButton><ElButton :loading="historyLoading" @click="loadHistory(historyId)">刷新详情</ElButton></div><OperationTaskDetail v-if="historyLoaded && historyTask" :task="historyTask" :action="historyAction" :can-confirm="!!historyAction && historyTask.status === 'planned'" :confirming="confirming || planning" :resolving-host-id="resolving?.taskId === historyTask.id ? resolving.hostId : null" @confirm="confirm" @resolve="resolve" /><section v-else-if="!historyLoading" class="host-section operation-section"><ElButton @click="loadHistory(historyId)">重试加载历史详情</ElButton></section></section>
      </template>
      <section v-else-if="!loading" class="host-section operation-section">{{ ready ? '当前模块不在操作目录中。' : '' }}<ElButton v-if="!ready" @click="loadOptions">重试加载</ElButton></section>
    </div>
  </main>
</template>
