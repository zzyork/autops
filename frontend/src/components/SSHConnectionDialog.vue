<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCheckbox, ElDialog, ElLoading, ElMessageBox, ElTag } from 'element-plus'
import { getConnectionTest, listConnectionTests, startConnectionTest, trustConnectionTest } from '@/api/ssh_connections'
import { showSystemError } from '@/components/feedback'
import type { ConnectionTest, ConnectionTestTarget } from '@/types/api'

const props = defineProps<{ target: ConnectionTestTarget | null; modelValue: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'record-updated': [record: ConnectionTest]
  closed: []
}>()
const vLoading = ElLoading.directive
const POLL_INTERVAL_MS = 800
const HISTORY_LIMIT = 20
const history = ref<ConnectionTest[]>([])
const selectedId = ref<string | null>(null)
const loading = ref(false)
const loaded = ref(false)
const submitting = ref(false)
const trusting = ref(false)
const recordLoadFailed = ref(false)
const verified = ref(false)
const selected = computed(() => history.value.find((item) => item.id === selectedId.value) ?? null)
const hasActiveTest = computed(() => history.value.some(isActive))
let session = 0
let pollId = 0
let timer: ReturnType<typeof setTimeout> | undefined

function stopPolling() {
  clearTimeout(timer)
  pollId++
}

function reset() {
  session++
  stopPolling()
  history.value = []
  selectedId.value = null
  loading.value = false
  loaded.value = false
  submitting.value = false
  trusting.value = false
  recordLoadFailed.value = false
  verified.value = false
}

watch(() => [props.modelValue, props.target] as const, ([visible, target]) => {
  reset()
  if (visible && target) void loadHistory()
}, { immediate: true, flush: 'sync' })
onUnmounted(reset)

function updateRecord(item: ConnectionTest) {
  const index = history.value.findIndex((record) => record.id === item.id)
  if (index >= 0) history.value.splice(index, 1, item)
  else history.value = [item, ...history.value].slice(0, HISTORY_LIMIT)
  const latest = history.value[0]
  if (latest) emit('record-updated', latest)
}

function isActive(item: ConnectionTest) {
  return item.status === 'queued' || item.status === 'running'
}

function poll(item: ConnectionTest) {
  if (!isActive(item) || !props.modelValue || selectedId.value !== item.id) return
  const currentSession = session
  const currentPoll = ++pollId
  timer = setTimeout(async () => {
    try {
      const result = await getConnectionTest(item.id)
      if (currentSession !== session || currentPoll !== pollId) return
      updateRecord(result)
      if (isActive(result)) poll(result)
    } catch {
      if (currentSession === session && currentPoll === pollId) {
        recordLoadFailed.value = true
        showSystemError()
      }
    }
  }, POLL_INTERVAL_MS)
}

async function loadHistory() {
  const target = props.target
  if (!props.modelValue || !target || loading.value || submitting.value || trusting.value) return
  const current = session
  stopPolling()
  loading.value = true
  loaded.value = false
  recordLoadFailed.value = false
  verified.value = false
  try {
    const result = await listConnectionTests(target.target_type, target.target_id)
    if (current !== session) return
    history.value = result
    if (result[0]) emit('record-updated', result[0])
    selectedId.value = result.some((item) => item.id === selectedId.value) ? selectedId.value : result[0]?.id ?? null
    loaded.value = true
    const item = selected.value
    if (item) poll(item)
  } catch {
    if (current === session) showSystemError()
  } finally {
    if (current === session) loading.value = false
  }
}

function selectRecord(item: ConnectionTest) {
  if (submitting.value || trusting.value) return
  stopPolling()
  selectedId.value = item.id
  recordLoadFailed.value = false
  verified.value = false
  poll(item)
}

async function startTest() {
  const target = props.target
  if (!props.modelValue || !target || !loaded.value || loading.value || submitting.value || trusting.value || hasActiveTest.value) return
  const current = session
  submitting.value = true
  try {
    const item = await startConnectionTest({ target_type: target.target_type, target_id: target.target_id, version: target.version })
    if (current !== session) return
    stopPolling()
    updateRecord(item)
    selectedId.value = item.id
    recordLoadFailed.value = false
    verified.value = false
    poll(item)
  } catch {
    if (current === session) showSystemError()
  } finally {
    if (current === session) submitting.value = false
  }
}

