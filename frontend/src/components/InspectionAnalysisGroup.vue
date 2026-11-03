<script setup lang="ts">
import { computed } from 'vue'
import { ElTable, ElTableColumn, ElTag } from 'element-plus'
import InspectionAnalysisIssue from '@/components/InspectionAnalysisIssue.vue'
import ListPagination from '@/components/ListPagination.vue'
import { analysisSeverityLabel, analysisSeverityType, type AnalysisProblemGroup } from '@/components/inspectionAnalysisDisplay'
import { useListPagination } from '@/components/pagination'
import type { AnalysisEvidence } from '@/types/inspections'

const props = defineProps<{ group: AnalysisProblemGroup; evidence: AnalysisEvidence[] }>()
const problems = computed(() => props.group.problems)
const { page, pageSize, total, pageItems } = useListPagination(problems)
const findings = computed(() => pageItems.value.flatMap((problem) => problem.kind === 'finding' ? [problem.finding] : []))
const issues = computed(() => pageItems.value.flatMap((problem) => problem.kind === 'issue' ? [problem] : []))
</script>

<template>
  <section class="inspection-analysis-section" :aria-label="group.title">
    <div class="inspection-analysis-section-heading"><h3>{{ group.title }}</h3><span class="ui-text-muted">{{ total }} 项</span></div>
    <div v-if="findings.length" class="ui-table-wrap">
      <ElTable :data="findings" row-key="id" class="ui-table">
        <ElTableColumn label="级别" width="90"><template #default="{ row }"><ElTag :type="analysisSeverityType(row.severity)" size="small">{{ analysisSeverityLabel(row.severity) }}</ElTag></template></ElTableColumn>
        <ElTableColumn label="影响主机" min-width="240"><template #default="{ row }"><div class="ui-item-title">{{ row.host_name }}</div><div class="ui-item-secondary">{{ row.address }}</div></template></ElTableColumn>
        <ElTableColumn prop="check_title" label="检查项" min-width="150" />
        <ElTableColumn label="问题描述" min-width="360"><template #default="{ row }"><p>{{ row.content }}</p></template></ElTableColumn>
      </ElTable>
    </div>
    <InspectionAnalysisIssue v-for="problem in issues" :key="problem.id" :issue="problem.issue" :host="problem.host" :evidence="evidence" />
    <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" />
  </section>
</template>
