<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElTag } from 'element-plus'
import { runLabel, runType, summarizeChecks, timeLabel } from '@/components/inspectionDisplay'
import InspectionAnalysisReport from '@/components/InspectionAnalysisReport.vue'
import type { TaskDetail } from '@/types/inspections'

const props = defineProps<{ task: TaskDetail }>()
const router = useRouter()
const summary = computed(() => summarizeChecks(props.task.hosts.flatMap((host) => host.checks)))
</script>

<template>
  <section class="inspection-detail" aria-label="巡检记录概览">
    <div class="section-header">
      <h2>{{ task.name }}</h2>
      <ElButton type="primary" @click="router.push({ name: 'inspection-record-detail', params: { taskId: task.id } })">巡检记录详情</ElButton>
    </div>
    <div class="inspection-detail-meta">
      <span>执行状态 <ElTag :type="runType(task.status)" size="small">{{ runLabel(task.status) }}</ElTag></span>
      <span>主机 {{ task.completed_hosts }} / {{ task.host_count }} 完成，{{ task.failed_hosts }} 失败</span>
      <span>开始 {{ timeLabel(task.started_at) }}</span>
      <span>结束 {{ timeLabel(task.finished_at) }}</span>
    </div>
    <div class="inspection-host-summary" aria-label="本次巡检风险概览">
      <ElTag :type="summary.critical ? 'danger' : 'info'" size="small">重要 {{ summary.critical }}</ElTag>
      <ElTag :type="summary.warning ? 'warning' : 'info'" size="small">警告 {{ summary.warning }}</ElTag>
      <span v-if="summary.incomplete" class="inspection-muted">{{ summary.incomplete }} 项检查尚未完成，风险无法完整判定</span>
    </div>
    <InspectionAnalysisReport :task-id="task.id" :task-status="task.status" />
  </section>
</template>
