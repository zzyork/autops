<script setup lang="ts">
import { inject, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElLoading, ElMessageBox, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { HttpError, RequestCancelledError } from '@/api/http'
import { deleteExecution, getExecution, listExecutions, subscribeExecution } from '@/api/ssh_executions'
import { showRequestError } from '@/components/feedback'
import { useServerPagination } from '@/components/serverPagination'
import { workspaceVisibleKey } from '@/components/workspace'
import { executionLabel, executionTag, executionTime } from '@/components/sshExecutionDisplay'
import SSHExecutionDetail from '@/components/SSHExecutionDetail.vue'
import SSHExecutionCreateDialog from '@/components/SSHExecutionCreateDialog.vue'
import ListPagination from '@/components/ListPagination.vue'
import type { ExecutionDetail, ExecutionEvent, ExecutionSummary } from '@/types/sshExecutions'
import '@/styles/sshExecutions.css'

const vLoading = ElLoading.directive
const visible = inject(workspaceVisibleKey)
const list = useServerPagination(listExecutions)
const creating = ref(false)
const selectedId = ref<string | null>(null)
const detail = ref<ExecutionDetail | null>(null)
const detailLoading = ref(false)
const detailFailed = ref(false)
const disconnected = ref(false)
const deleting = ref(false)
let active = true
let generation = 0
let controller: AbortController | null = null
const OUTPUT_LIMIT = 20 * 256 * 1024
const encoder = new TextEncoder()
const isVisible = () => visible?.value !== false
let outputBytes = 0

function invalidate() {
  generation++
  controller?.abort()
  controller = null
  detailLoading.value = false
}
function applyEvent(event: ExecutionEvent, id: string) {
  const current = detail.value
  if (!current || current.id !== id || (event.kind !== 'done' && event.sequence !== current.sequence + 1)) throw new HttpError()
  if (event.kind === 'done') {
    if (event.sequence !== current.sequence || event.execution.id !== id || event.execution.status !== current.status
      || !['succeeded', 'failed', 'unknown'].includes(current.status)) throw new HttpError()
    detail.value = { ...current, ...event.execution, sequence: event.sequence }
    return
  }
  if (event.kind === 'state') {
    if (event.execution.id !== id || event.steps.length !== current.steps.length
      || new Set(event.steps.map((step) => step.id)).size !== event.steps.length
      || event.steps.some((step) => !current.steps.some((item) => item.id === step.id))) throw new HttpError()
    detail.value = { ...current, ...event.execution, sequence: event.sequence,
      steps: current.steps.map((item) => {
        const next = event.steps.find((step) => step.id === item.id)
        if (!next) throw new HttpError()
        return { ...item, ...next }
      }) }
    return
  }
  const index = current.steps.findIndex((step) => step.id === event.step_id)
  const step = current.steps[index]
  if (!step) throw new HttpError()
  const bytes = encoder.encode(event.text).length
  if (outputBytes + bytes > OUTPUT_LIMIT) throw new HttpError()
  const output = step[event.stream] + event.text
  outputBytes += bytes
  detail.value = { ...current, sequence: event.sequence,
    steps: current.steps.map((item, position) => position === index ? { ...item, [event.stream]: output } : item) }
}
async function loadDetail(id: string) {
  invalidate()
  if (!active || !isVisible()) return
  const current = generation
  const request = new AbortController()
  controller = request
  detail.value = null
  detailFailed.value = false
  disconnected.value = false
  detailLoading.value = true
  try {
    const snapshot = await getExecution(id, request.signal)
    if (!active || current !== generation || selectedId.value !== id || !isVisible()) return
    if (snapshot.id !== id) throw new HttpError()
    const bytes = snapshot.steps.reduce((total, step) => total + encoder.encode(step.stdout).length + encoder.encode(step.stderr).length, 0)
    if (bytes > OUTPUT_LIMIT) throw new HttpError()
    outputBytes = bytes
    detail.value = snapshot
    detailLoading.value = false
    await subscribeExecution(id, snapshot.sequence, request.signal, (event) => {
      if (!active || current !== generation || selectedId.value !== id || !isVisible()) throw new RequestCancelledError()
      applyEvent(event, id)
    })
    if (active && current === generation) void list.refresh()
  } catch (error) {
    if (!active || current !== generation || selectedId.value !== id || !isVisible()) return
    if (error instanceof RequestCancelledError) return
    if (!detail.value) detailFailed.value = true
    else disconnected.value = true
    showRequestError(error)
  } finally {
    if (active && current === generation) {
      detailLoading.value = false
      controller = null
    }
  }
}
function select(id: string) {
  selectedId.value = id
  void loadDetail(id)
}
function back() {
  invalidate()
  selectedId.value = null
  detail.value = null
  detailFailed.value = false
  disconnected.value = false
  void list.refresh()
}
function created(result: ExecutionDetail) {
  creating.value = false
  select(result.id)
  void list.refresh()
}
async function remove(item: ExecutionSummary) {
  if (deleting.value || item.status === 'queued' || item.status === 'running') return
  try {
    await ElMessageBox.confirm(`删除“${item.name}”（${item.host_name}）的执行记录？步骤、命令及全部输出将永久删除，不会撤销已执行的远端命令。`, '删除执行记录', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'delete-confirm-button',
    })
  } catch { return }
  deleting.value = true
  try {
    await deleteExecution(item.id)
    if (!active || !isVisible()) return
    if (selectedId.value === item.id) back()
    else await list.refresh()
  } catch (error) {
    if (active && isVisible()) showRequestError(error)
  } finally {
    deleting.value = false
  }
}
watch(() => visible?.value, (shown, previous) => {
  if (shown === false) { invalidate(); return }
  if (shown && previous === false && selectedId.value) void loadDetail(selectedId.value)
})
onUnmounted(() => { active = false; invalidate() })
</script>

