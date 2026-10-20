<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { generateInspectionAnalysis, getInspectionAnalysis } from '@/api/inspections'
import { showSystemError } from '@/components/feedback'
import { isActiveRun, runLabel } from '@/components/inspectionDisplay'
import { timeLabel } from '@/components/timeDisplay'
import ListPagination from '@/components/ListPagination.vue'
import InspectionAnalysisIssue from '@/components/InspectionAnalysisIssue.vue'
import { analysisSeverityLabel as severityLabel, analysisSeverityType as severityType, analysisStatusLabel as statusLabel, issueDiagnosticGroups } from '@/components/inspectionAnalysisDisplay'
import { useListPagination } from '@/components/pagination'
import type { AnalysisEvidence, AnalysisIssue, AnalysisResponse, RunStatus } from '@/types/inspections'

const props = defineProps<{ taskId: string; taskStatus: RunStatus }>()
const POLL_INTERVAL_MS = 2000
const TERMINAL_POLL_COUNT = 5
const response = ref<AnalysisResponse | null>(null)
const loaded = ref(false)
const loading = ref(false)
const generating = ref(false)
const loadFailed = ref(false)
let terminalPolls = 0
let request = 0
let session = 0
let active = true
let timer: ReturnType<typeof setTimeout> | undefined

const report = computed(() => response.value?.report ?? null)
const logEvidenceIds = computed(() => new Set(report.value?.evidence.filter((item) => item.kind === 'log').map((item) => item.id) ?? []))
const logIssues = computed(() => report.value?.issues.filter((issue) => issue.evidence_ids.some((id) => logEvidenceIds.value.has(id))) ?? [])
const otherProblems = computed(() => report.value?.evidence.filter((item) => item.kind === 'finding' && item.severity !== 'info') ?? [])
const { page: logPage, pageSize: logPageSize, total: logTotal, pageItems: visibleLogs, resetPage: resetLogs } = useListPagination(logIssues)
const { page: problemPage, pageSize: problemPageSize, total: problemTotal, pageItems: visibleProblems, resetPage: resetProblems } = useListPagination(otherProblems)
const legacyLogs = computed(() => logIssues.value.some((issue) => issue.log_source === null || issue.log_source === undefined))

function issueHost(issue: AnalysisIssue): string {
  const items = report.value?.evidence.filter((evidence) => issue.evidence_ids.includes(evidence.id)) ?? []
  return [...new Set(items.map((item) => `${item.host_name} (${item.address})`))].join('、')
}

function statusType(status: AnalysisResponse['status']): 'info' | 'success' | 'warning' | 'danger' {
  if (status === 'completed') return 'success'
  if (status === 'failed' || status === 'interrupted') return 'danger'
  if (status === 'unavailable') return 'warning'
  return 'info'
}
function kindLabel(kind: AnalysisEvidence['kind']): string {
  return { host: '主机', check: '检查', finding: '风险发现', log: '日志' }[kind]
}

function schedule() {
  clearTimeout(timer)
  if (!active || loadFailed.value || generating.value || !response.value) return
  const status = response.value.status
  if (isActiveRun(props.taskStatus) || status === 'queued' || status === 'running' || (status === 'not_generated' && terminalPolls > 0)) {
    timer = setTimeout(() => { void load(true) }, POLL_INTERVAL_MS)
  }
}

async function load(poll = false) {
  clearTimeout(timer)
  const current = ++request
  const currentSession = session
  if (!poll) loading.value = true
  try {
    const result = await getInspectionAnalysis(props.taskId)
    if (!active || currentSession !== session || current !== request) return
    response.value = result
    loaded.value = true
    loadFailed.value = false
    if (!isActiveRun(props.taskStatus) && result.status === 'not_generated') terminalPolls = Math.max(0, terminalPolls - 1)
    schedule()
  } catch {
    if (!active || currentSession !== session || current !== request) return
    loadFailed.value = true
    loaded.value = false
    showSystemError()
  } finally {
    if (active && currentSession === session && current === request) loading.value = false
  }
}

