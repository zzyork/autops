<script setup lang="ts">
import { computed, shallowRef, useTemplateRef, watch } from 'vue'
import { ElButton, ElDialog, ElTag } from 'element-plus'
import type { InspectionProposal, OperationResultStatus, OperationStatus } from '@/types/ai'
import type { ExecutionState } from '@/types/executionStatus'

const props = defineProps<{ proposal: InspectionProposal; busy: boolean; open: boolean; visible: boolean }>()
const emit = defineEmits<{ open: []; close: []; closed: []; decide: [id: string, approve: boolean] }>()
const planContent = useTemplateRef<HTMLDivElement>('planContent')
const pendingDecision = shallowRef<boolean | null>(null)
const statusLabels: Record<OperationStatus | OperationResultStatus, string> = {
  queued: '等待执行', running: '正在执行', succeeded: '执行成功', failed: '执行失败',
  unknown: '结果未知', interrupted: '已中止', skipped: '未执行',
}
const errorLabels: Record<string, string> = {
  timeout: '执行或连接超时', connection: 'SSH 连接失败', authentication: 'SSH 身份认证失败',
  configuration: '连接配置不可用', host_key_required: '需要确认 SSH 服务器身份',
  asset_changed: '主机资产已变更', interrupted: '执行已中止', output_limit: '命令输出达到上限',
  exit_status: '命令以非 0 状态退出', internal: '内部错误', unknown: '执行结果未知',
  server_restarted: '应用服务重启，执行过程被中断', dispatch_failed: '任务分派失败', not_executed: '未执行',
}
const completeResults = computed(() => !!props.proposal.execution?.hosts.length
  && props.proposal.execution.hosts.every((host) => host.steps.length > 0))
const proposalLabel = computed(() => {
  if (props.proposal.status === 'pending') return '待确认'
  if (props.proposal.status === 'cancelled') return '已拒绝'
  const execution = props.proposal.execution
  if (!execution) return '等待执行状态'
  if (!completeResults.value && execution.status === 'succeeded') return '执行结果不完整，尚未确认'
  return statusLabels[execution.status]
})
const uncertain = computed(() => {
  const execution = props.proposal.execution
  return execution?.status === 'unknown' || execution?.status === 'interrupted'
    || execution?.hosts.some((host) => host.status === 'unknown' || host.steps.some((step) => step.status === 'unknown'))
})

function executionState(status: OperationStatus | OperationResultStatus, hasResults = true): ExecutionState {
  if (status === 'queued' || status === 'skipped') return 'not-started'
  if (status === 'running') return 'in-progress'
  if (status === 'succeeded') return hasResults ? 'completed' : 'incomplete'
  if (status === 'interrupted') return 'aborted'
  return 'incomplete'
}
function errorLabel(code: string): string {
  if (Object.prototype.hasOwnProperty.call(errorLabels, code)) return `${errorLabels[code]}（${code}）`
  return code
}
function close(): void {
  pendingDecision.value = null
  emit('close')
}
function decide(approve: boolean): void {
  if (props.busy || !props.visible || props.proposal.status !== 'pending') return
  pendingDecision.value = approve
  emit('close')
}
function finishClose(): void {
  const approve = pendingDecision.value
  pendingDecision.value = null
  emit('closed')
  // 先释放计划弹窗的焦点与滚动锁，再进入共用 SSH 身份确认流程。
  if (approve !== null && props.visible && !props.busy && props.proposal.status === 'pending') {
    emit('decide', props.proposal.id, approve)
  }
}
function focusPlan(): void {
  if (props.open && props.visible) planContent.value?.focus()
}
watch(() => props.visible, (value) => { if (!value) close() })
watch(() => props.proposal.status, (value) => { if (value !== 'pending') close() })
</script>

