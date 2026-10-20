<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCollapse, ElCollapseItem, ElOption, ElSelect, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { getInspectionReportArchive } from '@/api/inspections'
import { showSystemError } from '@/components/feedback'
import { ensureSSHIdentities, wasSSHOperationStarted } from '@/api/sshIdentity'
import { checkLabel, conclusionLabel, conclusionType, displayChecks, findingLabel, isActiveRun, metricLabel, runLabel, runType, summarizeChecks } from '@/components/inspectionDisplay'
import { timeLabel } from '@/components/timeDisplay'
import type { CheckResponse, TaskDetail } from '@/types/inspections'

const props = defineProps<{ task: TaskDetail }>()
const hostId = ref<string | null>(null)
const exporting = ref(false)
const selectedHost = computed(() => props.task.hosts.find((host) => host.id === hostId.value) ?? null)
const expandedChecks = ref<string[]>([])
const hostSummary = computed(() => summarizeChecks(selectedHost.value?.checks ?? []))
const visibleChecks = computed(() => displayChecks(selectedHost.value?.checks ?? []))
let session = 0
let observedRunning = false
const promptedHosts = new Set<string>()
const checkingIdentity = ref(false)
async function checkIdentity() {
  const host = selectedHost.value
  if (!host || checkingIdentity.value) return
  const current = session
  checkingIdentity.value = true
  try {
    await ensureSSHIdentities([{ target_type: 'host', target_id: host.host_id }], { isCurrent: () => current === session })
  } catch (error) { if (current === session) showSystemError(error) }
  finally { if (current === session) checkingIdentity.value = false }
}
watch(() => props.task.id, () => {
  session++
  observedRunning = false
  promptedHosts.clear()
  checkingIdentity.value = false
  hostId.value = props.task.hosts[0]?.id ?? null
  exporting.value = false
}, { immediate: true })
onUnmounted(() => { session++ })
watch(() => props.task, (task) => {
  if (wasSSHOperationStarted(task.id) || isActiveRun(task.status)) observedRunning = true
  if (!observedRunning) return
  for (const host of task.hosts) {
    if (host.failure_code !== 'host_key_required' || promptedHosts.has(host.id)) continue
    promptedHosts.add(host.id)
    const current = session
    void ensureSSHIdentities([{ target_type: 'host', target_id: host.host_id }], {
      isCurrent: () => current === session && props.task.id === task.id,
    }).catch((error: unknown) => {
      if (current === session) showSystemError(error)
    })
  }
}, { immediate: true })
watch(hostId, () => {
  expandedChecks.value = selectedHost.value?.checks.map((check) => check.check_id) ?? []
}, { immediate: true })

function checkType(check: CheckResponse): 'info' | 'success' | 'warning' | 'danger' {
  if (check.status === 'failed' || check.status === 'interrupted') return 'danger'
  if (check.status === 'completed') return 'success'
  return 'info'
}

