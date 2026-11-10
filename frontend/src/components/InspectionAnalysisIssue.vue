<script setup lang="ts">
import { computed } from 'vue'
import { ElTag } from 'element-plus'
import DisclosurePanel from '@/components/DisclosurePanel.vue'
import ListPagination from '@/components/ListPagination.vue'
import { useListPagination } from '@/components/pagination'
import { analysisSeverityLabel, analysisSeverityType, issueLogDetails } from '@/components/inspectionAnalysisDisplay'
import type { AnalysisEvidence, AnalysisIssue } from '@/types/inspections'

const props = defineProps<{ issue: AnalysisIssue; host: string; evidence: AnalysisEvidence[] }>()
const details = computed(() => issueLogDetails(props.issue, props.evidence))
const { page, pageSize, total, pageItems } = useListPagination(details)
</script>

<template>
  <article class="inspection-analysis-issue" :aria-label="issue.title">
    <header class="issue-heading">
      <ElTag :type="analysisSeverityType(issue.severity)" size="small">{{ analysisSeverityLabel(issue.severity) }}</ElTag>
      <dl class="issue-context">
        <div><dt>影响主机</dt><dd>{{ host }}</dd></div>
      </dl>
    </header>
    <section class="issue-analysis-block">
      <h4>原因分析</h4>
      <p>{{ issue.analysis }}</p>
    </section>
    <section class="issue-analysis-block issue-analysis-recommendation">
      <h4>处理建议</h4>
      <p>{{ issue.recommendation }}</p>
    </section>
    <DisclosurePanel v-if="total" label="相关报错详情" :context="issue.title">
      <div v-for="detail in pageItems" :key="detail.id" class="issue-group">
        <p class="issue-message">{{ detail.message }}</p>
        <dl class="issue-detail-context">
          <div><dt>主机</dt><dd>{{ detail.host }}</dd></div>
          <div v-if="detail.path"><dt>日志路径</dt><dd>{{ detail.path }}</dd></div>
          <div><dt>报错时间范围</dt><dd>{{ detail.firstTime ?? '未记录' }} 至 {{ detail.lastTime ?? '未记录' }}</dd></div>
          <div><dt>报错发生次数</dt><dd>{{ detail.occurrences === null ? '未记录' : `${detail.occurrences} 次` }}</dd></div>
        </dl>
      </div>
      <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" />
    </DisclosurePanel>
  </article>
</template>

<style scoped>
.inspection-analysis-issue { display: grid; gap: var(--ui-space-4); min-width: 0; }
.inspection-analysis-issue + .inspection-analysis-issue { padding-top: var(--ui-space-4); border-top: 1px solid var(--ui-border); }
.issue-heading { display: flex; align-items: center; flex-wrap: wrap; gap: var(--ui-space-2) var(--ui-space-4); }
.issue-heading > .el-tag { flex: none; }
.inspection-analysis-issue :is(p, strong, h4, dd) { overflow-wrap: anywhere; min-width: 0; }
.inspection-analysis-issue p { margin: 0; white-space: pre-wrap; line-height: var(--ui-line-height-base); }
.issue-context, .issue-detail-context { display: grid; gap: var(--ui-space-2); margin: 0; }
.issue-context { flex: 1; min-width: 0; color: var(--ui-text-secondary); font-size: var(--ui-font-size-small); line-height: var(--ui-line-height-small); }
.issue-context > div, .issue-detail-context > div { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: var(--ui-space-4); }
.issue-context > div { grid-template-columns: max-content minmax(0, 1fr); }
.issue-context dt, .issue-detail-context dt { color: var(--ui-text-secondary); }
.issue-context dd, .issue-detail-context dd { margin: 0; white-space: pre-wrap; }
.inspection-analysis-issue .issue-message { font-family: var(--ui-font-mono); font-size: var(--ui-font-size-code); line-height: var(--ui-line-height-code); }
.issue-analysis-block { display: grid; grid-template-columns: 80px minmax(0, 1fr); gap: var(--ui-space-4); min-width: 0; }
.issue-analysis-block h4 { margin: 0; font-size: var(--ui-font-size-base); line-height: calc(var(--ui-line-height-base) + var(--ui-space-1)); font-weight: 600; }
.issue-analysis-block p { line-height: calc(var(--ui-line-height-base) + var(--ui-space-1)); }
.issue-analysis-recommendation { padding-top: var(--ui-space-3); border-top: 1px solid var(--ui-border); }
.issue-analysis-recommendation h4 { color: var(--ui-primary); }
.issue-group { display: grid; gap: var(--ui-space-2); padding: var(--ui-space-3) 0; border-bottom: 1px solid var(--ui-border); }
</style>
