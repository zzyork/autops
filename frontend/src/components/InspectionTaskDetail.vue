<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCollapse, ElCollapseItem, ElOption, ElSelect, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { getInspectionReportArchive } from '@/api/inspections'
import { showSystemError } from '@/components/feedback'
import { ensureSSHIdentities, wasSSHOperationStarted } from '@/api/sshIdentity'
import { checkLabel, checkState, displayChecks, findingLabel, isActiveRun, metricLabel, runLabel, runState, summarizeChecks } from '@/components/inspectionDisplay'
import { timeLabel } from '@/components/timeDisplay'
import type { CheckStatus, TaskDetail } from '@/types/inspections'

const CHECK_STATUS_MESSAGES: Record<CheckStatus, string> = {
  queued: '检查尚未开始。',
  running: '正在检查，结果尚未确定。',
  completed: '检查已完成',
  failed: '检查未完成',
  skipped: '检查未完成（已跳过）',
  interrupted: '检查未完成（已中断）',
}

const props = defineProps<{ task: TaskDetail }>()
const hostId = ref<string | null>(null)
const exporting = ref(false)
const selectedHost = computed(() => props.task.hosts.find((host) => host.id === hostId.value) ?? null)
const expandedChecks = ref<string[]>([])
const hostSummary = computed(() => summarizeChecks(selectedHost.value?.checks ?? []))
const visibleChecks = computed(() => {
  const host = selectedHost.value
  const checks = displayChecks(host?.checks ?? [])
  return checks.map((check) => {
    let statusMessage = CHECK_STATUS_MESSAGES[check.status]
    if (check.status !== 'completed' && check.payload.findings.length) {
      statusMessage += ' 仅展示已返回的风险线索。'
    }
    // 身份阻断的风险限制集中在主机警告中，检查行保留执行状态。
    if (host?.failure_code === 'host_key_required') {
      statusMessage = checkLabel(check.status)
    }
    return {
      ...check,
      expandable: check.status === 'completed' || check.payload.findings.length > 0,
      statusMessage,
      executionState: checkState(check.status),
    }
  })
})
const expandableCheckIds = computed(() => visibleChecks.value.filter((check) => check.expandable).map((check) => check.check_id))
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
watch([() => props.task.id, hostId], () => {
  expandedChecks.value = []
}, { immediate: true })

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
      <span>
        执行状态
        <ElTag class="ui-execution-status" :data-execution-state="runState(task.status)" size="small">
          {{ runLabel(task.status) }}
        </ElTag>
      </span>
      <span>主机 {{ task.completed_hosts }} / {{ task.host_count }} 已结束</span>
      <span>开始 {{ timeLabel(task.started_at) }}</span><span>结束 {{ timeLabel(task.finished_at) }}</span>
    </div>
    <template v-if="task.hosts.length">
      <div class="inspection-host-choice">
        <span>查看主机</span>
        <ElSelect v-model="hostId" aria-label="选择巡检主机">
          <ElOption v-for="host in task.hosts" :key="host.id" :label="host.host_name === host.address ? host.address : `${host.host_name} · ${host.address}`" :value="host.id" />
        </ElSelect>
      </div>
      <template v-if="selectedHost">
        <div class="inspection-host-meta">
          <h3 class="inspection-host-title">
            {{ selectedHost.address }}
            <span v-if="selectedHost.host_name !== selectedHost.address" class="inspection-host-name">{{ selectedHost.host_name }}</span>
          </h3>
          <span class="inspection-host-connection">{{ selectedHost.group_name }}</span>
        </div>
        <div class="inspection-host-summary" aria-label="主机检查概览">
          <span>检查完成 <strong>{{ hostSummary.completed }} / {{ selectedHost.checks.length }}</strong></span>
          <ElTag v-if="hostSummary.critical > 0" type="danger" size="small">
            紧急 {{ hostSummary.critical }}
          </ElTag>
          <ElTag v-if="hostSummary.warning > 0" class="inspection-risk-tag" type="warning" size="small">
            警告 {{ hostSummary.warning }}
          </ElTag>
          <div v-if="expandableCheckIds.length" class="inspection-collapse-actions">
            <ElButton native-type="button" @click="expandedChecks = [...expandableCheckIds]">全部展开</ElButton>
            <ElButton native-type="button" @click="expandedChecks = []">全部收起</ElButton>
          </div>
        </div>
        <template v-if="selectedHost.failure_code === 'host_key_required'">
          <ElAlert type="warning" :closable="false" show-icon class="inspection-key-alert">
            <template #title>该主机因 SSH 身份尚未确认而未完成巡检，无法判定风险。确认身份后本次巡检不会自动重试，请重新发起巡检。</template>
          </ElAlert>
          <ElButton :loading="checkingIdentity" @click="checkIdentity">重新检查服务器身份</ElButton>
        </template>
        <p
          v-else-if="selectedHost.failure_code && !selectedHost.checks.length"
          class="ui-execution-status ui-execution-notice"
          :data-execution-state="runState(selectedHost.status)"
        >该主机未完成巡检，无法判定风险。</p>
        <p v-else-if="!selectedHost.checks.length" class="ui-execution-status ui-execution-notice" data-execution-state="not-started">
          检查项尚未开始。
        </p>
        <ElCollapse v-if="visibleChecks.length" v-model="expandedChecks" expand-icon-position="right" class="inspection-checks ui-collapse">
          <template v-for="check in visibleChecks" :key="`${selectedHost.id}-${check.check_id}`">
            <ElCollapseItem v-if="check.expandable" :name="check.check_id">
              <template #title>
                <div class="inspection-check-header">
                  <h4>{{ check.title }}</h4>
                  <span class="ui-text-muted ui-execution-status" :data-execution-state="check.executionState">
                    {{ check.statusMessage }}
                  </span>
                  <span v-if="check.payload.findings.length" class="ui-text-muted">发现 {{ check.payload.findings.length }} 个问题</span>
                </div>
              </template>
              <template #icon="{ isActive }">
                <svg class="ui-collapse-arrow" :class="{ 'is-expanded': isActive }" viewBox="0 0 14 14" aria-hidden="true" focusable="false"><path d="m5 3 4 4-4 4" /></svg>
              </template>
              <section class="inspection-check-result" :aria-label="check.title">
                <p v-for="(finding, index) in check.payload.findings" :key="index" class="inspection-finding" :class="`inspection-finding-${finding.severity}`">
                  <ElTag class="inspection-risk-tag" :type="finding.severity === 'critical' ? 'danger' : 'warning'" size="small">
                    {{ finding.severity === 'critical' ? '紧急' : '警告' }}
                  </ElTag>
                  {{ findingLabel(finding.message) }}
                </p>
                <template v-if="check.status === 'completed'">
                  <dl v-if="check.payload.metrics.length" class="inspection-metrics">
                    <div v-for="(metric, index) in check.payload.metrics" :key="index" class="inspection-metric">
                      <dt>{{ metric.name }}</dt>
                      <dd>{{ metricLabel(metric) }}</dd>
                    </div>
                  </dl>
                  <div v-for="(table, index) in check.payload.tables" :key="index" class="inspection-result-table">
                    <h5>{{ table.name }}</h5>
                    <div class="ui-table-wrap">
                      <ElTable :data="table.rows" class="ui-table" :empty-text="'无数据'">
                        <ElTableColumn v-for="(column, columnIndex) in table.columns" :key="columnIndex" :label="column" min-width="140">
                          <template #default="{ row }">{{ row[columnIndex] ?? '' }}</template>
                        </ElTableColumn>
                      </ElTable>
                    </div>
                  </div>
                  <p v-if="!check.payload.findings.length && !check.payload.metrics.length && !check.payload.tables.length" class="ui-text-muted">无详细数据。</p>
                </template>
              </section>
            </ElCollapseItem>
            <div v-else class="inspection-check-header inspection-check-static">
              <h4>{{ check.title }}</h4>
              <span class="ui-text-muted ui-execution-status" :data-execution-state="check.executionState">
                {{ check.statusMessage }}
              </span>
            </div>
          </template>
        </ElCollapse>
      </template>
    </template>
    <p v-else class="ui-text-muted">主机结果尚未生成。</p>
  </section>
</template>
