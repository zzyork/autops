<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElCollapse, ElCollapseItem, ElTag } from 'element-plus'
import { generateInspectionAnalysis, getInspectionAnalysis } from '@/api/inspections'
import { showSystemError } from '@/components/feedback'
import { isActiveRun, runLabel, timeLabel } from '@/components/inspectionDisplay'
import type { AnalysisEvidence, AnalysisIssue, AnalysisReport, AnalysisResponse, AnalysisSeverity, RunStatus } from '@/types/inspections'

const props = defineProps<{ taskId: string; taskStatus: RunStatus }>()
const POLL_INTERVAL_MS = 2000
const TERMINAL_POLL_COUNT = 5
const response = ref<AnalysisResponse | null>(null)
const loaded = ref(false)
const loading = ref(false)
const generating = ref(false)
const loadFailed = ref(false)
const expandedEvidence = ref<string[]>([])
let terminalPolls = 0
let request = 0
let session = 0
let active = true
let timer: ReturnType<typeof setTimeout> | undefined

const report = computed(() => response.value?.report ?? null)
const logEvidenceIds = computed(() => new Set(report.value?.evidence.filter((item) => item.kind === 'log').map((item) => item.id) ?? []))
const logIssues = computed(() => report.value?.issues.filter((issue) => issue.evidence_ids.some((id) => logEvidenceIds.value.has(id))) ?? [])
const otherIssues = computed(() => report.value?.issues.filter((issue) => !issue.evidence_ids.some((id) => logEvidenceIds.value.has(id))) ?? [])
const criticalIssues = computed(() => otherIssues.value.filter((issue) => issue.severity === 'critical'))
const warningIssues = computed(() => otherIssues.value.filter((issue) => issue.severity === 'warning'))
const infoIssues = computed(() => otherIssues.value.filter((issue) => issue.severity === 'info'))

