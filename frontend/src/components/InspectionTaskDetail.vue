<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElOption, ElSelect, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { getInspectionReport } from '@/api/inspections'
import { showSystemError } from '@/components/feedback'
import { checkLabel, conclusionLabel, conclusionType, isActiveRun, runLabel, runType, timeLabel } from '@/components/inspectionDisplay'
import type { CheckResponse, TaskDetail } from '@/types/inspections'

const props = defineProps<{ task: TaskDetail }>()
const hostId = ref<string | null>(null)
const exporting = ref(false)
const selectedHost = computed(() => props.task.hosts.find((host) => host.id === hostId.value) ?? null)
let session = 0
watch(() => props.task.id, () => {
  session++
  hostId.value = props.task.hosts[0]?.id ?? null
  exporting.value = false
}, { immediate: true })
onUnmounted(() => { session++ })

function checkType(check: CheckResponse): 'info' | 'success' | 'warning' | 'danger' {
  if (check.status === 'failed' || check.status === 'interrupted') return 'danger'
  if (check.status === 'completed') return 'success'
  return 'info'
}

async function exportReport() {
  if (isActiveRun(props.task.status) || exporting.value) return
  const current = session
  exporting.value = true
  try {
    const report = await getInspectionReport(props.task.id)
    if (current !== session) return
    const url = URL.createObjectURL(new Blob([report.content], { type: 'text/plain;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = report.filename
    document.body.append(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch {
    if (current === session) showSystemError()
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
      <span>规则版本 {{ task.rule_version }}</span>
      <span>开始 {{ timeLabel(task.started_at) }}</span><span>结束 {{ timeLabel(task.finished_at) }}</span>
    </div>
    <details class="inspection-config-summary"><summary>本次巡检配置</summary>
      <p>命令时限 {{ task.config.command_timeout_seconds }} 秒 · 主机时限 {{ task.config.host_timeout_seconds }} 秒</p>
      <p>资源阈值（警告 / 严重）：CPU {{ task.config.thresholds.cpu_warning }} / {{ task.config.thresholds.cpu_critical }}%，内存 {{ task.config.thresholds.mem_warning }} / {{ task.config.thresholds.mem_critical }}%，磁盘 {{ task.config.thresholds.disk_warning }} / {{ task.config.thresholds.disk_critical }}%，Swap {{ task.config.thresholds.swap_warning }} / {{ task.config.thresholds.swap_critical }}%</p>
      <p>服务：{{ task.config.services.length ? task.config.services.map((service) => `${service.name}（${service.candidates.join('、')}，${service.required ? '必需' : '可选'}）`).join('；') : '无' }}</p>
    </details>
    <template v-if="task.hosts.length">
      <label class="inspection-host-choice">查看主机 <ElSelect v-model="hostId" aria-label="选择巡检主机"><ElOption v-for="host in task.hosts" :key="host.id" :label="`${host.host_name} · ${host.address}`" :value="host.id" /></ElSelect></label>
      <template v-if="selectedHost">
        <div class="inspection-host-meta"><strong>{{ selectedHost.host_name }}</strong><span>{{ selectedHost.group_name }} · {{ selectedHost.username }}@{{ selectedHost.address }}:{{ selectedHost.port }}</span><ElTag :type="runType(selectedHost.status)" size="small">{{ runLabel(selectedHost.status) }}</ElTag></div>
        <ElAlert v-if="selectedHost.failure_code === 'host_key_required'" type="warning" :closable="false" show-icon class="inspection-key-alert">
          <template #title>该主机因主机密钥尚未确认而未完成巡检。请到 <RouterLink to="/assets/hosts">资产管理</RouterLink> 对该主机进行连接测试并独立核对身份。</template>
        </ElAlert>
        <p v-else-if="selectedHost.failure_code" class="inspection-muted">该主机未完成巡检（{{ selectedHost.failure_code }}），无法判定风险。</p>
        <p v-if="!selectedHost.checks.length" class="inspection-muted">检查项尚未开始。</p>
        <section v-for="check in selectedHost.checks" :key="check.check_id" class="inspection-check-result" :aria-label="check.title">
          <div class="inspection-check-header"><h3>{{ check.title }}</h3><span>执行状态 <ElTag :type="checkType(check)" size="small">{{ checkLabel(check.status) }}</ElTag></span><span>检查结论 <ElTag :type="check.status === 'completed' ? conclusionType(check.conclusion) : 'info'" size="small">{{ check.status === 'completed' ? conclusionLabel(check.conclusion) : '无法判定' }}</ElTag></span></div>
          <p v-if="check.status === 'failed' || check.status === 'interrupted' || check.status === 'skipped'" class="inspection-muted">{{ check.status === 'skipped' ? '检查已跳过' : '检查未完成' }}{{ check.error_code ? `（${check.error_code}）` : '' }}，无法判定风险。</p>
          <p v-else-if="check.status === 'queued'" class="inspection-muted">检查尚未开始。</p>
          <p v-else-if="check.status === 'running'" class="inspection-muted">正在检查，结果尚未确定。</p>
          <p v-if="check.status !== 'completed' && check.payload.findings.length" class="inspection-muted">以下为已返回的风险线索，检查尚未完成，不能视为完整结论。</p>
          <p v-for="(finding, index) in check.payload.findings" :key="index" class="inspection-finding" :class="`inspection-finding-${finding.severity}`"><ElTag :type="finding.severity === 'critical' ? 'danger' : 'warning'" size="small">{{ finding.severity === 'critical' ? '严重' : '警告' }}</ElTag>{{ finding.message }}</p>
          <template v-if="check.status === 'completed'">
            <dl v-if="check.payload.metrics.length" class="inspection-metrics"><template v-for="(metric, index) in check.payload.metrics" :key="index"><dt>{{ metric.name }}</dt><dd>{{ metric.value ?? '未记录' }}{{ metric.value !== null && metric.unit ? ` ${metric.unit}` : '' }}</dd></template></dl>
            <div v-for="(table, index) in check.payload.tables" :key="index" class="inspection-result-table"><h4>{{ table.name }}</h4><div class="host-table-wrap"><ElTable :data="table.rows" class="host-table" :empty-text="'无数据'"><ElTableColumn v-for="(column, columnIndex) in table.columns" :key="columnIndex" :label="column" min-width="140"><template #default="{ row }">{{ row[columnIndex] ?? '' }}</template></ElTableColumn></ElTable></div></div>
            <p v-if="!check.payload.findings.length && !check.payload.metrics.length && !check.payload.tables.length" class="inspection-muted">无详细数据。</p>
          </template>
        </section>
      </template>
    </template>
    <p v-else class="inspection-muted">主机结果尚未生成。</p>
  </section>
</template>