<template>
  <main class="assets-main">
    <div class="assets-heading"><h1>SSH 执行</h1></div>
    <section v-if="selectedId" class="host-section" aria-label="执行详情">
      <div class="section-header"><ElButton @click="back">返回执行记录</ElButton><ElButton :loading="detailLoading" :disabled="detailLoading" @click="loadDetail(selectedId)">刷新结果 / 继续查看</ElButton></div>
      <div v-loading="detailLoading">
        <SSHExecutionDetail v-if="detail" :detail="detail" :disconnected="disconnected" />
        <div v-else-if="detailFailed" class="inspection-retry">详情未加载。<ElButton @click="loadDetail(selectedId)">重试读取</ElButton></div>
      </div>
    </section>
    <section v-else class="host-section" aria-label="执行记录列表">
      <div class="host-toolbar"><ElButton type="primary" @click="creating = true">创建执行</ElButton><ElButton :loading="list.loading.value" @click="list.refresh()">刷新</ElButton></div>
      <div v-loading="list.loading.value" class="host-table-wrap">
        <ElTable v-if="!list.loadFailed.value" :data="list.items.value" row-key="id" class="host-table" empty-text="暂无执行记录">
          <ElTableColumn label="名称" min-width="180"><template #default="{ row }"><ElButton link type="primary" class="ssh-execution-name" @click="select(row.id)">{{ row.name }}</ElButton></template></ElTableColumn>
          <ElTableColumn label="目标主机" min-width="200"><template #default="{ row }">{{ row.host_name }}<div class="host-address">{{ row.address }}</div></template></ElTableColumn>
          <ElTableColumn label="步骤" width="80" prop="step_count" />
          <ElTableColumn label="状态" width="110"><template #default="{ row }"><ElTag :type="executionTag(row.status)" size="small">{{ executionLabel(row.status) }}</ElTag></template></ElTableColumn>
          <ElTableColumn label="创建时间" width="180"><template #default="{ row }">{{ executionTime(row.created_at) }}</template></ElTableColumn>
          <ElTableColumn label="操作" width="100" fixed="right"><template #default="{ row }"><ElButton link type="danger" :loading="deleting" :disabled="deleting || row.status === 'queued' || row.status === 'running'" @click="remove(row as ExecutionSummary)">删除</ElButton></template></ElTableColumn>
        </ElTable>
        <div v-else-if="!list.loading.value" class="inspection-retry">记录未加载。<ElButton @click="list.refresh()">重试</ElButton></div>
      </div>
      <ListPagination v-model:page="list.page.value" v-model:page-size="list.pageSize.value" :total="list.total.value" :total-known="!list.loadFailed.value && !list.loading.value" :disabled="list.loading.value || list.loadFailed.value || deleting" />
    </section>
    <SSHExecutionCreateDialog v-if="creating" @close="creating = false" @created="created" />
  </main>
</template>
