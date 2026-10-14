<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElDialog, ElLoading } from 'element-plus'
import { getConnectionTest, listConnectionTests, startConnectionTest } from '@/api/ssh_connections'
import { showSystemError } from '@/components/feedback'
import { ensureSSHIdentities } from '@/api/sshIdentity'
import { SSH_STATUS_UNAVAILABLE, sshTestDisplay } from '@/components/sshTestDisplay'
import TestStatus from '@/components/TestStatus.vue'
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
const focusedRecordId = ref<string | null>(null)
const loading = ref(false)
const loaded = ref(false)
const submitting = ref(false)
const trusting = ref(false)
const recordLoadFailed = ref(false)
const launchedId = ref<string | null>(null)
const confirmedId = ref<string | null>(null)
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
  focusedRecordId.value = null
  loading.value = false
  loaded.value = false
  submitting.value = false
  trusting.value = false
  recordLoadFailed.value = false
  launchedId.value = null
  confirmedId.value = null
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

function updateVisible(visible: boolean) {
  if (!visible && (submitting.value || trusting.value)) return
  emit('update:modelValue', visible)
}

async function checkIdentity(item: ConnectionTest, current: number) {
  if (item.id !== launchedId.value || item.status !== 'awaiting_trust' || trusting.value) return
  trusting.value = true
  try {
    await ensureSSHIdentities([{ target_type: item.target_type, target_id: item.target_id }], {
      isCurrent: () => current === session && props.modelValue && launchedId.value === item.id,
    })
    if (current === session && launchedId.value === item.id) confirmedId.value = item.id
  } catch (error) {
    if (current === session) showSystemError(error)
  } finally {
    if (current === session) trusting.value = false
  }
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
      else if (result.status === 'awaiting_trust') void checkIdentity(result, currentSession)
    } catch (error) {
      if (currentSession === session && currentPoll === pollId) {
        recordLoadFailed.value = true
        showSystemError(error)
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
  try {
    const result = await listConnectionTests(target.target_type, target.target_id)
    if (current !== session) return
    history.value = result
    if (result[0]) emit('record-updated', result[0])
    selectedId.value = result.some((item) => item.id === selectedId.value) ? selectedId.value : result[0]?.id ?? null
    loaded.value = true
    const item = selected.value
    if (item) poll(item)
  } catch (error) {
    if (current === session) showSystemError(error)
  } finally {
    if (current === session) loading.value = false
  }
}

function selectRecord(item: ConnectionTest) {
  if (submitting.value || trusting.value) return
  stopPolling()
  selectedId.value = item.id
  recordLoadFailed.value = false
  poll(item)
}

async function startTest() {
  const target = props.target
  if (!props.modelValue || !target || !loaded.value || loading.value || submitting.value || trusting.value || hasActiveTest.value) return
  const current = session
  submitting.value = true
  try {
    const item = await startConnectionTest({ target_type: target.target_type, target_id: target.target_id, version: target.version }, {
      isCurrent: () => current === session && props.modelValue,
    })
    if (current !== session) return
    stopPolling()
    updateRecord(item)
    selectedId.value = item.id
    launchedId.value = item.id
    confirmedId.value = null
    recordLoadFailed.value = false
    poll(item)
    if (item.status === 'awaiting_trust') void checkIdentity(item, current)
  } catch (error) {
    if (current === session) showSystemError(error)
  } finally {
    if (current === session) submitting.value = false
  }
}

function recordDisplay(item: ConnectionTest) {
  if (recordLoadFailed.value && selectedId.value === item.id) {
    return { status: 'unavailable' as const, label: SSH_STATUS_UNAVAILABLE, description: SSH_STATUS_UNAVAILABLE }
  }
  return sshTestDisplay(item.status)
}

function dateLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

</script>

<template>
  <ElDialog :model-value="modelValue" align-center :title="`SSH 连接测试：${target?.name ?? ''}`" width="min(720px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!submitting && !trusting" :show-close="!submitting && !trusting" @update:model-value="updateVisible" @closed="emit('closed')">
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
            <button v-for="item in history" :key="item.id" type="button" class="ssh-test-history-row" :class="{ selected: selectedId === item.id }" :aria-pressed="selectedId === item.id" :disabled="submitting || trusting" @click="selectRecord(item)" @focus="focusedRecordId = item.id" @blur="focusedRecordId = null">
               <span>{{ dateLabel(item.created_at) }}</span>
                <span class="ssh-test-status"><TestStatus :status="recordDisplay(item).status" :description="`${item.target_name}：${recordDisplay(item).description}`" :focusable="false" :tooltip-visible="focusedRecordId === item.id ? true : undefined" />{{ recordDisplay(item).label }}</span>
            </button>
          </div>
        </section>
        <section v-if="selected && !recordLoadFailed" class="ssh-test-result" aria-label="测试结果">
          <h2>测试结果 <span class="ssh-test-status"><TestStatus :status="recordDisplay(selected).status" :description="`${selected.target_name}：${recordDisplay(selected).description}`" />{{ recordDisplay(selected).label }}</span></h2>
          <dl class="ssh-test-details">
            <dt>目标</dt><dd>{{ selected.target_name }} · {{ selected.address }}:{{ selected.port }}</dd>
            <dt>登录用户</dt><dd>{{ selected.username }}</dd>
            <dt>开始时间</dt><dd>{{ selected.started_at ? dateLabel(selected.started_at) : '尚未开始' }}</dd>
            <dt>耗时</dt><dd>{{ selected.duration_ms !== null ? `${selected.duration_ms} ms` : (selected.status === 'running' ? '计时中' : '未记录') }}</dd>
          </dl>
        </section>
        <ElAlert v-if="selected && !recordLoadFailed && selected.status === 'awaiting_trust'" :title="confirmedId === selected.id ? '身份已确认，请重新开始测试。' : '测试因身份待确认而停止，请重新开始测试。'" type="warning" :closable="false" show-icon />
      </template>
    </div>
    <template #footer><ElButton :disabled="submitting || trusting" @click="updateVisible(false)">关闭</ElButton></template>
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
.ssh-test-status { display: inline-flex; align-items: center; gap: 8px; }
.ssh-test-muted { color: var(--ui-text-secondary); }
.ssh-test-result { border-top: 1px solid var(--ui-border); padding-top: 16px; }
.ssh-test-result h2 { display: flex; align-items: center; gap: 8px; }
.ssh-test-result .ssh-test-status { font-size: 13px; font-weight: 400; }
.ssh-test-details { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 8px 12px; margin: 0; }
.ssh-test-details dt { color: var(--ui-text-secondary); }
.ssh-test-details dd { margin: 0; overflow-wrap: anywhere; }
</style>
