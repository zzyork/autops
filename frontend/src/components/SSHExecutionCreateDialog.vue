<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { ElButton, ElDialog, ElInput, ElInputNumber, ElLoading, ElMessageBox, ElTable, ElTableColumn } from 'element-plus'
import { listHostsPage } from '@/api/assets'
import { createExecution } from '@/api/ssh_executions'
import { HttpError } from '@/api/http'
import { showRequestError } from '@/components/feedback'
import { useServerPagination } from '@/components/serverPagination'
import ListPagination from '@/components/ListPagination.vue'
import type { Host } from '@/types/api'
import type { ExecutionDetail, ExecutionInput } from '@/types/sshExecutions'

const emit = defineEmits<{ close: []; created: [detail: ExecutionDetail] }>()
const vLoading = ElLoading.directive
interface DraftStep { key: string; name: string; command: string; codes: string; timeout: number }
const hosts = useServerPagination(async (page, size) => {
  const value = await listHostsPage('', null, page, size)
  if (!Array.isArray(value.items) || !Number.isSafeInteger(value.total) || value.total < 0
    || !value.items.every((host) => Number.isSafeInteger(host.id) && host.id > 0 && Number.isSafeInteger(host.version)
      && host.version > 0 && typeof host.name === 'string' && typeof host.address === 'string')) throw new HttpError()
  return value
})
const selectedHost = ref<Host | null>(null)
const name = ref('')
const timeout = ref(900)
const steps = ref<DraftStep[]>([{ key: crypto.randomUUID(), name: '', command: '', codes: '0', timeout: 30 }])
const saving = ref(false)
const error = ref('')
const submitted = ref<ExecutionInput | null>(null)
let active = true
let submitController: AbortController | null = null

function selectHost(host: Host) { if (!submitted.value) selectedHost.value = host }
function addStep() {
  if (steps.value.length < 20) steps.value.push({ key: crypto.randomUUID(), name: '', command: '', codes: '0', timeout: 30 })
}
function move(index: number, direction: number) {
  const next = index + direction
  if (next < 0 || next >= steps.value.length) return
  const item = steps.value[index]
  if (!item) return
  steps.value.splice(index, 1)
  steps.value.splice(next, 0, item)
}
function buildInput(): ExecutionInput | null {
  if (!selectedHost.value) { error.value = '请选择一台主机。'; return null }
  if (!name.value.trim() || name.value.trim().length > 100) { error.value = '流程名称须填写且不超过 100 字符。'; return null }
  if (!Number.isSafeInteger(timeout.value) || timeout.value < 10 || timeout.value > 1800) { error.value = '流程时限须为 10–1800 秒。'; return null }
  if (!steps.value.length || steps.value.length > 20) { error.value = '须设置 1–20 个步骤。'; return null }
  const inputs: ExecutionInput['steps'] = []
  for (const [index, item] of steps.value.entries()) {
    if (!item.name.trim() || item.name.trim().length > 100 || !item.command.trim() || item.command.length > 8192 || item.command.includes('\0')
      || !Number.isSafeInteger(item.timeout) || item.timeout < 1 || item.timeout > 600) {
      error.value = `步骤 ${index + 1} 的名称、完整命令或时限无效。`
      return null
    }
    const parts = item.codes.split(',').map((part) => part.trim())
    const codes = parts.map(Number)
    if (parts.length < 1 || parts.length > 16 || parts.some((part) => !/^(0|[1-9]\d*)$/.test(part))
      || codes.some((code) => !Number.isSafeInteger(code) || code < 0 || code > 255) || new Set(codes).size !== codes.length) {
      error.value = `步骤 ${index + 1} 的预期退出码须为不重复的 0–255 整数（逗号分隔）。`
      return null
    }
    inputs.push({ name: item.name.trim(), command: item.command, success_exit_codes: codes, timeout_seconds: item.timeout })
  }
  return { id: crypto.randomUUID(), name: name.value.trim(), host: { id: selectedHost.value.id, version: selectedHost.value.version }, timeout_seconds: timeout.value, steps: inputs }
}
async function submit() {
  if (saving.value || hosts.loadFailed.value) return
  error.value = ''
  const body = submitted.value ?? buildInput()
  if (!body) return
  const target = selectedHost.value
  if (!target) { error.value = '请选择一台主机。'; return }
  saving.value = true
  try {
    await ElMessageBox.confirm(`目标：${target.name}（${target.address}）\n步骤：${body.steps.map((step, index) => `${index + 1}. ${step.name}`).join('、')}\n将按顺序在该主机执行完整命令；失败或结果未知时停止后续步骤。确认执行？`, '确认 SSH 执行', {
      confirmButtonText: '确认执行', cancelButtonText: '取消', type: 'warning', distinguishCancelAndClose: true,
    })
  } catch { saving.value = false; return }
  if (!active) return
  // 首次请求开始前固定正文与 UUID；响应未知时只能由用户显式重提相同正文。
  submitted.value = body
  const controller = new AbortController()
  submitController = controller
  try {
    const result = await createExecution(body, { signal: controller.signal, isCurrent: () => active })
    if (active) emit('created', result)
  } catch (cause) {
    if (active) showRequestError(cause)
  } finally {
    if (active) saving.value = false
    if (submitController === controller) submitController = null
  }
}
async function discard() {
  if (saving.value) return
  if (submitted.value) {
    try {
      await ElMessageBox.confirm('上次请求结果可能未知。放弃本次提交标识后，新的请求可能再次执行命令。确定放弃？', '放弃本次请求', {
        confirmButtonText: '放弃', cancelButtonText: '继续查看', type: 'warning',
      })
    } catch { return }
  }
  emit('close')
}
async function newIntent() {
  if (saving.value) return
  try {
    await ElMessageBox.confirm('上次请求结果可能未知。修改正文将创建新的执行请求，可能再次执行命令。确定修改？', '新建执行意图', {
      confirmButtonText: '继续修改', cancelButtonText: '取消', type: 'warning',
    })
    submitted.value = null
  } catch { /* 用户保持原请求。 */ }
}
onUnmounted(() => { active = false; submitController?.abort() })
</script>

