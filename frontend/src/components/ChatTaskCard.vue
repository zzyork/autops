<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElTag } from 'element-plus'
import { getInspectionAnalysis, getInspectionTask } from '@/api/inspections'
import { showRequestError } from '@/components/feedback'
import { isActiveRun, runLabel, runType } from '@/components/inspectionDisplay'
import { analysisStatusLabel } from '@/components/inspectionAnalysisDisplay'
import type { AnalysisResponse, TaskDetail } from '@/types/inspections'
import '@/styles/inspections.css'

const props = defineProps<{ taskId: string }>()
const router = useRouter()
const task = ref<TaskDetail | null>(null)
const loaded = ref(false)
const loading = ref(false)
const analysis = ref<AnalysisResponse | null>(null)
const analysisLoaded = ref(false)
const analysisLoading = ref(false)
const reportAvailable = computed(() => {
  if (!analysisLoaded.value || !analysis.value || !task.value) return false
  return analysis.value.report !== null || (!isActiveRun(task.value.status) && analysis.value.status !== 'queued' && analysis.value.status !== 'running')
})
let active = true
let timer: ReturnType<typeof setTimeout> | undefined
let analysisTimer: ReturnType<typeof setTimeout> | undefined
let sequence = 0
let analysisSequence = 0
let terminalPolls = 0
const POLL_MS = 1000
const ANALYSIS_POLL_MS = 2000
const TERMINAL_POLL_COUNT = 5

async function loadAnalysis() {
  clearTimeout(analysisTimer)
  const current = ++analysisSequence
  analysisLoading.value = true
  try {
    const result = await getInspectionAnalysis(props.taskId)
    if (!active || current !== analysisSequence) return
    analysis.value = result
    analysisLoaded.value = true
    const taskActive = task.value !== null && isActiveRun(task.value.status)
    if (!taskActive && result.status === 'not_generated') terminalPolls = Math.max(0, terminalPolls - 1)
    if (taskActive || result.status === 'queued' || result.status === 'running' || (result.status === 'not_generated' && terminalPolls > 0)) {
      analysisTimer = setTimeout(() => { void loadAnalysis() }, ANALYSIS_POLL_MS)
    }
  } catch {
    if (!active || current !== analysisSequence) return
    analysisLoaded.value = false
    showRequestError()
  } finally {
    if (active && current === analysisSequence) analysisLoading.value = false
  }
}

async function load() {
  clearTimeout(timer)
  const current = ++sequence
  loading.value = true
  try {
    const result = await getInspectionTask(props.taskId)
    if (!active || current !== sequence) return
    const firstLoad = task.value === null
    const justFinished = task.value !== null && isActiveRun(task.value.status) && !isActiveRun(result.status)
    task.value = result
    loaded.value = true
    if (isActiveRun(result.status)) timer = setTimeout(() => { void load() }, POLL_MS)
    if (firstLoad || justFinished) {
      terminalPolls = isActiveRun(result.status) ? 0 : TERMINAL_POLL_COUNT
      void loadAnalysis()
    }
  } catch {
    if (!active || current !== sequence) return
    loaded.value = false
    showRequestError()
  } finally {
    if (active && current === sequence) loading.value = false
  }
}
onMounted(() => { void load() })
onUnmounted(() => { active = false; sequence++; analysisSequence++; clearTimeout(timer); clearTimeout(analysisTimer) })
</script>

<template>
  <section class="ai-task" :aria-label="`巡检任务 ${task?.name ?? taskId}`">
    <template v-if="loaded && task">
      <div class="ai-card-heading"><strong>{{ task.name }}</strong><ElTag :type="runType(task.status)" size="small">{{ runLabel(task.status) }}</ElTag></div>
      <p class="inspection-muted">已完成 {{ task.completed_hosts }} / {{ task.host_count }} 台主机巡检，执行失败 {{ task.failed_hosts }} 台。</p>
      <div v-if="analysisLoaded && analysis" class="ai-task-analysis-status"><p class="inspection-muted" role="status">AI 报告：{{ analysisStatusLabel(analysis.status) }}<template v-if="analysis.report && analysis.status !== 'completed'">，可查看上次成功生成的报告</template>。</p><ElButton link type="primary" :loading="analysisLoading" @click="loadAnalysis">刷新报告状态</ElButton></div>
      <p v-else-if="analysisLoading" class="inspection-muted">正在读取 AI 报告状态...</p>
      <p v-else class="inspection-retry">AI 报告状态未加载。<ElButton @click="loadAnalysis">重试</ElButton></p>
      <div class="ai-task-actions">
        <ElButton type="primary" :disabled="!reportAvailable" @click="router.push({ name: 'inspection-records', query: { task: task.id } })">查看 AI 报告</ElButton>
        <ElButton @click="router.push({ name: 'inspection-record-detail', params: { taskId: task.id } })">查看巡检记录</ElButton>
      </div>
    </template>
    <p v-else-if="loading" class="inspection-muted">正在读取任务...</p>
    <p v-else class="inspection-retry">任务未加载。<ElButton @click="load">重试</ElButton></p>
  </section>
</template>