async function exportReport() {
  if (isActiveRun(props.task.status) || exporting.value) return
  const current = session
  const taskId = props.task.id
  exporting.value = true
  try {
    const archive = await getInspectionReportArchive(taskId)
    if (current !== session) return
    const url = URL.createObjectURL(archive)
    const link = document.createElement('a')
    link.href = url
    link.download = `inspection-${taskId}.zip`
    document.body.append(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (error) {
    if (current === session) showSystemError(error)
  } finally {
    if (current === session) exporting.value = false
  }
}
</script>

<template>
  <section class="inspection-detail" aria-label="巡检任务详情">
    <div class="section-header"><h2>{{ task.name }}</h2><ElButton :disabled="isActiveRun(task.status)" :loading="exporting" @click="exportReport">导出报告</ElButton></div>
    <div class="inspection-detail-meta">
      <span>执行状态 <ElTag :type="runType(task.status)" size="small">{{ runLabel(task.status) }}</ElTag></span>
      <span>主机 {{ task.completed_hosts }} / {{ task.host_count }} 完成，{{ task.failed_hosts }} 失败</span>
      <span>开始 {{ timeLabel(task.started_at) }}</span><span>结束 {{ timeLabel(task.finished_at) }}</span>
    </div>
    <template v-if="task.hosts.length">
      <div class="inspection-host-choice"><span>查看主机</span><ElSelect v-model="hostId" aria-label="选择巡检主机"><ElOption v-for="host in task.hosts" :key="host.id" :label="`${host.host_name} · ${host.address}`" :value="host.id" /></ElSelect></div>
      <template v-if="selectedHost">
        <div class="inspection-host-meta"><h3 class="inspection-host-title">{{ selectedHost.address }}<span v-if="selectedHost.host_name !== selectedHost.address" class="inspection-host-name">{{ selectedHost.host_name }}</span></h3><span class="inspection-host-connection">{{ selectedHost.group_name }} · {{ selectedHost.username }}@{{ selectedHost.address }}:{{ selectedHost.port }}</span><ElTag :type="runType(selectedHost.status)" size="small">{{ runLabel(selectedHost.status) }}</ElTag></div>
        <div class="inspection-host-summary" aria-label="主机检查概览">
          <span>检查完成 <strong>{{ hostSummary.completed }} / {{ selectedHost.checks.length }}</strong></span>
          <ElTag :type="hostSummary.critical ? 'danger' : 'info'" size="small">重要 {{ hostSummary.critical }}</ElTag>
          <ElTag :type="hostSummary.warning ? 'warning' : 'info'" size="small">警告 {{ hostSummary.warning }}</ElTag>
          <span v-if="hostSummary.incomplete" class="ui-text-muted">{{ hostSummary.incomplete }} 项尚未完成，风险无法完整判定</span>
          <div v-if="visibleChecks.length" class="inspection-collapse-actions"><ElButton native-type="button" @click="expandedChecks = visibleChecks.map((check) => check.check_id)">全部展开</ElButton><ElButton native-type="button" @click="expandedChecks = []">全部收起</ElButton></div>
        </div>
        <ElAlert v-if="selectedHost.failure_code === 'host_key_required'" type="warning" :closable="false" show-icon class="inspection-key-alert">
          <template #title>该主机因 SSH 身份尚未确认而未完成巡检。确认身份后本次巡检不会自动重试，请重新发起巡检。</template>
        </ElAlert>
        <ElButton v-if="selectedHost.failure_code === 'host_key_required'" :loading="checkingIdentity" @click="checkIdentity">重新检查服务器身份</ElButton>
        <p v-else-if="selectedHost.failure_code" class="ui-text-muted">该主机未完成巡检，无法判定风险。</p>
        <p v-if="!selectedHost.checks.length" class="ui-text-muted">检查项尚未开始。</p>
        <ElCollapse v-if="visibleChecks.length" v-model="expandedChecks" expand-icon-position="left" class="inspection-checks ui-collapse">
        <ElCollapseItem v-for="check in visibleChecks" :key="`${selectedHost.id}-${check.check_id}`" :name="check.check_id">
          <template #title="{ isActive }"><div class="inspection-check-header"><h4>{{ check.title }}</h4><span class="ui-collapse-action">{{ isActive ? '收起' : '展开' }}</span><span>执行 <ElTag :type="checkType(check)" size="small">{{ checkLabel(check.status) }}</ElTag></span><span>结论 <ElTag :type="check.status === 'completed' ? conclusionType(check.conclusion) : 'info'" size="small">{{ check.status === 'completed' ? conclusionLabel(check.conclusion) : '无法判定' }}</ElTag></span><span v-if="check.payload.findings.length" class="ui-text-muted">{{ check.payload.findings.length }} 条风险发现</span></div></template>
          <template #icon="{ isActive }"><svg class="ui-collapse-arrow" :class="{ 'is-expanded': isActive }" viewBox="0 0 14 14" aria-hidden="true" focusable="false"><path d="m5 3 4 4-4 4" /></svg></template>
          <section class="inspection-check-result" :aria-label="check.title">
          <p v-if="check.status === 'failed' || check.status === 'interrupted' || check.status === 'skipped'" class="ui-text-muted">{{ check.status === 'skipped' ? '检查已跳过' : '检查未完成' }}，无法判定风险。</p>
          <p v-else-if="check.status === 'queued'" class="ui-text-muted">检查尚未开始。</p>
          <p v-else-if="check.status === 'running'" class="ui-text-muted">正在检查，结果尚未确定。</p>
          <p v-if="check.status !== 'completed' && check.payload.findings.length" class="ui-text-muted">以下为已返回的风险线索，检查尚未完成，不能视为完整结论。</p>
          <p v-for="(finding, index) in check.payload.findings" :key="index" class="inspection-finding" :class="`inspection-finding-${finding.severity}`"><ElTag :type="finding.severity === 'critical' ? 'danger' : 'warning'" size="small">{{ finding.severity === 'critical' ? '严重' : '警告' }}</ElTag>{{ findingLabel(finding.message) }}</p>
          <template v-if="check.status === 'completed'">
            <dl v-if="check.payload.metrics.length" class="inspection-metrics"><div v-for="(metric, index) in check.payload.metrics" :key="index" class="inspection-metric"><dt>{{ metric.name }}</dt><dd>{{ metricLabel(metric) }}</dd></div></dl>
            <div v-for="(table, index) in check.payload.tables" :key="index" class="inspection-result-table"><h5>{{ table.name }}</h5><div class="ui-table-wrap"><ElTable :data="table.rows" class="ui-table" :empty-text="'无数据'"><ElTableColumn v-for="(column, columnIndex) in table.columns" :key="columnIndex" :label="column" min-width="140"><template #default="{ row }">{{ row[columnIndex] ?? '' }}</template></ElTableColumn></ElTable></div></div>
            <p v-if="!check.payload.findings.length && !check.payload.metrics.length && !check.payload.tables.length" class="ui-text-muted">无详细数据。</p>
          </template>
          </section>
        </ElCollapseItem>
        </ElCollapse>
      </template>
    </template>
    <p v-else class="ui-text-muted">主机结果尚未生成。</p>
  </section>
</template>
