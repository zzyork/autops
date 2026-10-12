<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ElButton, ElTag } from 'element-plus'
import { getInspectionTask } from '@/api/inspections'
import { showRequestError } from '@/components/feedback'
import { isActiveRun, runLabel, runType } from '@/components/inspectionDisplay'
import InspectionTaskDetail from '@/components/InspectionTaskDetail.vue'
import type { TaskDetail } from '@/types/inspections'
import '@/styles/inspections.css'

const props = defineProps<{ taskId: string }>()
const task = ref<TaskDetail | null>(null)
const loaded = ref(false)
const loading = ref(false)
const expanded = ref(false)
let active = true
let timer: ReturnType<typeof setTimeout> | undefined
let sequence = 0
const POLL_MS = 1000

async function load() {
  clearTimeout(timer)
  const current = ++sequence
  loading.value = true
  try {
    const result = await getInspectionTask(props.taskId)
    if (!active || current !== sequence) return
    task.value = result
    loaded.value = true
    if (isActiveRun(result.status)) timer = setTimeout(() => { void load() }, POLL_MS)
  } catch {
    if (!active || current !== sequence) return
    loaded.value = false
    showRequestError()
  } finally {
    if (active && current === sequence) loading.value = false
  }
}
onMounted(() => { void load() })
onUnmounted(() => { active = false; sequence++; clearTimeout(timer) })
</script>

<template>
  <section class="ai-task" :aria-label="`巡检任务 ${task?.name ?? taskId}`">
    <template v-if="loaded && task">
      <div class="ai-card-heading"><strong>{{ task.name }}</strong><ElTag :type="runType(task.status)" size="small">{{ runLabel(task.status) }}</ElTag></div>
      <p class="inspection-muted">主机 {{ task.completed_hosts }} / {{ task.host_count }} 完成，{{ task.failed_hosts }} 失败</p>
      <ElButton link type="primary" :aria-expanded="expanded" @click="expanded = !expanded">{{ expanded ? '收起详情' : '查看详情' }}</ElButton>
      <InspectionTaskDetail v-if="expanded" :task="task" />
    </template>
    <p v-else-if="loading" class="inspection-muted">正在读取任务...</p>
    <p v-else class="inspection-retry">任务未加载。<ElButton @click="load">重试</ElButton></p>
  </section>
</template>
