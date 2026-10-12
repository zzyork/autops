<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElLoading, ElPagination, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { getInspectionTask, listInspectionTasks } from '@/api/inspections'
import InspectionCreateDialog from '@/components/InspectionCreateDialog.vue'
import InspectionTaskDetail from '@/components/InspectionTaskDetail.vue'
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
const detailLoaded = ref(false)
const creating = ref(false)
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
    const result = await listInspectionTasks(PAGE_SIZE, (page.value - 1) * PAGE_SIZE)
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
  clearTimeout(detailTimer)
  const current = ++detailRequest
  const wasActive = detail.value !== null && isActiveRun(detail.value.status)
  if (!poll) detailFailures = 0
  detailLoading.value = true
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
  if (props.records) void router.replace({ path: '/inspections/records' })
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
watch(() => route.query.task, (id) => {
  if (!props.records) return
  if (typeof id === 'string' && id) selectRecord(id)
  else {
    clearTimeout(detailTimer)
    detailRequest++
    selectedId.value = null
    detail.value = null
    detailLoaded.value = false
    detailLoading.value = false
  }
}, { immediate: true })
onMounted(() => { void loadList() })
onUnmounted(() => {
  active = false
  listRequest++
  detailRequest++
  clearTimeout(listTimer)
  clearTimeout(detailTimer)
})
</script>

<template>
      <div v-if="records && selectedId" v-loading="detailLoading" class="host-section inspection-record-detail">
        <InspectionTaskDetail v-if="detailLoaded && detail" :task="detail" />
        <p v-else-if="!detailLoading" class="inspection-retry">详情未加载。<ElButton @click="loadDetail(selectedId!)">重试</ElButton></p>
      </div>
      <section class="host-section" :aria-label="records ? '巡检记录列表' : '巡检任务列表'">
        <div class="host-toolbar"><div><ElButton v-if="!records" type="primary" @click="creating = true">创建巡检</ElButton></div><ElButton :loading="listLoading" @click="loadList()">刷新</ElButton></div>
        <div v-loading="listLoading" class="host-table-wrap">
          <ElTable v-if="listLoaded" :data="tasks" row-key="id" class="host-table" :empty-text="records ? '暂无巡检记录' : '暂无巡检任务'">
            <ElTableColumn label="任务名称" min-width="210"><template #default="{ row }"><ElButton link type="primary" class="inspection-name" @click="selectTask(row.id)">{{ row.name }}</ElButton></template></ElTableColumn>
            <ElTableColumn label="执行状态" width="115"><template #default="{ row }"><ElTag :type="runType(row.status)" size="small">{{ runLabel(row.status) }}</ElTag></template></ElTableColumn>
            <ElTableColumn label="主机进度" width="160"><template #default="{ row }">{{ row.completed_hosts }} / {{ row.host_count }} 完成 · {{ row.failed_hosts }} 失败</template></ElTableColumn>
            <ElTableColumn label="创建时间" min-width="180"><template #default="{ row }">{{ timeLabel(row.created_at) }}</template></ElTableColumn>
            <ElTableColumn label="结束时间" min-width="180"><template #default="{ row }">{{ timeLabel(row.finished_at) }}</template></ElTableColumn>
            <ElTableColumn v-if="!records" label="操作" width="110" fixed="right"><template #default="{ row }"><ElButton link type="primary" @click="selectTask(row.id)">查看记录</ElButton></template></ElTableColumn>
          </ElTable>
          <p v-else-if="!listLoading" class="inspection-retry">任务列表未加载。<ElButton @click="loadList()">重试</ElButton></p>
        </div>
        <div v-if="listLoaded && total > PAGE_SIZE" class="inspection-pagination"><ElPagination :current-page="page" :page-size="PAGE_SIZE" :total="total" layout="total, prev, pager, next" @current-change="changePage" /></div>
      </section>
    <InspectionCreateDialog v-if="!records" v-model="creating" @created="created" />
</template>