function refresh() {
  if (generating.value) return
  loadFailed.value = false
  void load()
}

async function generate() {
  if (!loaded.value || !response.value?.can_generate || isActiveRun(props.taskStatus) || response.value.status === 'queued' || response.value.status === 'running' || generating.value || loading.value) return
  clearTimeout(timer)
  request++
  const currentSession = session
  const id = props.taskId
  let submitted = false
  generating.value = true
  try {
    const result = await generateInspectionAnalysis(id)
    if (!active || currentSession !== session) return
    response.value = result
    loaded.value = true
    loadFailed.value = false
    submitted = true
  } catch {
    if (active && currentSession === session) {
      loaded.value = false
      loadFailed.value = true
      showSystemError()
    }
  } finally {
    if (active && currentSession === session) generating.value = false
    if (active && currentSession === session && submitted) schedule()
  }
}

function exportText() {
  const value = report.value
  if (!loaded.value || !value) return
  const issueLines = (issues: AnalysisIssue[]) => issues.flatMap((issue) => [
    `[${severityLabel(issue.severity)}] ${issue.title} · ${issueHost(issue)}`,
    ...(issue.log_source != null ? [`日志文件路径 / 来源：${issue.log_source}`] : []),
    ...(issue.log_message != null ? [`报错内容：${issue.log_message}`] : []),
    ...issueDiagnosticGroups(issue).flatMap((group) => [
      `诊断组：${group.id}；${group.host_count} 台主机；${group.occurrences} 次来源观察`,
      `报错模板：${group.template}`,
      ...group.observations.map((item) => `${item.host_name} (${item.address}) · ${item.source} · ${item.occurrences} 次 · ${item.first_time ?? '时间未知'} 至 ${item.last_time ?? '时间未知'}`),
    ]),
    `报错原因：${issue.analysis}`,
    `处理手段建议：${issue.recommendation}`,
    `证据：${issue.evidence_ids.join('、') || '无'}`,
    '',
  ])
  const content = [
    '巡检 AI 汇报', `任务：${value.task_name}（${runLabel(value.task_status)}）`,
    `采集开始：${timeLabel(value.inspection_started_at)}；结束：${timeLabel(value.inspection_finished_at)}`,
    `生成时间：${timeLabel(value.generated_at)}`, `模型：${value.model_name} (v${value.model_version})`,
    `范围：${value.host_count} 台主机，${value.finding_count} 条发现，${value.log_count} 条日志，${value.incomplete_count} 项未完成，${value.unassessed_count} 项不适用或结论未知`,
    '', '非错误日志问题', ...otherProblems.value.map((item) =>
      `[${severityLabel(item.severity)}] ${item.host_name} (${item.address}) · ${item.check_title}：${item.content}`),
    '', '错误日志分析', ...(legacyLogs.value ? ['此汇报为旧版汇总，可重新生成诊断组分析。'] : []),
    ...issueLines(logIssues.value), '日志证据',
    ...value.evidence.filter((item) => item.kind === 'log').flatMap((item) => [
      `[${item.id}] ${severityLabel(item.severity)} / ${kindLabel(item.kind)} / ${item.host_name} (${item.address})`,
      `${item.check_title} / ${item.source}${item.source_table_index != null ? ` / 来源表 ${item.source_table_index}` : ''}`, item.content,
      ...(item.original_lines ?? []).map((line, index) => item.original_indices?.[index] != null ? `结果行 ${item.original_indices[index]}：${line}` : line), '',
    ]),
  ].join('\n')
  const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = '巡检AI汇报.txt'
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

watch(() => props.taskId, () => {
  session++
  request++
  clearTimeout(timer)
  response.value = null
  loaded.value = false
  loading.value = false
  generating.value = false
  loadFailed.value = false
  resetLogs()
  resetProblems()
  terminalPolls = isActiveRun(props.taskStatus) ? 0 : TERMINAL_POLL_COUNT
  void load()
}, { immediate: true })
watch(() => props.taskStatus, (status, previous) => {
  if (isActiveRun(previous) && !isActiveRun(status) && !loadFailed.value) {
    terminalPolls = TERMINAL_POLL_COUNT
    void load()
  }
})
onUnmounted(() => {
  active = false
  session++
  request++
  clearTimeout(timer)
})
</script>

<template>
  <section class="inspection-analysis" aria-label="巡检 AI 汇报">
    <div class="section-header inspection-analysis-heading">
      <h2>AI 巡检报告</h2>
    </div>
    <div class="inspection-analysis-toolbar">
      <div class="inspection-analysis-actions">
        <ElButton type="primary" :loading="generating" :disabled="!loaded || !response?.can_generate || isActiveRun(taskStatus) || response?.status === 'queued' || response?.status === 'running' || loading" @click="generate">{{ report ? '重新生成' : '生成 AI 汇报' }}</ElButton>
        <ElButton v-if="loaded && report" @click="exportText">导出汇报</ElButton>
      </div>
      <ElButton :loading="loading" :disabled="generating" @click="refresh">刷新</ElButton>
    </div>
    <p v-if="loadFailed" class="ui-text-muted">汇报未加载，请刷新重试。</p>
    <p v-else-if="!loaded" class="ui-text-muted">正在读取汇报状态…</p>
    <template v-else-if="response">
      <dl class="inspection-analysis-meta">
        <div><dt>本轮状态</dt><dd><ElTag :type="statusType(response.status)" size="small">{{ statusLabel(response.status) }}</ElTag></dd></div>
        <div v-if="response.model_name"><dt>本轮模型</dt><dd>{{ response.model_name }}<template v-if="response.model_version !== null"> (v{{ response.model_version }})</template></dd></div>
        <div v-if="response.started_at"><dt>生成开始</dt><dd>{{ timeLabel(response.started_at) }}</dd></div>
        <div v-if="response.finished_at"><dt>生成结束</dt><dd>{{ timeLabel(response.finished_at) }}</dd></div>
      </dl>
      <p v-if="response.status === 'unavailable'" class="ui-text-muted">{{ response.can_generate ? '上次生成时主模型不可用，现在可以重新生成。' : '主模型未配置或未通过测试，暂不可生成汇报。' }}</p>
      <p v-else-if="response.status === 'not_generated' && isActiveRun(taskStatus)" class="ui-text-muted">巡检进行中，结束后将检查自动生成条件。</p>
      <p v-else-if="response.status === 'not_generated'" class="ui-text-muted">尚无 AI 汇报。</p>
      <p v-else-if="response.status === 'queued'" class="ui-text-muted">本轮汇报排队中。</p>
      <p v-else-if="response.status === 'running'" class="ui-text-muted" role="status">
        <template v-if="response.progress">{{ response.progress.current_step }}，本阶段开始 {{ timeLabel(response.progress.step_started_at) }}。</template>
        <template v-else>正在生成本轮汇报。</template>
      </p>
      <p v-else-if="response.status === 'failed' || response.status === 'interrupted'" class="ui-text-muted">本轮汇报{{ statusLabel(response.status) }}。已有汇报如有显示，仍为上次成功生成的版本。</p>
      <p v-if="!response.can_generate && !isActiveRun(taskStatus) && response.status !== 'queued' && response.status !== 'running' && response.status !== 'unavailable'" class="ui-text-muted">当前无法发起生成，请检查主模型及生成服务状态。</p>
      <template v-if="report">
        <section class="inspection-analysis-saved" aria-label="已保存汇报摘要">
          <div class="inspection-analysis-saved-heading"><strong>{{ response.status === 'completed' ? '已保存汇报' : '上次成功汇报' }}</strong><span class="ui-text-muted">生成于 {{ timeLabel(report.generated_at) }}</span></div>
          <dl class="inspection-analysis-stats">
            <div><dt>分析主机</dt><dd>{{ report.host_count }} <span>台</span></dd></div>
            <div><dt>巡检发现</dt><dd>{{ report.finding_count }} <span>条</span></dd></div>
            <div><dt>采集日志</dt><dd>{{ report.log_count }} <span>条</span></dd></div>
            <div><dt>未完成检查</dt><dd>{{ report.incomplete_count }} <span>项</span></dd></div>
          </dl>
          <div class="inspection-analysis-provenance"><span>报告模型：{{ report.model_name }} (v{{ report.model_version }})</span><span>采集时间：{{ timeLabel(report.inspection_started_at) }} 至 {{ timeLabel(report.inspection_finished_at) }}</span></div>
        </section>
        <section v-if="report.incomplete_count" class="inspection-analysis-section">
          <h3>未完成检查</h3>
          <p>本次有 {{ report.incomplete_count }} 项检查未完成，相关风险无法完整判定。</p>
          <p v-for="item in report.evidence.filter((evidence) => evidence.incomplete && evidence.kind === 'check')" :key="item.id" class="ui-text-muted">{{ item.id }} · {{ item.host_name }} · {{ item.check_title }}：检查未完成，无法判定。</p>
        </section>
        <section v-if="report.unassessed_count" class="inspection-analysis-section">
          <h3>判定范围限制</h3>
          <p>本次有 {{ report.unassessed_count }} 项检查不适用或结论未知，不能作为健康依据。</p>
          <p v-for="item in report.evidence.filter((evidence) => evidence.limited)" :key="item.id" class="ui-text-muted">{{ item.id }} · {{ item.host_name }} · {{ item.check_title }}：不适用或结论未知。</p>
        </section>
        <p v-if="!report.issues.length" class="ui-text-muted">没有可分析的匹配错误日志或巡检风险；正常检查不进行 AI 分析。</p>
        <section v-if="problemTotal" class="inspection-analysis-section">
          <div class="inspection-analysis-section-heading"><h3>非错误日志问题</h3><span class="ui-text-muted">{{ problemTotal }} 项</span></div>
          <div class="ui-table-wrap">
            <ElTable :data="visibleProblems" row-key="id" class="ui-table">
              <ElTableColumn label="级别" width="90"><template #default="{ row }"><ElTag :type="severityType(row.severity)" size="small">{{ severityLabel(row.severity) }}</ElTag></template></ElTableColumn>
              <ElTableColumn label="影响主机" min-width="240"><template #default="{ row }"><div class="ui-item-title">{{ row.host_name }}</div><div class="ui-item-secondary">{{ row.address }}</div></template></ElTableColumn>
              <ElTableColumn prop="check_title" label="检查项" min-width="150" />
              <ElTableColumn label="问题描述" min-width="360"><template #default="{ row }"><p>{{ row.content }}</p></template></ElTableColumn>
            </ElTable>
          </div>
          <ListPagination v-model:page="problemPage" v-model:page-size="problemPageSize" :total="problemTotal" />
        </section>
        <section v-if="logTotal" class="inspection-analysis-section">
          <div class="inspection-analysis-section-heading"><h3>错误日志分析</h3><span class="ui-text-muted">{{ logTotal }} 项</span></div>
          <p v-if="legacyLogs" class="ui-text-muted">此汇报为旧版汇总，可重新生成诊断组分析。</p>
          <InspectionAnalysisIssue v-for="(issue, index) in visibleLogs" :key="`${report.generated_at}:${(logPage - 1) * logPageSize + index}`" :issue="issue" :host="issueHost(issue)" :evidence="report.evidence" />
          <ListPagination v-model:page="logPage" v-model:page-size="logPageSize" :total="logTotal" />
        </section>
      </template>
    </template>
  </section>
</template>
