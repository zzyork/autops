<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElAlert, ElButton, ElLoading, ElMessageBox, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { deleteInspectionTask, getInspectionTask, listInspectionTasks } from '@/api/inspections'
import InspectionCreateDialog from '@/components/InspectionCreateDialog.vue'
import InspectionRecordSummary from '@/components/InspectionRecordSummary.vue'
import ListPagination from '@/components/ListPagination.vue'
import { DEFAULT_PAGE_SIZE } from '@/components/pagination'
import { showSystemError } from '@/components/feedback'
import { isActiveRun, runLabel, runType } from '@/components/inspectionDisplay'
import { timeLabel } from '@/components/timeDisplay'
import type { TaskDetail, TaskSummary } from '@/types/inspections'
import '@/styles/inspections.css'

const vLoading = ElLoading.directive
const props = defineProps<{ records?: boolean }>()
const route = useRoute()
const router = useRouter()
const pageSize = ref(DEFAULT_PAGE_SIZE)
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
const taskTable = ref<{
  clearSelection: () => void
  toggleAllSelection: () => void
  toggleRowSelection: (task: TaskSummary, selected: boolean) => void
} | null>(null)
const selectedTasks = ref<TaskSummary[]>([])
const deletableTasks = computed(() => tasks.value.filter((task) => !isActiveRun(task.status)))
const allTasksSelected = computed(() =>
  deletableTasks.value.length > 0 && selectedTasks.value.length === deletableTasks.value.length,
)
const deletingIds = ref<string[]>([])
const deleting = computed(() => deletingIds.value.length > 0)
const deletionFailure = ref<{ deleted: number; notSubmitted: number } | null>(null)
const taskLabel = computed(() => props.records ? '巡检记录' : '巡检任务')
let active = true
let listRequest = 0
let detailRequest = 0
let listFailures = 0
let detailFailures = 0
let listTimer: ReturnType<typeof setTimeout> | undefined
let detailTimer: ReturnType<typeof setTimeout> | undefined