function statusLabel(status: AnalysisResponse['status']): string {
  return { not_generated: '未生成', unavailable: '不可用', queued: '排队中', running: '生成中', completed: '已完成', failed: '生成失败', interrupted: '已中断' }[status]
}
function statusType(status: AnalysisResponse['status']): 'info' | 'success' | 'warning' | 'danger' {
  if (status === 'completed') return 'success'
  if (status === 'failed' || status === 'interrupted') return 'danger'
  if (status === 'unavailable') return 'warning'
  return 'info'
}
function severityLabel(severity: AnalysisSeverity): string {
  return { critical: '严重', warning: '警告', info: '信息' }[severity]
}
function severityType(severity: AnalysisSeverity): 'danger' | 'warning' | 'info' {
  if (severity === 'critical') return 'danger'
  return severity
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
    `[${severityLabel(issue.severity)}] ${issue.title}`,
    `分析：${issue.analysis}`,
    `建议：${issue.recommendation}`,
    `证据：${issue.evidence_ids.join('、') || '无'}`,
    '',
  ])
  const content = [
    '巡检 AI 汇报', `任务：${value.task_name}（${runLabel(value.task_status)}）`,
    `采集开始：${timeLabel(value.inspection_started_at)}；结束：${timeLabel(value.inspection_finished_at)}`,
    `生成时间：${timeLabel(value.generated_at)}`, `模型：${value.model_name} (v${value.model_version})`,
    `范围：${value.host_count} 台主机，${value.finding_count} 条发现，${value.log_count} 条日志，${value.incomplete_count} 项未完成，${value.unassessed_count} 项不适用或结论未知`,
    '', '总体分析', value.summary, '', '严重问题', ...issueLines(criticalIssues.value),
    '警告问题', ...issueLines(warningIssues.value), '日志问题', ...issueLines(logIssues.value),
    '其他问题', ...issueLines(infoIssues.value), '证据',
    ...value.evidence.flatMap((item) => [
      `[${item.id}] ${severityLabel(item.severity)} / ${kindLabel(item.kind)} / ${item.host_name} (${item.address})`,
      `${item.check_title} / ${item.source}`, item.content, '',
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
  expandedEvidence.value = []
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
    <div class="section-header">
      <h2>AI 汇报</h2>
      <div class="inspection-analysis-actions">
        <ElButton :loading="loading" :disabled="generating" @click="refresh">刷新</ElButton>
        <ElButton v-if="loaded && report" @click="exportText">导出汇报</ElButton>
        <ElButton type="primary" :loading="generating" :disabled="!loaded || !response?.can_generate || isActiveRun(taskStatus) || response?.status === 'queued' || response?.status === 'running' || loading" @click="generate">{{ report ? '重新生成' : '生成 AI 汇报' }}</ElButton>
      </div>
    </div>
    <p v-if="loadFailed" class="inspection-muted">汇报未加载，请刷新重试。</p>
    <p v-else-if="!loaded" class="inspection-muted">正在读取汇报状态…</p>
    <template v-else-if="response">
      <div class="inspection-analysis-meta">
        <span>本轮状态 <ElTag :type="statusType(response.status)" size="small">{{ statusLabel(response.status) }}</ElTag></span>
        <span v-if="response.model_name">本轮模型 {{ response.model_name }}<template v-if="response.model_version !== null"> (v{{ response.model_version }})</template></span>
        <span v-if="response.started_at">开始 {{ timeLabel(response.started_at) }}</span>
        <span v-if="response.finished_at">结束 {{ timeLabel(response.finished_at) }}</span>
      </div>
      <p v-if="response.status === 'unavailable'" class="inspection-muted">{{ response.can_generate ? '上次生成时主模型不可用，现在可以重新生成。' : '主模型未配置或未通过测试，暂不可生成汇报。' }}</p>
      <p v-else-if="response.status === 'not_generated' && isActiveRun(taskStatus)" class="inspection-muted">巡检进行中，结束后将检查自动生成条件。</p>
      <p v-else-if="response.status === 'not_generated'" class="inspection-muted">尚无 AI 汇报。</p>
      <p v-else-if="response.status === 'queued' || response.status === 'running'" class="inspection-muted">正在生成本轮汇报。</p>
      <p v-else-if="response.status === 'failed' || response.status === 'interrupted'" class="inspection-muted">本轮汇报{{ statusLabel(response.status) }}。已有汇报如有显示，仍为上次成功生成的版本。</p>
      <p v-if="!response.can_generate && !isActiveRun(taskStatus) && response.status !== 'queued' && response.status !== 'running' && response.status !== 'unavailable'" class="inspection-muted">当前无法发起生成，请检查主模型及生成服务状态。</p>
      <template v-if="report">
        <div class="inspection-analysis-meta inspection-analysis-saved">
          <strong>{{ response.status === 'completed' ? '已保存汇报' : '上次成功汇报' }}</strong><span>生成 {{ timeLabel(report.generated_at) }}</span><span>模型 {{ report.model_name }} (v{{ report.model_version }})</span>
          <span>{{ report.host_count }} 台主机 · {{ report.finding_count }} 条发现 · {{ report.log_count }} 条日志 · {{ report.incomplete_count }} 项未完成</span>
          <span>采集开始 {{ timeLabel(report.inspection_started_at) }} · 结束 {{ timeLabel(report.inspection_finished_at) }}</span>
        </div>
        <section v-if="report.incomplete_count" class="inspection-analysis-section">
          <h3>未完成检查</h3>
          <p>本次有 {{ report.incomplete_count }} 项检查未完成，相关风险无法完整判定。</p>
          <p v-for="item in report.evidence.filter((evidence) => evidence.incomplete && evidence.kind === 'check')" :key="item.id" class="inspection-muted">{{ item.id }} · {{ item.host_name }} · {{ item.check_title }}：检查未完成，无法判定。</p>
        </section>
        <section v-if="report.unassessed_count" class="inspection-analysis-section">
          <h3>判定范围限制</h3>
          <p>本次有 {{ report.unassessed_count }} 项检查不适用或结论未知，不能作为健康依据。</p>
          <p v-for="item in report.evidence.filter((evidence) => evidence.limited)" :key="item.id" class="inspection-muted">{{ item.id }} · {{ item.host_name }} · {{ item.check_title }}：不适用或结论未知。</p>
        </section>
        <section class="inspection-analysis-section"><h3>总体分析</h3><p>{{ report.summary }}</p></section>
        <p v-if="!report.issues.length" class="inspection-muted">暂无报告问题。</p>
        <section v-for="group in [
          { label: '严重问题', issues: criticalIssues },
          { label: '警告问题', issues: warningIssues },
          { label: '日志问题', issues: logIssues },
          { label: '其他问题', issues: infoIssues },
        ]" v-show="group.issues.length" :key="group.label" class="inspection-analysis-section">
          <h3>{{ group.label }} ({{ group.issues.length }})</h3>
          <div v-for="(issue, index) in group.issues" :key="index" class="inspection-analysis-issue">
            <div class="inspection-analysis-issue-title"><ElTag :type="severityType(issue.severity)" size="small">{{ severityLabel(issue.severity) }}</ElTag><strong>{{ issue.title }}</strong></div>
            <p>{{ issue.analysis }}</p><p><strong>建议：</strong>{{ issue.recommendation }}</p>
            <p v-if="issue.evidence_ids.length" class="inspection-muted">证据编号：{{ issue.evidence_ids.join('、') }}</p>
          </div>
        </section>
        <ElCollapse v-if="report.evidence.length" v-model="expandedEvidence" class="inspection-checks inspection-analysis-evidence">
          <ElCollapseItem name="evidence">
            <template #title><h3>证据 ({{ report.evidence.length }})</h3></template>
            <div v-for="item in report.evidence" :key="item.id" class="inspection-analysis-evidence-item">
              <div class="inspection-analysis-issue-title"><ElTag :type="severityType(item.severity)" size="small">{{ severityLabel(item.severity) }}</ElTag><strong>{{ item.id }} · {{ item.host_name }} ({{ item.address }})</strong></div>
              <p class="inspection-muted">{{ item.check_title }} · {{ item.source }} · {{ kindLabel(item.kind) }}</p>
              <p>{{ item.content }}</p>
            </div>
          </ElCollapseItem>
        </ElCollapse>
      </template>
    </template>
  </section>
</template>

<style scoped>
.inspection-analysis { display: grid; gap: 12px; min-width: 0; padding-top: 16px; border-top: 1px solid var(--ui-border); }
.inspection-analysis-actions, .inspection-analysis-meta, .inspection-analysis-issue-title { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; min-width: 0; }
.inspection-analysis-meta { color: var(--ui-text-secondary); }
.inspection-analysis-saved { padding-top: 12px; border-top: 1px solid var(--ui-border); }
.inspection-analysis-section { display: grid; gap: 8px; min-width: 0; }
.inspection-analysis-section h3, .inspection-analysis-evidence h3 { margin: 0; font-size: 14px; }
.inspection-analysis-issue { display: grid; gap: 8px; padding: 8px 0 8px 12px; border-left: 2px solid var(--ui-border); min-width: 0; }
.inspection-analysis-issue-title strong { min-width: 0; }
.inspection-analysis-evidence-item { padding: 12px 16px; border-bottom: 1px solid var(--ui-border); }
.inspection-analysis :is(p, strong, span, h3) { overflow-wrap: anywhere; }
.inspection-analysis p { margin: 0; white-space: pre-wrap; }
.inspection-analysis-evidence-item p { margin-top: 8px; }
</style>
