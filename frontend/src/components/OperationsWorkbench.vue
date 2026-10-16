<script setup lang="ts">
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElLoading } from 'element-plus'
import { listHosts } from '@/api/assets'
import { HttpError, RequestCancelledError } from '@/api/http'
import { confirmOperation, getOperationCatalog, getOperationTask, inspectOperation, prepareOperation, recoverOperation, resolveOperationHost } from '@/api/operations'
import { showRequestError } from './feedback'
import { isRunningOperation, taskLabels, validateOperationActions } from './operationDisplay'
import OperationSetup from './OperationSetup.vue'
import OperationTaskDetail from './OperationTaskDetail.vue'
import OperationConfirmationDialog from './OperationConfirmationDialog.vue'
import OperationLiveOutput from './OperationLiveOutput.vue'
import OperationBlockers from './OperationBlockers.vue'
import { useOperationOutput } from './useOperationOutput'
import { workspaceVisibleKey } from './workspace'
import type { Host } from '@/types/api'
import type { OperationCatalog, OperationInspectInput, OperationInspection, OperationModuleId, OperationPlanInput, OperationTask } from '@/types/operations'
import '@/styles/operations.css'

const props = defineProps<{ module: OperationModuleId; fixedHost?: Host; initialAction?: string; allowedActions?: string[]; embedded?: boolean; section?: string; visible?: boolean }>()
const emit = defineEmits<{ busy: [value: boolean] }>()
const route = useRoute()
const router = useRouter()
const workspaceVisible = inject(workspaceVisibleKey, ref(true))
const activeView = computed(() => workspaceVisible.value && props.visible !== false)
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
const confirming = ref(false)
const confirmationOpen = ref(false)
const pendingCancelledId = ref<string | null>(null)
const confirmingUncertain = ref(false)
const detailFailed = ref(false)
const resolving = ref<{ taskId: string; hostId: number } | null>(null)
const detailBusy = ref(false)
const detailDialog = ref(false)
const pendingRequests = ref(0)
const blockerView = ref<InstanceType<typeof OperationBlockers> | null>(null)
const blockersTotal = ref(0)
const blockersReady = ref(false)
const recoveryReady = ref(false)
const recoveryFailed = ref(false)
const viewReady = ref(false)
const selectedHostId = ref<number | null>(null)
const busy = computed(() => pendingRequests.value > 0 || loading.value || inspecting.value || planning.value || confirming.value || resolving.value !== null || confirmationOpen.value || pendingCancelledId.value !== null || detailDialog.value || detailBusy.value)
watch(busy, (value) => emit('busy', value), { immediate: true, flush: 'sync' })
const moduleInfo = computed(() => {
  const source = catalog.value?.modules.find((item) => item.id === props.module)
  if (!source || !props.allowedActions && !props.initialAction) return source
  return { ...source, actions: source.actions.filter((item) => props.initialAction ? item.id === props.initialAction : props.allowedActions?.includes(item.id)) }
})
const actions = computed(() => moduleInfo.value?.actions.map((item) => item.id) ?? [])
const executionStatus = computed(() => {
  const status = prepared.value?.status
  return status === 'queued' || status === 'running' ? status : null
})
const canStart = computed(() => !props.fixedHost || recoveryReady.value && !recoveryFailed.value)
const writeReady = computed(() => !confirmingUncertain.value && !detailFailed.value && (!props.fixedHost || blockersReady.value && recoveryReady.value && !recoveryFailed.value && blockersTotal.value === 0))
const streamTaskId = computed(() => viewReady.value && preparedLoaded.value && prepared.value && isRunningOperation(prepared.value.status) ? prepared.value.id : null)
const streamVisible = computed(() => activeView.value && viewReady.value)
const { snapshot, state: streamState, connect, stop } = useOperationOutput(streamTaskId, selectedHostId, streamVisible, (id) => { void loadTask(id) })
let active = true
let optionsRequest = 0
let inspectRequest = 0
let taskRequest = 0
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function owns(task: OperationTask) {
  return task.module === props.module && actions.value.includes(task.action) && (!props.fixedHost || task.hosts.some((host) => host.host_id === props.fixedHost?.id))
}
function canConfirm(task: OperationTask) {
  return owns(task) && (!props.fixedHost || task.hosts.length === 1 && task.hosts[0]?.host_id === props.fixedHost.id)
}
async function locate(id: string) {
  if (!props.fixedHost) return
  const section = props.section ?? props.module
  if (route.query.taskId === id && route.query.section === section) return
  await router.replace({ path: route.path, query: { ...route.query, section, taskId: id } })
}
async function clearLocation() {
  await router.replace({ path: route.path, query: { ...route.query, section: props.section ?? props.module, taskId: undefined } })
}
function closeConfirmation() {
  if (confirming.value || prepared.value?.status !== 'planned') return
  pendingCancelledId.value = prepared.value.id
  confirmationOpen.value = false
}
async function finishConfirmationClose() {
  const id = pendingCancelledId.value
  if (!id) return
  if (prepared.value?.id === id && prepared.value.status === 'planned') {
    prepared.value = null
    preparedLoaded.value = false
    selectedHostId.value = null
  }
  try {
    if (route.query.taskId === id && route.query.section === (props.section ?? props.module)) {
      await nextTick()
      await clearLocation()
    }
  } finally {
    if (route.query.taskId === id) recoveryFailed.value = true
    pendingCancelledId.value = null
  }
}
async function abandonConfirmation() {
  if (!confirmingUncertain.value || !preparedLoaded.value || prepared.value?.status !== 'planned') return
  prepared.value = null
  preparedLoaded.value = false
  confirmingUncertain.value = false
  detailFailed.value = false
  await clearLocation()
}
async function loadOptions() {
  const current = ++optionsRequest
  loading.value = true
  ready.value = false
  pendingRequests.value++
  try {
    const [nextCatalog, nextHosts] = await Promise.all([getOperationCatalog(), props.fixedHost ? Promise.resolve([props.fixedHost]) : listHosts('', null)])
    if (!active || current !== optionsRequest) return
    const source = nextCatalog.modules.find((item) => item.id === props.module)
    if (!source) throw new HttpError()
    validateOperationActions(props.module, source.actions)
    catalog.value = nextCatalog
    hosts.value = nextHosts
    ready.value = true
    if (props.fixedHost) void restore()
  } catch (error) { if (active && current === optionsRequest) showRequestError(error) }
  finally { pendingRequests.value--; if (active && current === optionsRequest) loading.value = false }
}