<template>
  <ElDialog :model-value="true" align-center title="创建 SSH 执行" width="min(720px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving" :before-close="discard">
    <div class="asset-form ssh-execution-form">
      <label class="field"><span>流程名称 <em>*</em></span><ElInput v-model="name" maxlength="100" :disabled="!!submitted || saving" /></label>
      <div class="form-section-title">目标主机 <em>*</em></div>
      <p v-if="selectedHost" class="ssh-field-hint">已选：{{ selectedHost.name }}（{{ selectedHost.address }}）</p>
      <div class="ssh-execution-hosts">
        <ElTable v-if="!hosts.loadFailed.value" v-loading="hosts.loading.value" :data="hosts.items.value" row-key="id" :empty-text="hosts.loading.value ? '加载中' : '暂无主机'">
          <ElTableColumn label="选择" width="64"><template #default="{ row }"><input type="radio" name="execution-host" :aria-label="`选择主机 ${row.name}`" :checked="selectedHost?.id === row.id" :disabled="!!submitted || saving" @change="selectHost(row as Host)" /></template></ElTableColumn>
          <ElTableColumn prop="name" label="主机" min-width="170" /><ElTableColumn prop="address" label="地址" min-width="180" />
        </ElTable>
        <div v-else class="inspection-retry">主机列表未加载。<ElButton @click="hosts.refresh()">重试</ElButton></div>
      </div>
      <ListPagination v-model:page="hosts.page.value" v-model:page-size="hosts.pageSize.value" :total="hosts.total.value" :total-known="!hosts.loadFailed.value && !hosts.loading.value" :disabled="hosts.loading.value || hosts.loadFailed.value || saving" />
      <div class="field-grid"><label class="field"><span>流程时限（秒） <em>*</em></span><ElInputNumber v-model="timeout" :min="10" :max="1800" :disabled="!!submitted || saving" /></label></div>
      <div class="form-section-title ssh-execution-step-heading"><span>执行步骤 <em>*</em></span><ElButton :disabled="!!submitted || saving || steps.length >= 20" @click="addStep">添加步骤</ElButton></div>
      <div v-for="(item, index) in steps" :key="item.key" class="ssh-execution-step-editor">
        <div class="ssh-execution-step-heading"><strong>步骤 {{ index + 1 }}</strong><div class="ssh-execution-actions"><ElButton :disabled="!!submitted || saving || index === 0" @click="move(index, -1)">上移</ElButton><ElButton :disabled="!!submitted || saving || index === steps.length - 1" @click="move(index, 1)">下移</ElButton><ElButton type="danger" link :disabled="!!submitted || saving || steps.length === 1" @click="steps.splice(index, 1)">删除</ElButton></div></div>
        <div class="field-grid"><label class="field"><span>步骤名称 <em>*</em></span><ElInput v-model="item.name" maxlength="100" :disabled="!!submitted || saving" /></label><label class="field"><span>时限（秒） <em>*</em></span><ElInputNumber v-model="item.timeout" :min="1" :max="600" :disabled="!!submitted || saving" /></label></div>
        <label class="field"><span>完整命令 <em>*</em></span><ElInput v-model="item.command" type="textarea" :rows="3" :disabled="!!submitted || saving" /></label>
        <label class="field"><span>预期退出码（逗号分隔） <em>*</em></span><ElInput v-model="item.codes" :disabled="!!submitted || saving" /></label>
      </div>
      <p v-if="error" class="ssh-field-error" role="alert">{{ error }}</p>
      <div v-if="submitted" class="ssh-execution-pending">本次请求结果可能未知。重提相同正文和标识不会重复执行已受理的任务；若首次请求未受理，重提可能开始执行。<ElButton link type="primary" :disabled="saving" @click="newIntent">修改为新请求</ElButton></div>
    </div>
    <template #footer><ElButton :disabled="saving" @click="discard">关闭</ElButton><ElButton type="primary" :loading="saving" :disabled="hosts.loadFailed.value || hosts.loading.value" @click="submit">{{ submitted ? '重提同一请求' : '确认并执行' }}</ElButton></template>
  </ElDialog>
</template>