function canSelectTask(task: TaskSummary) {
  return listLoaded.value && !listLoading.value && !deleting.value && !isActiveRun(task.status)
}
function toggleAllTasks() {
  if (!listLoaded.value || listLoading.value || deleting.value || !deletableTasks.value.length) return
  taskTable.value?.toggleAllSelection()
}
function clearSelectedTasks() {
  selectedTasks.value = []
  taskTable.value?.clearSelection()
}
function scheduleList() {
  clearTimeout(listTimer)
  if (active && !deleting.value && !selectedId.value && tasks.value.some((task) => isActiveRun(task.status))) {
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
  if (!active || deleting.value) return
  clearTimeout(listTimer)
  const current = ++listRequest
  const wasActive = tasks.value.some((task) => isActiveRun(task.status))
  if (!poll) {
    listFailures = 0
    clearSelectedTasks()
  }
  listLoading.value = true
  try {
    const result = await listInspectionTasks(pageSize.value, (page.value - 1) * pageSize.value, props.records === true)
    if (!active || current !== listRequest) return
    const lastPage = Math.max(1, Math.ceil(result.total / pageSize.value))
    if (page.value > lastPage) {
      page.value = lastPage
      await loadList()
      return
    }
    const selectableIds = new Set(result.items.filter((task) => !isActiveRun(task.status)).map((task) => task.id))
    for (const task of selectedTasks.value) {
      if (!selectableIds.has(task.id)) taskTable.value?.toggleRowSelection(task, false)
    }
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
  if (deleting.value) return
  void router.push({ path: '/inspections/records', query: { task: id } })
}
function selectRecord(id: string) {
  clearSelectedTasks()
  clearTimeout(detailTimer)
  detailRequest++
  selectedId.value = id
  detail.value = null
  detailLoaded.value = false
  void loadDetail(id)
}
function changePage() {
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
async function removeTasks(requested: TaskSummary[]) {
  if (!active || deleting.value || listLoading.value || !listLoaded.value || !requested.length) return
  const requestedIds = new Set(requested.map((task) => task.id))
  const targets = tasks.value.filter((task) => requestedIds.has(task.id))
  const firstTarget = targets[0]
  if (!firstTarget || targets.length !== requestedIds.size || targets.some((task) => isActiveRun(task.status))) return
  deletingIds.value = targets.map((task) => task.id)
  clearTimeout(listTimer)
  listRequest++
  let deleted = 0
  try {
    const targetLabel = targets.length === 1
      ? `${taskLabel.value}“${firstTarget.name}”`
      : `所选 ${targets.length} 项${taskLabel.value}`
    try {
      await ElMessageBox.confirm(
        `确定删除${targetLabel}吗？关联的任务、巡检记录、主机检查结果及报告将一并删除，此操作不可撤销。`,
        `删除${taskLabel.value}`,
        {
          confirmButtonText: '删除',
          cancelButtonText: '取消',
          type: 'warning',
          confirmButtonClass: 'delete-confirm-button',
        },
      )
    } catch {
      return
    }
    if (!active) return
    deletionFailure.value = null
    // 逐项等待确认结果；任一失败即停止，已完成的删除不视为回滚。
    for (const task of targets) {
      if (!active) return
      deletingDetailId.value = task.id
      if (selectedId.value === task.id) {
        clearTimeout(detailTimer)
        detailRequest++
        detailLoading.value = false
      }
      await deleteInspectionTask(task.id)
      deleted++
      if (!active) return
      taskTable.value?.toggleRowSelection(task, false)
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
      if (props.records && route.query.task === task.id) {
        void router.replace({ path: '/inspections/records' })
      }
    }
  } catch {
    if (active) {
      deletionFailure.value = { deleted, notSubmitted: targets.length - deleted - 1 }
      showSystemError()
    }
  } finally {
    deletingDetailId.value = null
    deletingIds.value = []
    if (active) {
      if (deleted === targets.length && !selectedId.value) {
        page.value = Math.min(page.value, Math.max(1, Math.ceil(total.value / pageSize.value)))
        void loadList()
      } else {
        scheduleList()
      }
      if (selectedId.value && !detailLoaded.value) void loadDetail(selectedId.value)
    }
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
      <section v-if="records && selectedId" v-loading="detailLoading" class="ui-panel inspection-record-detail" aria-label="巡检记录概览">
        <div class="section-header"><ElButton @click="router.push({ path: '/inspections/records' })">返回</ElButton></div>
        <InspectionRecordSummary v-if="detailLoaded && detail" :task="detail" />
        <p v-else-if="!detailLoading" class="ui-load-retry">详情未加载。<ElButton @click="loadDetail(selectedId!)">重试</ElButton></p>
      </section>
      <section v-else class="ui-panel" :aria-label="records ? '巡检记录列表' : '巡检任务列表'">
        <div class="ui-toolbar">
          <div class="ui-toolbar-left">
            <ElButton
              :disabled="listLoading || !listLoaded || deleting || !deletableTasks.length"
              :aria-label="`${allTasksSelected ? '取消全选' : '全选'}当前页可删除的${taskLabel}`"
              @click="toggleAllTasks"
            >{{ allTasksSelected ? '取消全选' : '全选' }}</ElButton>
            <ElButton
              type="danger"
              :loading="deleting"
              :disabled="listLoading || !listLoaded || deleting || !selectedTasks.length"
              @click="removeTasks(selectedTasks)"
            >删除所选（{{ selectedTasks.length }}）</ElButton>
            <span v-if="!records" class="ui-text-muted">仅可选择已结束的任务</span>
          </div>
          <div class="ui-toolbar-right">
            <ElButton v-if="!records" type="primary" :disabled="deleting" @click="creating = true">创建巡检</ElButton>
            <ElButton :loading="listLoading" :disabled="deleting" @click="loadList()">刷新</ElButton>
          </div>
        </div>
        <ElAlert v-if="deletionFailure" type="warning" :closable="false" show-icon class="ui-page-alert">
          <template #title>
            已确认删除 {{ deletionFailure.deleted }} 项，1 项删除结果未确认<span v-if="deletionFailure.notSubmitted">，{{ deletionFailure.notSubmitted }} 项未提交</span>。
          </template>
        </ElAlert>
        <div v-loading="listLoading" class="ui-table-wrap">
           <!-- 轮询失败时隐藏旧数据并保留表格实例，恢复后继续核对本页选择。 -->
           <ElTable
             v-show="listLoaded"
             ref="taskTable"
             :data="tasks"
             row-key="id"
             class="ui-table"
             :empty-text="records ? '暂无历史记录' : '暂无巡检任务'"
             @selection-change="selectedTasks = $event"
           >
             <ElTableColumn type="selection" width="44" :selectable="canSelectTask" reserve-selection />
             <ElTableColumn label="任务名称" min-width="210">
               <template #default="{ row }">
                 <ElButton link type="primary" class="inspection-name" :disabled="deleting" @click="selectTask(row.id)">{{ row.name }}</ElButton>
               </template>
             </ElTableColumn>
            <ElTableColumn label="执行状态" width="115"><template #default="{ row }"><ElTag :type="runType(row.status)" size="small">{{ runLabel(row.status) }}</ElTag></template></ElTableColumn>
            <ElTableColumn label="主机进度" width="160"><template #default="{ row }">{{ row.completed_hosts }} / {{ row.host_count }} 完成 · {{ row.failed_hosts }} 失败</template></ElTableColumn>
            <ElTableColumn label="创建时间" min-width="180"><template #default="{ row }">{{ timeLabel(row.created_at) }}</template></ElTableColumn>
            <ElTableColumn label="结束时间" min-width="180"><template #default="{ row }">{{ timeLabel(row.finished_at) }}</template></ElTableColumn>
             <ElTableColumn label="操作" :width="records ? 110 : 180" fixed="right">
               <template #default="{ row }">
                 <div class="ui-toolbar-left">
                   <ElButton v-if="!records" link type="primary" :disabled="deleting" @click="selectTask(row.id)">查看记录</ElButton>
                   <span :title="isActiveRun(row.status) ? '排队中、执行中的任务不可删除' : undefined">
                     <ElButton
                       link
                       type="danger"
                       :loading="deletingIds.includes(row.id)"
                       :disabled="!canSelectTask(row as TaskSummary)"
                       @click="removeTasks([row as TaskSummary])"
                     >删除</ElButton>
                   </span>
                 </div>
               </template>
             </ElTableColumn>
          </ElTable>
            <p v-if="!listLoaded && !listLoading" class="ui-load-retry">{{ records ? '历史记录' : '任务列表' }}未加载。<ElButton @click="loadList()">重试</ElButton></p>
        </div>
        <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :total-known="listLoaded && !listLoading" :disabled="listLoading || !listLoaded || deleting" @change="changePage" />
      </section>
    <InspectionCreateDialog v-if="!records" v-model="creating" @created="created" />
</template>
