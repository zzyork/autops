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
  <article class="inspection-analysis-issue">
    <header class="issue-heading">
      <div class="issue-title"><ElTag :type="analysisSeverityType(issue.severity)" size="small">{{ analysisSeverityLabel(issue.severity) }}</ElTag><h4>{{ issue.title }}</h4></div>
      <p v-if="groups.length" class="inspection-muted">{{ hostCount }} 台主机 · {{ occurrences }} 次来源观察 · {{ groups.length }} 个关联报错类型</p>
    </header>
    <dl class="issue-context">
      <div><dt>影响主机</dt><dd>{{ host }}</dd></div>
      <template v-if="groups.length <= 1 && issue.log_source != null">
        <div><dt>日志来源</dt><dd>{{ issue.log_source }}<template v-if="issue.log_source === 'systemd journal'">（未采集具体文件路径）</template></dd></div>
        <div v-if="issue.log_message != null"><dt>报错内容</dt><dd class="issue-message">{{ issue.log_message }}</dd></div>
      </template>
    </dl>
    <div class="issue-analysis-grid">
      <section><h5>原因分析</h5><p>{{ issue.analysis }}</p></section>
      <section><h5>处理建议</h5><p>{{ issue.recommendation }}</p></section>
    </div>
    <div class="issue-footer">
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
  </article>
</template>

<style scoped>
.inspection-analysis-issue { display: grid; gap: 16px; border: 1px solid var(--ui-border); min-width: 0; }
.issue-heading { display: grid; gap: 8px; padding: 12px 16px; background: var(--ui-row-hover); border-bottom: 1px solid var(--ui-border); }
.issue-title { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0; }
.issue-title h4 { margin: 0; font-size: 14px; font-weight: 600; }
.inspection-analysis-issue :is(p, strong, h4, dd) { overflow-wrap: anywhere; min-width: 0; }
.inspection-analysis-issue p { margin: 0; white-space: pre-wrap; line-height: 1.6; }
.issue-context { display: grid; gap: 8px; margin: 0; padding: 0 16px; }
.issue-context > div { display: grid; grid-template-columns: 80px minmax(0, 1fr); gap: 16px; }
.issue-context dt { color: var(--ui-text-secondary); }
.issue-context dd { margin: 0; white-space: pre-wrap; }
.issue-message { font-family: ui-monospace, Consolas, monospace; }
.issue-analysis-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; padding: 0 16px; }
.issue-analysis-grid section { min-width: 0; border-top: 1px solid var(--ui-border); padding-top: 12px; }
.issue-analysis-grid h5 { margin: 0 0 8px; font-size: 13px; font-weight: 600; }
.issue-footer { display: grid; gap: 8px; padding: 0 16px 12px; }
.issue-footer > .el-button { justify-self: start; }
.issue-groups { min-width: 0; }
.issue-group { display: grid; gap: 8px; padding: 12px 0; border-bottom: 1px solid var(--ui-border); }
</style>
