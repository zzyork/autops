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
  <article class="inspection-analysis-issue">
    <header class="issue-heading">
      <div class="issue-title"><ElTag :type="analysisSeverityType(issue.severity)" size="small">{{ analysisSeverityLabel(issue.severity) }}</ElTag><h4>{{ issue.title }}</h4></div>
    </header>
    <dl class="issue-context">
      <div><dt>影响主机</dt><dd>{{ host }}</dd></div>
    </dl>
    <div class="issue-analysis-grid">
      <section><h5>原因分析</h5><p>{{ issue.analysis }}</p></section>
      <section><h5>处理建议</h5><p>{{ issue.recommendation }}</p></section>
    </div>
    <div class="issue-footer">
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
.issue-context, .issue-detail-context { display: grid; gap: 8px; margin: 0; }
.issue-context { padding: 0 16px; }
.issue-context > div, .issue-detail-context > div { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 16px; }
.issue-context dt, .issue-detail-context dt { color: var(--ui-text-secondary); }
.issue-context dd, .issue-detail-context dd { margin: 0; white-space: pre-wrap; }
.issue-message { font-family: ui-monospace, Consolas, monospace; }
.issue-analysis-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; padding: 0 16px; }
.issue-analysis-grid section { min-width: 0; border-top: 1px solid var(--ui-border); padding-top: 12px; }
.issue-analysis-grid h5 { margin: 0 0 8px; font-size: 13px; font-weight: 600; }
.issue-footer { display: grid; gap: 8px; padding: 0 16px 12px; }
.issue-group { display: grid; gap: 8px; padding: 12px 0; border-bottom: 1px solid var(--ui-border); }
</style>