async function loadTask(id: string): Promise<boolean> {
  if (prepared.value?.id !== id) return false
  const current = ++taskRequest
  pendingRequests.value++
  try {
    const task = await getOperationTask(id)
    if (!active || current !== taskRequest) return false
    if (!owns(task)) throw new HttpError()
    prepared.value = task
    preparedLoaded.value = true
    if (task.status !== 'planned') confirmingUncertain.value = false
    if (!task.hosts.some((host) => host.host_id === selectedHostId.value)) selectedHostId.value = props.fixedHost?.id ?? task.hosts[0]?.host_id ?? null
    viewReady.value = true
    detailFailed.value = false
    if (props.fixedHost) void blockerView.value?.refresh(true)
    return true
  } catch (error) {
    if (active && current === taskRequest) { detailFailed.value = true; showRequestError(error) }
    return false
  } finally { pendingRequests.value-- }
}

async function restore() {
  const host = props.fixedHost
  if (!host || !moduleInfo.value) return
  const current = ++taskRequest
  viewReady.value = false
  prepared.value = null
  preparedLoaded.value = false
  selectedHostId.value = null
  recoveryReady.value = false
  recoveryFailed.value = false
  detailFailed.value = false
  try {
    const section = props.section ?? props.module
    const requested = route.query.taskId
    if (requested !== undefined && route.query.section !== section) { recoveryFailed.value = true; return }
    if (requested !== undefined && (typeof requested !== 'string' || !uuid.test(requested))) { recoveryFailed.value = true; return }
    const attention = await recoverOperation(host.id, props.module, actions.value, 'attention')
    if (!active || current !== taskRequest) return
    let requestedTask: OperationTask | null = null
    if (typeof requested === 'string') {
      requestedTask = await getOperationTask(requested)
      if (!active || current !== taskRequest) return
      if (requestedTask.id.toLowerCase() !== requested.toLowerCase() || !owns(requestedTask) || requestedTask.status === 'planned') throw new HttpError()
    }
    const summary = attention.task ?? (requestedTask ? null : (await recoverOperation(host.id, props.module, actions.value, 'latest')).task)
    if (!active || current !== taskRequest) return
    let task = requestedTask
    if (summary) {
      if (!actions.value.includes(summary.action) || summary.module !== props.module) throw new HttpError()
      if (summary.id !== requestedTask?.id) {
        task = await getOperationTask(summary.id)
        if (!active || current !== taskRequest) return
      }
      if (!task || task.id !== summary.id || !owns(task) || task.status === 'planned') throw new HttpError()
    }
    prepared.value = task
    if (task) {
      preparedLoaded.value = true
      selectedHostId.value = host.id
      if (activeView.value && (route.query.taskId !== task.id || route.query.section !== section)) await locate(task.id)
    }
    if (!active || current !== taskRequest) return
    recoveryReady.value = true
    viewReady.value = activeView.value && !!task
  } catch (error) { if (active && current === taskRequest) { recoveryFailed.value = true; showRequestError(error) } }
}

