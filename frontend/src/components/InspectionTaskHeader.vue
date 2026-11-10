<script setup lang="ts">
import { computed } from 'vue'
import { ElTag } from 'element-plus'
import { hostProgressLabel, runLabel, runState, summarizeChecks } from '@/components/inspectionDisplay'
import { timeLabel } from '@/components/timeDisplay'
import type { TaskDetail } from '@/types/inspections'

const props = defineProps<{ task: TaskDetail }>()
const summary = computed(() => summarizeChecks(props.task.hosts.flatMap((host) => host.checks)))
</script>

<template>
  <header class="inspection-task-header">
    <div class="section-header inspection-record-heading">
      <div class="inspection-record-title">
        <h1>{{ task.name }}</h1>
        <ElTag class="ui-execution-status" :data-execution-state="runState(task.status)" size="small">
          {{ runLabel(task.status) }}
        </ElTag>
      </div>
      <slot />
    </div>
    <dl class="inspection-record-overview" aria-label="本次巡检概览">
      <div>
        <dt>主机进度</dt>
        <dd class="ui-execution-status" :data-execution-state="task.failed_hosts ? 'incomplete' : undefined">
          {{ hostProgressLabel(task) }}
        </dd>
      </div>
      <div v-if="summary.critical > 0 || summary.warning > 0">
        <dt>风险统计</dt>
        <dd class="inspection-record-risks">
          <ElTag v-if="summary.critical > 0" type="danger" size="small">
            紧急 {{ summary.critical }}
          </ElTag>
          <ElTag v-if="summary.warning > 0" class="inspection-risk-tag" type="warning" size="small">
            警告 {{ summary.warning }}
          </ElTag>
        </dd>
      </div>
      <div><dt>巡检开始</dt><dd>{{ timeLabel(task.started_at) }}</dd></div>
      <div><dt>巡检结束</dt><dd>{{ timeLabel(task.finished_at) }}</dd></div>
    </dl>
    <p
      v-if="summary.incomplete"
      class="ui-execution-status ui-execution-notice"
      :data-execution-state="summary.incompleteState"
    >{{ summary.incomplete }} 项检查尚未完成，风险无法完整判定</p>
  </header>
</template>
