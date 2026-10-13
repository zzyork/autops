<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElLoading, ElMessageBox, ElPagination, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { deleteInspectionTask, getInspectionTask, listInspectionTasks } from '@/api/inspections'
import InspectionCreateDialog from '@/components/InspectionCreateDialog.vue'
import InspectionRecordSummary from '@/components/InspectionRecordSummary.vue'
import { showSystemError } from '@/components/feedback'
import { isActiveRun, runLabel, runType, timeLabel } from '@/components/inspectionDisplay'
import type { TaskDetail, TaskSummary } from '@/types/inspections'
import '@/styles/inspections.css'

const vLoading = ElLoading.directive
const props = defineProps<{ records?: boolean }>()
const route = useRoute()
const router = useRouter()
const PAGE_SIZE = 20
const POLL_INTERVAL_MS = 1000
const MAX_POLL_FAILURES = 2
const tasks = ref<TaskSummary[]>([])
const total = ref(0)
const page = ref(1)
const listLoading = ref(false)
const listLoaded = ref(false)
const detail = ref<TaskDetail | null>(null)
const selectedId = ref<string | null>(null)
const detailLoading = ref(false)
const deletingDetailId = ref<string | null>(null)
const detailLoaded = ref(false)
const creating = ref(false)
const deletingId = ref<string | null>(null)
let active = true
let listRequest = 0
let detailRequest = 0
let listFailures = 0
let detailFailures = 0
let listTimer: ReturnType<typeof setTimeout> | undefined
let detailTimer: ReturnType<typeof setTimeout> | undefined

function scheduleList() {
  clearTimeout(listTimer)
  if (active && tasks.value.some((task) => isActiveRun(task.status))) {
    listTimer = setTimeout(() => { void loadList(true) }, POLL_INTERVAL_MS)
  }
}
function scheduleDetail() {
  clearTimeout(detailTimer)
  if (active && detail.value && isActiveRun(detail.value.status)) {
    detailTimer = setTimeout(() => { void loadDetail(detail.value!.id, true) }, POLL_INTERVAL_MS)
  }
}
async function loadList(poll = false) {
  clearTimeout(listTimer)
  const current = ++listRequest
  const wasActive = tasks.value.some((task) => isActiveRun(task.status))
  if (!poll) listFailures = 0
  listLoading.value = true
  try {
    const result = await listInspectionTasks(PAGE_SIZE, (page.value - 1) * PAGE_SIZE, props.records === true)
    if (!active || current !== listRequest) return
    tasks.value = result.items
    total.value = result.total
    listLoaded.value = true
    listFailures = 0
    scheduleList()
  } catch {
    if (!active || current !== listRequest) return
    listLoaded.value = false
    listFailures++
    showSystemError()
    if (poll && wasActive && listFailures < MAX_POLL_FAILURES) listTimer = setTimeout(() => { void loadList(true) }, POLL_INTERVAL_MS)
  } finally {
    if (active && current === listRequest) listLoading.value = false
  }
}
async function loadDetail(id: string, poll = false) {
  if (deletingDetailId.value === id) return
  clearTimeout(detailTimer)
  const current = ++detailRequest
  const wasActive = detail.value !== null && isActiveRun(detail.value.status)
  if (!poll) detailFailures = 0
  if (!poll) detailLoading.value = true
  try {
    const result = await getInspectionTask(id)
    if (!active || current !== detailRequest || selectedId.value !== id) return
    detail.value = result
    detailLoaded.value = true
    detailFailures = 0
    const index = tasks.value.findIndex((item) => item.id === id)
    if (index >= 0) tasks.value.splice(index, 1, result)
    scheduleDetail()
  } catch {
    if (!active || current !== detailRequest || selectedId.value !== id) return
    detailLoaded.value = false
    detailFailures++
    showSystemError()
    if (poll && wasActive && detailFailures < MAX_POLL_FAILURES) detailTimer = setTimeout(() => { void loadDetail(id, true) }, POLL_INTERVAL_MS)
  } finally {
    if (active && current === detailRequest) detailLoading.value = false
  }
}
function selectTask(id: string) {
  void router.push({ path: '/inspections/records', query: { task: id } })
}
function selectRecord(id: string) {
  clearTimeout(detailTimer)
  detailRequest++
  selectedId.value = id
  detail.value = null
  detailLoaded.value = false
  void loadDetail(id)
}
function changePage(next: number) {
  page.value = next
  listLoaded.value = false
  void loadList()
}
function created() {
  page.value = 1
  clearTimeout(listTimer)
  listRequest++
  clearTimeout(detailTimer)
  detailRequest++
  void loadList()
}
async function removeRecord(task: TaskSummary) {
  if (!props.records || deletingId.value || isActiveRun(task.status)) return
  deletingId.value = task.id
  try {
    await ElMessageBox.confirm(`确定删除巡检记录“${task.name}”吗？该记录的主机检查结果及报告将一并删除，此操作不可撤销。`, '删除巡检记录', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'delete-confirm-button',
    })
  } catch {
    deletingId.value = null
    return
  }
  try {
    const latest = tasks.value.find((item) => item.id === task.id)
    if (!latest || isActiveRun(latest.status)) return
    deletingDetailId.value = task.id
    if (selectedId.value === task.id) {
      clearTimeout(detailTimer)
      detailRequest++
      detailLoading.value = false
    }
    await deleteInspectionTask(task.id)
    if (!active) return
    clearTimeout(listTimer)
    listRequest++
    listLoading.value = false
    tasks.value = tasks.value.filter((item) => item.id !== task.id)
    total.value = Math.max(0, total.value - 1)
    if (selectedId.value === task.id) {
      clearTimeout(detailTimer)
      detailRequest++
      selectedId.value = null
      detail.value = null
      detailLoaded.value = false
      detailLoading.value = false
    }
    if (route.query.task === task.id) void router.replace({ path: '/inspections/records' })
    page.value = Math.min(page.value, Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
    void loadList()
  } catch {
    if (active) showSystemError()
  } finally {
    deletingDetailId.value = null
    deletingId.value = null
    if (active && selectedId.value === task.id && !detailLoaded.value) void loadDetail(task.id)
  }
}
watch(() => route.query.task, (id, previous) => {
  if (!props.records) return
  if (typeof id === 'string' && id) {
    clearTimeout(listTimer)
    listRequest++
    listLoading.value = false
    selectRecord(id)
  }
  else {
    clearTimeout(detailTimer)
    detailRequest++
    selectedId.value = null
    detail.value = null
    detailLoaded.value = false
    detailLoading.value = false
    if (previous) void loadList()
  }
}, { immediate: true })
onMounted(() => { if (!props.records || !selectedId.value) void loadList() })
onUnmounted(() => {
  active = false
  listRequest++
  detailRequest++
  clearTimeout(listTimer)
  clearTimeout(detailTimer)
})
</script>