function changed() {
  inspectRequest++
  inspection.value = null
  lastInspectInput.value = null
  inspecting.value = false
  inspectFailed.value = false
  if (prepared.value?.status === 'planned') {
    const id = prepared.value.id
    taskRequest++
    prepared.value = null
    preparedLoaded.value = false
    confirmationOpen.value = false
    if (route.query.taskId === id && !pendingCancelledId.value) void clearLocation()
  }
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
  } catch (error) { if (active && current === inspectRequest) { inspectFailed.value = !(error instanceof RequestCancelledError); showRequestError(error) } }
  finally { pendingRequests.value--; if (active && current === inspectRequest) inspecting.value = false }
}

async function prepare(input: OperationPlanInput) {
  const action = moduleInfo.value?.actions.find((item) => item.id === input.action)
  if (!action || input.module !== props.module || !canStart.value || executionStatus.value !== null || planning.value || confirming.value || pendingCancelledId.value !== null || action.destructive && !writeReady.value || props.fixedHost && (input.host_ids.length !== 1 || input.host_ids[0] !== props.fixedHost.id)) return
  const current = ++taskRequest
  planning.value = true
  pendingRequests.value++
  try {
    if (action.destructive && props.fixedHost) {
      const clear = await blockerView.value?.refresh(true)
      if (!clear) return
      if (!active || current !== taskRequest || !writeReady.value) return
    }
    const task = await prepareOperation(input, { isCurrent: () => active && current === taskRequest })
    if (!active || current !== taskRequest) return
    if (!canConfirm(task) || task.status !== 'planned') throw new HttpError()
    prepared.value = task
    preparedLoaded.value = true
    selectedHostId.value = props.fixedHost?.id ?? task.hosts[0]?.host_id ?? null
    await locate(task.id)
    if (!active || current !== taskRequest) return
    if (action.destructive) confirmationOpen.value = true
    else { planning.value = false; void confirm(task.id) }
  } catch (error) { if (active && current === taskRequest) showRequestError(error) }
  finally { pendingRequests.value--; if (active && current === taskRequest) planning.value = false }
}

async function confirm(id: string) {
  const selected = prepared.value
  if (!selected || selected.id !== id || !preparedLoaded.value || selected.status !== 'planned' || !canConfirm(selected) || confirming.value) return
  const current = ++taskRequest
  confirming.value = true
  pendingRequests.value++
  try {
    const task = await confirmOperation(id, { isCurrent: () => active && current === taskRequest })
    if (!active || current !== taskRequest) return
    confirmationOpen.value = false
    if (!owns(task)) throw new HttpError()
    prepared.value = task
    viewReady.value = activeView.value
  } catch (error) {
    if (active && current === taskRequest) {
      confirmationOpen.value = false
      confirmingUncertain.value = true
      preparedLoaded.value = false
      showRequestError(error)
      void loadTask(id)
    }
  } finally { pendingRequests.value--; confirming.value = false }
}

async function resolve(id: string, hostId: number, note: string) {
  const task = prepared.value
  if (resolving.value || !task || task.id !== id || props.fixedHost && hostId !== props.fixedHost.id || !task.hosts.some((host) => host.host_id === hostId && host.status === 'unknown' && !host.resolved_at)) return
  resolving.value = { taskId: id, hostId }
  pendingRequests.value++
  try {
    const result = await resolveOperationHost(id, hostId, note)
    if (!active) return
    if (prepared.value?.id === id) { prepared.value = result; preparedLoaded.value = true }
    await blockerView.value?.refresh(true)
  } catch (error) { if (active) showRequestError(error) }
  finally { pendingRequests.value--; resolving.value = null }
}

async function reconnect() {
  const id = prepared.value?.id
  if (!id || !activeView.value) return
  const alreadyVisible = viewReady.value && streamTaskId.value === id
  if (await loadTask(id) && alreadyVisible && prepared.value?.id === id && isRunningOperation(prepared.value.status)) connect()
}
watch(activeView, (visible) => {
  if (!visible) { if (!recoveryReady.value && !planning.value && !confirming.value) taskRequest++; viewReady.value = false; stop() }
  else if (!recoveryReady.value || recoveryFailed.value || route.query.section === (props.section ?? props.module) && route.query.taskId && route.query.taskId !== prepared.value?.id) void restore()
  else if (prepared.value && prepared.value.status !== 'planned') void loadTask(prepared.value.id)
})
watch(() => [route.query.section, route.query.taskId], () => {
  if (activeView.value && ready.value && (recoveryFailed.value || !recoveryReady.value && !prepared.value || route.query.section === (props.section ?? props.module)
    && route.query.taskId !== prepared.value?.id)) void restore()
})
onMounted(() => { void loadOptions() })
onUnmounted(() => { active = false; optionsRequest++; inspectRequest++; taskRequest++; stop() })
</script>

