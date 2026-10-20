<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElLoading } from 'element-plus'
import { getInspectionTask } from '@/api/inspections'
import InspectionTaskDetail from '@/components/InspectionTaskDetail.vue'
import { showSystemError } from '@/components/feedback'
import { isActiveRun } from '@/components/inspectionDisplay'
import type { TaskDetail } from '@/types/inspections'
import '@/styles/inspections.css'

const vLoading = ElLoading.directive
const route = useRoute()
const router = useRouter()
const task = ref<TaskDetail | null>(null)
const loading = ref(false)
const loaded = ref(false)
const POLL_INTERVAL_MS = 1000
let request = 0
let active = true
let timer: ReturnType<typeof setTimeout> | undefined

async function load(poll = false) {
  clearTimeout(timer)
  const id = route.params.taskId
  if (typeof id !== 'string') return
  const current = ++request
  if (!poll) loading.value = true
  try {
    const result = await getInspectionTask(id)
    if (!active || current !== request) return
    task.value = result
    loaded.value = true
    if (isActiveRun(result.status)) timer = setTimeout(() => { void load(true) }, POLL_INTERVAL_MS)
  } catch {
    if (!active || current !== request) return
    loaded.value = false
    showSystemError()
  } finally {
    if (active && current === request) loading.value = false
  }
}

watch(() => route.params.taskId, () => {
  task.value = null
  loaded.value = false
  void load()
}, { immediate: true })
onUnmounted(() => {
  active = false
  request++
  clearTimeout(timer)
})
</script>

<template>
    <main class="console-main">
      <div class="console-page-heading inspection-section-heading">
        <ElButton @click="router.push({ path: '/inspections/records', query: { task: route.params.taskId } })">返回巡检记录</ElButton>
      </div>
      <section v-loading="loading" class="ui-panel inspection-record-detail" aria-label="服务器巡检记录">
        <InspectionTaskDetail v-if="loaded && task" :task="task" />
        <p v-else-if="!loading" class="ui-load-retry">详情未加载。<ElButton @click="load()">重试</ElButton></p>
      </section>
    </main>
</template>