<template>
  <section class="ai-proposal" :aria-label="`运维计划 ${proposal.name}`">
    <div class="ai-card-heading">
      <strong>{{ proposal.name }}</strong>
      <ElTag class="ui-execution-status" :data-execution-state="proposal.execution ? executionState(proposal.execution.status, completeResults) : undefined" size="small">{{ proposalLabel }}</ElTag>
    </div>
    <p class="ui-text-muted">运维计划 · {{ proposal.hosts.length }} 台目标主机 · {{ proposal.commands.length }} 步命令</p>
    <div class="ai-proposal-actions">
      <ElButton :disabled="busy || !visible" @click="emit('open')">{{ proposal.status === 'pending' ? '查看并确认' : '查看运维计划' }}</ElButton>
    </div>
    <template v-if="proposal.status === 'confirmed'">
      <p v-if="uncertain" class="ui-execution-status ui-execution-notice" data-execution-state="incomplete" role="status">任务可能已经在远端执行，取消或断连不代表回滚。结果未知的命令不会自动重试，请先核对远端状态。</p>
      <p v-if="proposal.execution?.error_code" class="ui-execution-status ui-execution-notice" data-execution-state="incomplete" role="status">任务原因：{{ errorLabel(proposal.execution.error_code) }}</p>
      <p v-if="!proposal.execution || !proposal.execution.hosts.length" class="ui-text-muted" role="status">{{ proposal.execution?.status === 'running' ? '正在执行，等待主机与步骤结果…' : '暂无主机与步骤结果，执行结果尚未确认。' }}</p>
      <section v-for="host in proposal.execution?.hosts ?? []" :key="host.id" class="operation-host" :aria-label="`${host.name} 执行结果`">
        <div class="ai-card-heading">
          <strong>{{ host.name }} · {{ host.address }}</strong>
          <span class="ui-execution-status" :data-execution-state="executionState(host.status, host.steps.length > 0)">{{ host.status === 'succeeded' && !host.steps.length ? '步骤结果为空，尚未确认' : statusLabels[host.status] }}</span>
        </div>
        <p v-if="host.error_code" class="ui-text-muted">主机原因：{{ errorLabel(host.error_code) }}</p>
        <p v-if="!host.steps.length" class="ui-text-muted">暂无步骤结果{{ host.status === 'running' || host.status === 'queued' ? '，等待执行结果…' : '，无法核对命令执行情况。' }}</p>
        <section v-for="(step, index) in host.steps" :key="index" class="operation-step" :aria-label="`步骤 ${index + 1} ${step.name}`">
          <div class="ai-card-heading">
            <strong>{{ index + 1 }}. {{ step.name }}</strong>
            <span class="ui-execution-status" :data-execution-state="executionState(step.status)">{{ statusLabels[step.status] }}</span>
            <span class="ui-text-muted">退出码：{{ step.exit_status === null ? '尚未取得' : step.exit_status }}</span>
          </div>
          <p v-if="step.error_code" class="ui-text-muted">步骤原因：{{ errorLabel(step.error_code) }}</p>
          <p class="ui-text-muted">标准输出（stdout）</p>
          <pre v-if="step.stdout" class="operation-code" tabindex="0" :aria-label="`${host.name} 步骤 ${index + 1} 标准输出`" translate="no"><code>{{ step.stdout }}</code></pre>
          <p v-else class="ui-text-muted">{{ step.status === 'queued' || step.status === 'running' ? '等待输出…' : '无标准输出' }}</p>
          <p class="ui-text-muted">标准错误（stderr）</p>
          <pre v-if="step.stderr" class="operation-code" tabindex="0" :aria-label="`${host.name} 步骤 ${index + 1} 标准错误`" translate="no"><code>{{ step.stderr }}</code></pre>
          <p v-else class="ui-text-muted">{{ step.status === 'queued' || step.status === 'running' ? '等待输出…' : '无标准错误输出' }}</p>
        </section>
      </section>
    </template>
  </section>
  <ElDialog
    :model-value="open && visible"
    :title="proposal.status === 'pending' ? '确认运维计划' : '运维计划'"
    width="min(var(--ui-dialog-width), calc(100vw - 32px))"
    align-center append-to-body :close-on-click-modal="false"
    @update:model-value="!$event && close()"
    @close="emit('close')"
    @opened="focusPlan"
    @closed="finishClose"
  >
    <div ref="planContent" class="operation-plan" tabindex="0" aria-label="完整运维计划">
      <strong>{{ proposal.name }}</strong>
      <p>以下命令将在各目标主机上按步骤依次执行；任一步骤非 0 退出或失败，立即停止后续步骤和后续目标主机。</p>
      <p>本次确认仅执行此处展示的当前命令。取消、中止或连接断开后，远端可能已执行，结果可能未知，不代表已回滚；不会自动重试。</p>
      <p>关闭此窗口仅收起计划，不会拒绝或执行任务。</p>
      <strong>全部目标主机（{{ proposal.hosts.length }}）</strong>
      <ol class="operation-targets">
        <li v-for="host in proposal.hosts" :key="host.id">{{ host.name }} · {{ host.address }} <span class="ui-text-muted">（ID {{ host.id }} / 版本 {{ host.version }}）</span></li>
      </ol>
      <p v-if="!proposal.hosts.length" class="ui-text-muted">暂无目标主机，无法确认执行。</p>
      <strong>全部命令（{{ proposal.commands.length }} 步）</strong>
      <section v-for="(command, index) in proposal.commands" :key="index" class="operation-step">
        <div class="ai-card-heading"><strong>{{ index + 1 }}. {{ command.name }}</strong><span class="ui-text-muted">时限 {{ command.timeout_seconds }} 秒</span></div>
        <pre class="operation-code" tabindex="0" :aria-label="`步骤 ${index + 1} 完整命令`" translate="no"><code>{{ command.command }}</code></pre>
      </section>
      <p v-if="!proposal.commands.length" class="ui-text-muted">暂无命令，无法确认执行。</p>
    </div>
    <template #footer>
      <template v-if="proposal.status === 'pending'">
        <ElButton :disabled="busy" @click="decide(false)">拒绝</ElButton>
        <ElButton type="primary" :disabled="busy || !proposal.hosts.length || !proposal.commands.length" @click="decide(true)">确认并执行</ElButton>
      </template>
      <ElButton v-else @click="close">关闭</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.operation-plan, .operation-host, .operation-step {
  min-width: 0;
  display: grid;
  gap: var(--ui-space-2);
  overflow-wrap: anywhere;
}
.operation-plan { gap: var(--ui-space-3); }
.operation-plan p, .operation-host p, .operation-step p { margin: 0; }
.operation-host, .operation-step {
  border-top: 1px solid var(--ui-border);
  padding-top: var(--ui-space-3);
}
.operation-step .ai-card-heading strong { font-size: var(--ui-font-size-base); }
.operation-targets { margin: 0; padding-left: var(--ui-space-6); }
.operation-targets li + li { margin-top: var(--ui-space-2); }
.operation-code {
  min-width: 0;
  max-width: 100%;
  max-height: 320px;
  overflow: auto;
  overscroll-behavior: contain;
  margin: 0;
  padding: var(--ui-space-3);
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-control-radius);
  background: var(--ui-surface-muted);
  color: var(--ui-text);
  font-family: var(--ui-font-mono);
  font-size: var(--ui-font-size-code);
  line-height: var(--ui-line-height-code);
  white-space: pre;
  overflow-wrap: normal;
  tab-size: 4;
}
.operation-code code { font: inherit; }
.operation-plan:focus-visible, .operation-code:focus-visible {
  outline: 2px solid var(--ui-primary);
  outline-offset: -2px;
}
</style>