async function trustKey() {
  const item = selected.value
  const challenge = item?.challenge
  if (!props.modelValue || !item || item.status !== 'awaiting_trust' || !challenge || !verified.value || trusting.value) return
  const current = session
  try {
    await ElMessageBox.confirm(
      `确认已独立核对 ${challenge.address}:${challenge.port} 的服务器身份？\n旧指纹：${challenge.previous_fingerprint ?? '无（首次信任）'}\n新指纹：${challenge.fingerprint}\n信任后将更新此主机密钥的信任记录，后续连接将按新指纹校验；本次测试不会自动重试。`,
      '信任此主机密钥',
      { confirmButtonText: '确认信任', cancelButtonText: '取消', type: 'warning', customClass: 'ssh-trust-confirm' },
    )
  } catch { return }
  if (current !== session || selectedId.value !== item.id || !verified.value) return
  trusting.value = true
  try {
    await trustConnectionTest(item.id)
    if (current !== session) return
    updateRecord({ ...item, status: 'trusted' })
    verified.value = false
    const result = await getConnectionTest(item.id)
    if (current === session) updateRecord(result)
  } catch {
    if (current === session) showSystemError()
  } finally {
    if (current === session) trusting.value = false
  }
}

function statusText(status: ConnectionTest['status']) {
  switch (status) {
    case 'queued': return '排队中'
    case 'running': return '测试中'
    case 'succeeded': return '测试通过'
    case 'failed': return '测试未通过'
    case 'awaiting_trust': return '待核对主机密钥'
    case 'interrupted': return '测试已中断'
    case 'trusted': return '已信任，需重新测试'
  }
}

function statusType(status: ConnectionTest['status']) {
  if (status === 'succeeded') return 'success'
  if (status === 'failed' || status === 'interrupted') return 'danger'
  if (status === 'awaiting_trust' || status === 'trusted') return 'warning'
  return 'info'
}

function dateLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

</script>

<template>
  <ElDialog :model-value="modelValue" align-center :title="`SSH 连接测试：${target?.name ?? ''}`" width="min(720px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!trusting" :show-close="!trusting" @update:model-value="emit('update:modelValue', $event)" @closed="emit('closed')">
    <div v-loading="loading" class="ssh-test-dialog">
      <div class="ssh-test-actions">
         <ElButton type="primary" :loading="submitting" :disabled="!loaded || loading || trusting || hasActiveTest" @click="startTest">开始测试</ElButton>
        <ElButton :disabled="loading || submitting || trusting" @click="loadHistory">刷新记录</ElButton>
      </div>
      <template v-if="loaded && !loading">
        <section aria-label="最近测试记录">
          <h2>最近测试记录</h2>
          <div v-if="!history.length" class="ssh-test-muted">暂无测试记录</div>
          <div v-else class="ssh-test-history">
            <button v-for="item in history" :key="item.id" type="button" class="ssh-test-history-row" :class="{ selected: selectedId === item.id }" :aria-pressed="selectedId === item.id" :disabled="submitting || trusting" @click="selectRecord(item)">
               <span>{{ dateLabel(item.created_at) }}</span><ElTag :type="recordLoadFailed && selectedId === item.id ? 'warning' : statusType(item.status)" size="small">{{ recordLoadFailed && selectedId === item.id ? '状态待刷新' : statusText(item.status) }}</ElTag>
            </button>
          </div>
        </section>
        <section v-if="selected && !recordLoadFailed" class="ssh-test-result" aria-label="测试结果">
          <h2>测试结果 <ElTag :type="statusType(selected.status)" size="small">{{ statusText(selected.status) }}</ElTag></h2>
          <dl class="ssh-test-details">
            <dt>目标</dt><dd>{{ selected.target_name }} · {{ selected.address }}:{{ selected.port }}</dd>
            <dt>登录用户</dt><dd>{{ selected.username }}{{ selected.via_jump_host ? '（目标主机）' : '' }}</dd>
            <dt>开始时间</dt><dd>{{ selected.started_at ? dateLabel(selected.started_at) : '尚未开始' }}</dd>
            <dt>耗时</dt><dd>{{ selected.duration_ms !== null ? `${selected.duration_ms} ms` : (selected.status === 'running' ? '计时中' : '未记录') }}</dd>
            <template v-if="selected.status === 'failed'"><dt>结果</dt><dd class="ssh-test-error">{{ selected.failure_message === null ? '该记录未保存具体错误，请重新测试' : selected.failure_message }}</dd></template>
          </dl>
        </section>
        <section v-if="selected && !recordLoadFailed && selected.challenge" class="ssh-test-challenge" aria-label="服务器身份核对">
            <h2>服务器身份核对</h2>
            <ElAlert v-if="selected.status === 'awaiting_trust'" :title="selected.challenge.previous_fingerprint === null ? '首次连接：请独立核对服务器身份指纹' : '主机密钥已变化：请独立核对服务器身份指纹'" type="warning" :closable="false" show-icon />
            <p>服务器身份：{{ selected.challenge.target_type === 'jump_host' ? '跳板机' : '目标主机' }} · {{ selected.challenge.address }}:{{ selected.challenge.port }}</p>
            <p>密钥类型：{{ selected.challenge.key_type }}</p>
            <p class="ssh-fingerprint">原指纹：{{ selected.challenge.previous_fingerprint ?? '无（首次信任）' }}</p>
            <p class="ssh-fingerprint">新指纹：{{ selected.challenge.fingerprint }}</p>
            <template v-if="selected.status === 'awaiting_trust'">
              <p>信任将{{ selected.challenge.previous_fingerprint === null ? '新增' : '替换' }}该主机密钥的信任记录，影响此地址后续 SSH 连接的身份校验；本次测试不会自动重试。</p>
              <ElCheckbox v-model="verified" :disabled="trusting">我已通过独立渠道核对上述服务器身份和新指纹</ElCheckbox>
              <div><ElButton type="primary" :loading="trusting" :disabled="!verified" @click="trustKey">信任此主机密钥</ElButton></div>
            </template>
        </section>
      </template>
    </div>
    <template #footer><ElButton :disabled="trusting" @click="emit('update:modelValue', false)">关闭</ElButton></template>
  </ElDialog>
