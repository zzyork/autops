<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElTag } from 'element-plus'
import { runLabel, runType, summarizeChecks } from '@/components/inspectionDisplay'
import { timeLabel } from '@/components/timeDisplay'
import InspectionAnalysisReport from '@/components/InspectionAnalysisReport.vue'
import type { TaskDetail } from '@/types/inspections'

const props = defineProps<{ task: TaskDetail }>()
const router = useRouter()
const summary = computed(() => summarizeChecks(props.task.hosts.flatMap((host) => host.checks)))
</script>

<template>
  <section class="inspection-detail" aria-label="巡检记录概览">
    <div class="section-header inspection-record-heading">
      <div class="inspection-record-title"><h2>{{ task.name }}</h2><ElTag :type="runType(task.status)" size="small">{{ runLabel(task.status) }}</ElTag></div>
      <ElButton @click="router.push({ name: 'inspection-record-detail', params: { taskId: task.id } })">巡检记录详情</ElButton>
    </div>
    <dl class="inspection-record-overview" aria-label="本次巡检概览">
      <div><dt>主机进度</dt><dd><strong>{{ task.completed_hosts }} / {{ task.host_count }}</strong> 完成 <span class="ui-text-muted">· {{ task.failed_hosts }} 失败</span></dd></div>
      <div><dt>风险统计</dt><dd class="inspection-record-risks"><ElTag :type="summary.critical ? 'danger' : 'info'" size="small">重要 {{ summary.critical }}</ElTag><ElTag :type="summary.warning ? 'warning' : 'info'" size="small">警告 {{ summary.warning }}</ElTag></dd></div>
      <div><dt>巡检开始</dt><dd>{{ timeLabel(task.started_at) }}</dd></div>
      <div><dt>巡检结束</dt><dd>{{ timeLabel(task.finished_at) }}</dd></div>
    </dl>
    <p v-if="summary.incomplete" class="ui-text-muted">{{ summary.incomplete }} 项检查尚未完成，风险无法完整判定</p>
    <InspectionAnalysisReport :task-id="task.id" :task-status="task.status" />
  </section>
</template>
