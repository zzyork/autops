<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElTag } from 'element-plus'
import { generateInspectionAnalysis, getInspectionAnalysis } from '@/api/inspections'
import { showSystemError } from '@/components/feedback'
import { isActiveRun, runLabel } from '@/components/inspectionDisplay'
import { timeLabel } from '@/components/timeDisplay'
import InspectionAnalysisGroup from '@/components/InspectionAnalysisGroup.vue'
import { analysisSeverityLabel as severityLabel, analysisState, analysisStatusLabel as statusLabel, groupAnalysisProblems, issueDiagnosticGroups } from '@/components/inspectionAnalysisDisplay'
import type { AnalysisEvidence, AnalysisIssue, AnalysisResponse, RunStatus } from '@/types/inspections'

const props = defineProps<{ taskId: string; taskStatus: RunStatus }>()
const emit = defineEmits<{ activity: [] }>()
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
const problemGroups = computed(() => report.value ? groupAnalysisProblems(report.value) : [])
const analyzedLogEvidence = computed(() => {
  const value = report.value
  if (!value) return []
  const ids = new Set(value.issues.flatMap((issue) => issue.evidence_ids))
  return value.evidence.filter((item) => item.kind === 'log' && ids.has(item.id))
})

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
  const issueLines = (issue: AnalysisIssue, host: string) => [
    `[${severityLabel(issue.severity)}] ${issue.title} · ${host}`,
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
  ]
  const content = [
    '巡检 AI 汇报', `任务：${value.task_name}（${runLabel(value.task_status)}）`,
    `采集开始：${timeLabel(value.inspection_started_at)}；结束：${timeLabel(value.inspection_finished_at)}`,
    `生成时间：${timeLabel(value.generated_at)}`, `模型：${value.model_name} (v${value.model_version})`,
    `范围：${value.host_count} 台主机，${value.finding_count} 条发现，${value.log_count} 条日志`,
    ...problemGroups.value.flatMap((group) => [
      '', `${group.title}（${group.problems.length} 项）`,
      ...group.problems.flatMap((problem) => {
        if (problem.kind === 'issue') return issueLines(problem.issue, problem.host)
        const item = problem.finding
        return [`[${severityLabel(item.severity)}] ${item.host_name} (${item.address}) · ${item.check_title}：${item.content}`]
      }),
    ]),
    ...(analyzedLogEvidence.value.length ? [
      '', '日志证据',
      ...analyzedLogEvidence.value.flatMap((item) => [
        `[${item.id}] ${severityLabel(item.severity)} / ${kindLabel(item.kind)} / ${item.host_name} (${item.address})`,
        `${item.check_title} / ${item.source}${item.source_table_index != null ? ` / 来源表 ${item.source_table_index}` : ''}`, item.content,
        ...(item.original_lines ?? []).map((line, index) => item.original_indices?.[index] != null ? `结果行 ${item.original_indices[index]}：${line}` : line), '',
      ]),
    ] : []),
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
  terminalPolls = isActiveRun(props.taskStatus) ? 0 : TERMINAL_POLL_COUNT
  void load()
}, { immediate: true })
watch(() => props.taskStatus, (status, previous) => {
  if (isActiveRun(previous) && !isActiveRun(status) && !loadFailed.value) {
    terminalPolls = TERMINAL_POLL_COUNT
    void load()
  }
})
watch(() => response.value?.status, (status) => {
  if (status === 'queued' || status === 'running') emit('activity')
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
        <div>
          <dt>本轮状态</dt>
          <dd>
            <ElTag
              class="ui-execution-status"
              :type="response.status === 'unavailable' ? 'warning' : 'info'"
              :data-execution-state="analysisState(response.status)"
              size="small"
            >{{ statusLabel(response.status) }}</ElTag>
          </dd>
        </div>
        <div v-if="response.model_name"><dt>本轮模型</dt><dd>{{ response.model_name }}<template v-if="response.model_version !== null"> (v{{ response.model_version }})</template></dd></div>
        <div v-if="response.started_at"><dt>生成开始</dt><dd>{{ timeLabel(response.started_at) }}</dd></div>
        <div v-if="response.finished_at"><dt>生成结束</dt><dd>{{ timeLabel(response.finished_at) }}</dd></div>
      </dl>
      <template v-if="report">
        <section class="inspection-analysis-saved" aria-label="已保存汇报摘要">
          <div class="inspection-analysis-saved-heading"><strong>{{ response.status === 'completed' ? '已保存汇报' : '上次成功汇报' }}</strong><span class="ui-text-muted">生成于 {{ timeLabel(report.generated_at) }}</span></div>
          <dl class="inspection-analysis-stats">
            <div><dt>分析主机</dt><dd>{{ report.host_count }} <span>台</span></dd></div>
            <div><dt>异常发现</dt><dd>{{ report.finding_count }} <span>条</span></dd></div>
            <div><dt>错误日志</dt><dd>{{ report.log_count }} <span>条</span></dd></div>
          </dl>
          <div class="inspection-analysis-provenance"><span>报告模型：{{ report.model_name }} (v{{ report.model_version }})</span><span>采集时间：{{ timeLabel(report.inspection_started_at) }} 至 {{ timeLabel(report.inspection_finished_at) }}</span></div>
        </section>
        <InspectionAnalysisGroup v-for="group in problemGroups" :key="`${report.generated_at}:${group.title}`" :group="group" :evidence="report.evidence" />
      </template>
    </template>
  </section>
</template>