</template>

<style scoped>
.ssh-test-dialog { display: grid; gap: 20px; min-height: 110px; }
.ssh-test-actions { display: flex; gap: 8px; }
.ssh-test-dialog h2 { margin-bottom: 8px; font-size: 14px; }
.ssh-test-history { max-height: 170px; overflow-y: auto; border: 1px solid var(--ui-border); }
.ssh-test-history-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; min-height: 38px; padding: 6px 12px; border: 0; border-bottom: 1px solid var(--ui-border); background: var(--ui-surface); color: var(--ui-text); cursor: pointer; text-align: left; }
.ssh-test-history-row:last-child { border-bottom: 0; }
.ssh-test-history-row:hover { background: var(--ui-row-hover); }
.ssh-test-history-row.selected { background: var(--ui-primary-soft); }
.ssh-test-history-row:focus-visible { outline: 2px solid var(--ui-primary) !important; outline-offset: -2px !important; }
.ssh-test-history-row:disabled { cursor: default; }
.ssh-test-muted { color: var(--ui-text-secondary); }
.ssh-test-result { border-top: 1px solid var(--ui-border); padding-top: 16px; }
.ssh-test-result h2 { display: flex; align-items: center; gap: 8px; }
.ssh-test-details { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 8px 12px; margin: 0; }
.ssh-test-details dt { color: var(--ui-text-secondary); }
.ssh-test-details dd { margin: 0; overflow-wrap: anywhere; }
.ssh-test-error { white-space: pre-wrap; }
.ssh-test-challenge { display: grid; gap: 8px; margin-top: 16px; padding: 12px; border: 1px solid var(--ui-border); background: var(--ui-warning-soft); overflow-wrap: anywhere; }
.ssh-test-challenge .el-checkbox { height: auto; white-space: normal; }
.ssh-test-challenge .el-checkbox :deep(.el-checkbox__label) { white-space: normal; color: var(--ui-text); }
</style>

<style>
.ssh-trust-confirm .el-message-box__message { white-space: pre-line; overflow-wrap: anywhere; }
</style>