<template>
  <component :is="embedded ? 'section' : 'main'" class="assets-main operations-main" :class="{ 'operations-embedded': embedded }">
    <div v-if="!embedded" class="assets-heading"><h1>{{ moduleInfo?.title ?? '服务器运维' }}</h1></div>
    <div v-if="!embedded && fixedHost" class="host-section server-operation-target"><strong>{{ fixedHost.name }}</strong><span>{{ fixedHost.address }}</span></div>
    <div v-loading="loading" class="operation-options">
      <template v-if="ready && catalog && moduleInfo">
        <OperationBlockers v-if="fixedHost" ref="blockerView" :host-id="fixedHost.id" @loaded="(ready, total) => { blockersReady = ready; blockersTotal = total }" @busy="detailBusy = $event" />
        <OperationSetup :module="module" :actions="moduleInfo.actions" :hosts="hosts" :fixed-host="fixedHost" :initial-action="initialAction" :hosts-ready="ready" :can-start="canStart" :can-write="writeReady" :execution-status="executionStatus" :busy="planning || confirming || confirmingUncertain || detailFailed || confirmationOpen || pendingCancelledId !== null" :inspecting="inspecting" @changed="changed" @inspect="inspect" @prepare="prepare" />
        <section v-if="inspection || inspectFailed" class="host-section operation-section" aria-label="主机现状"><template v-if="inspection"><div class="section-header"><h2>主机现状 · {{ inspection.host_name }}</h2></div><div class="operation-output"><pre>{{ inspection.output }}</pre></div></template><ElButton v-else :loading="inspecting" :disabled="!lastInspectInput" @click="lastInspectInput && inspect(lastInspectInput)">重试读取</ElButton></section>
        <section v-if="recoveryFailed" class="host-section operation-section"><ElButton @click="restore">重新查询任务</ElButton><ElButton v-if="route.query.taskId" @click="clearLocation">返回当前操作</ElButton></section>
        <section v-if="confirmingUncertain && prepared" class="host-section operation-section">{{ preparedLoaded && prepared.status === 'planned' ? '操作尚未执行' : '执行结果尚未确认' }} <ElButton v-if="preparedLoaded && prepared.status === 'planned' && canConfirm(prepared)" @click="moduleInfo.actions.find((item) => item.id === prepared?.action)?.destructive ? confirmationOpen = true : confirm(prepared.id)">{{ moduleInfo.actions.find((item) => item.id === prepared?.action)?.destructive ? '重新确认' : '重新查询' }}</ElButton><ElButton @click="loadTask(prepared.id)">查询结果</ElButton><ElButton v-if="preparedLoaded && prepared.status === 'planned'" @click="abandonConfirmation">放弃本次确认</ElButton></section>
        <section v-if="detailFailed && prepared && preparedLoaded && !confirmingUncertain" class="host-section operation-section">{{ streamState === 'done' && snapshot?.task_id === prepared.id ? `已收到任务终态（${taskLabels[snapshot.status]}），详情尚未取得` : '执行结果尚未确认' }} <ElButton @click="loadTask(prepared.id)">查询结果</ElButton></section>
        <OperationTaskDetail v-if="prepared && preparedLoaded && prepared.status !== 'planned' && !(detailFailed && streamState === 'done')" :task="prepared" :allowed-host-id="fixedHost?.id" :resolving-host-id="resolving?.taskId === prepared.id ? resolving.hostId : null" @resolve="resolve" @dialog-open="detailDialog = $event" @busy="detailBusy = $event" />
        <OperationLiveOutput v-if="prepared && preparedLoaded && prepared.status !== 'planned' && selectedHostId !== null" :task="prepared" :snapshot="snapshot" :host-id="selectedHostId" :allowed-host-id="fixedHost?.id" :state="streamState" :details-pending="detailFailed && streamState === 'done' && snapshot?.task_id === prepared.id" @update:host-id="selectedHostId = $event" @reconnect="reconnect" />
        <OperationConfirmationDialog :task="confirmationOpen && prepared?.status === 'planned' ? prepared : null" :action="moduleInfo.actions.find((item) => item.id === prepared?.action)" :confirming="confirming" @close="closeConfirmation" @closed="finishConfirmationClose" @confirm="confirm" />
      </template>
      <section v-else-if="!loading" class="host-section operation-section"><ElButton @click="loadOptions">重试加载</ElButton></section>
    </div>
  </component>
</template>
