<script setup lang="ts">
import { computed } from 'vue'
import { ElButton, ElCollapse, ElCollapseItem, ElTag } from 'element-plus'
import { analysisSeverityLabel, analysisSeverityType, issueDiagnosticGroups } from '@/components/inspectionAnalysisDisplay'
import type { AnalysisIssue } from '@/types/inspections'

const props = defineProps<{ issue: AnalysisIssue; host: string }>()
const emit = defineEmits<{ evidence: [] }>()
const groups = computed(() => issueDiagnosticGroups(props.issue))
const occurrences = computed(() => groups.value.reduce((total, group) => total + group.occurrences, 0))
const hostCount = computed(() => new Set(groups.value.flatMap((group) => group.observations.map((item) => JSON.stringify([item.host_name, item.address])))).size)
</script>

<template>
  <div class="inspection-analysis-issue">
    <div class="issue-title"><ElTag :type="analysisSeverityType(issue.severity)" size="small">{{ analysisSeverityLabel(issue.severity) }}</ElTag><strong>{{ issue.title }}</strong></div>
    <p>{{ host }}</p>
    <p v-if="groups.length">{{ hostCount }} 台主机 · {{ occurrences }} 次来源观察 · {{ groups.length }} 个关联报错类型</p>
    <template v-if="groups.length <= 1 && issue.log_source != null">
      <p><strong>日志文件路径 / 来源：</strong>{{ issue.log_source }}<template v-if="issue.log_source === 'systemd journal'">（未采集具体文件路径）</template></p>
      <p v-if="issue.log_message != null"><strong>报错内容：</strong>{{ issue.log_message }}</p>
    </template>
    <p><strong>报错原因：</strong>{{ issue.analysis }}</p>
    <p><strong>处理手段建议：</strong>{{ issue.recommendation }}</p>
    <ElCollapse v-if="groups.length" class="issue-groups">
      <ElCollapseItem name="groups" :title="`关联报错类型（${groups.length}）`">
        <div v-for="group in groups" :key="group.id" class="issue-group">
          <p><strong>{{ group.id }}</strong><template v-if="group.service"> · {{ group.service }}</template> · {{ group.occurrences }} 次来源观察</p>
          <p>{{ group.template }}</p>
          <p v-for="(item, index) in group.observations" :key="index" class="inspection-muted">{{ item.host_name }} ({{ item.address }}) · {{ item.source }} · {{ item.occurrences }} 次 · {{ item.first_time ?? '时间未知' }} 至 {{ item.last_time ?? '时间未知' }}</p>
        </div>
      </ElCollapseItem>
    </ElCollapse>
    <ElButton v-if="issue.evidence_ids.length" link type="primary" @click="emit('evidence')">查看关联证据（{{ issue.evidence_ids.length }}）</ElButton>
  </div>
</template>

<style scoped>
.inspection-analysis-issue { display: grid; gap: 8px; padding: 8px 0 8px 12px; border-left: 2px solid var(--ui-border); min-width: 0; }
.issue-title { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0; }
.inspection-analysis-issue :is(p, strong) { overflow-wrap: anywhere; min-width: 0; }
.inspection-analysis-issue p { margin: 0; white-space: pre-wrap; }
.issue-group { display: grid; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--ui-border); }
</style>