<template>
      <section v-if="records && selectedId" v-loading="detailLoading" class="host-section inspection-record-detail" aria-label="巡检记录概览">
        <div class="section-header"><ElButton @click="router.push({ path: '/inspections/records' })">返回历史记录</ElButton></div>
        <InspectionRecordSummary v-if="detailLoaded && detail" :task="detail" />
        <p v-else-if="!detailLoading" class="inspection-retry">详情未加载。<ElButton @click="loadDetail(selectedId!)">重试</ElButton></p>
      </section>
      <section v-else class="host-section" :aria-label="records ? '巡检记录列表' : '巡检任务列表'">
        <div class="host-toolbar"><div><ElButton v-if="!records" type="primary" @click="creating = true">创建巡检</ElButton></div><ElButton :loading="listLoading" @click="loadList()">刷新</ElButton></div>
        <div v-loading="listLoading" class="host-table-wrap">
           <ElTable v-if="listLoaded" :data="tasks" row-key="id" class="host-table" :empty-text="records ? '暂无历史记录' : '暂无巡检任务'">
            <ElTableColumn label="任务名称" min-width="210"><template #default="{ row }"><ElButton link type="primary" class="inspection-name" @click="selectTask(row.id)">{{ row.name }}</ElButton></template></ElTableColumn>
            <ElTableColumn label="执行状态" width="115"><template #default="{ row }"><ElTag :type="runType(row.status)" size="small">{{ runLabel(row.status) }}</ElTag></template></ElTableColumn>
            <ElTableColumn label="主机进度" width="160"><template #default="{ row }">{{ row.completed_hosts }} / {{ row.host_count }} 完成 · {{ row.failed_hosts }} 失败</template></ElTableColumn>
            <ElTableColumn label="创建时间" min-width="180"><template #default="{ row }">{{ timeLabel(row.created_at) }}</template></ElTableColumn>
            <ElTableColumn label="结束时间" min-width="180"><template #default="{ row }">{{ timeLabel(row.finished_at) }}</template></ElTableColumn>
            <ElTableColumn v-if="!records" label="操作" width="110" fixed="right"><template #default="{ row }"><ElButton link type="primary" @click="selectTask(row.id)">查看记录</ElButton></template></ElTableColumn>
            <ElTableColumn v-else label="操作" width="110" fixed="right"><template #default="{ row }"><span :title="isActiveRun(row.status) ? '执行中的记录不可删除' : undefined"><ElButton link type="danger" :loading="deletingId === row.id" :disabled="isActiveRun(row.status) || deletingId !== null" @click="removeRecord(row as TaskSummary)">删除</ElButton></span></template></ElTableColumn>
          </ElTable>
           <p v-else-if="!listLoading" class="inspection-retry">{{ records ? '历史记录' : '任务列表' }}未加载。<ElButton @click="loadList()">重试</ElButton></p>
        </div>
        <div v-if="listLoaded && total > PAGE_SIZE" class="inspection-pagination"><ElPagination :current-page="page" :page-size="PAGE_SIZE" :total="total" layout="total, prev, pager, next" @current-change="changePage" /></div>
      </section>
    <InspectionCreateDialog v-if="!records" v-model="creating" @created="created" />
</template>
