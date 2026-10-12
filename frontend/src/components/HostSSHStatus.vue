<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElTooltip } from 'element-plus'
import { getConnectionTest, listConnectionTests } from '@/api/ssh_connections'
import { showSystemError } from '@/components/feedback'
import type { ConnectionTest, Host } from '@/types/api'

const props = defineProps<{ host: Host; updatedRecord: ConnectionTest | null }>()
const POLL_INTERVAL_MS = 800
const latest = ref<ConnectionTest | null>(null)
const loading = ref(true)
const loadFailed = ref(false)
let requestId = 0
let timer: ReturnType<typeof setTimeout> | undefined

const appearance = computed(() => {
  if (loadFailed.value) return { tone: 'muted', symbol: '?', text: 'SSH 状态待刷新' }
  if (loading.value) return { tone: 'info', symbol: '…', text: '正在查询 SSH 状态' }
  switch (latest.value?.status) {
    case 'queued': return { tone: 'info', symbol: '…', text: 'SSH 连接测试排队中' }
    case 'running': return { tone: 'info', symbol: '…', text: 'SSH 连接测试中' }
    case 'succeeded': return { tone: 'success', symbol: '✓', text: '最近一次 SSH 连接测试通过' }
    case 'failed': return { tone: 'danger', symbol: '×', text: '最近一次 SSH 连接测试未通过' }
    case 'interrupted': return { tone: 'danger', symbol: '×', text: '最近一次 SSH 连接测试已中断' }
    case 'awaiting_trust': return { tone: 'warning', symbol: '!', text: 'SSH 待核对主机密钥' }
    case 'trusted': return { tone: 'warning', symbol: '!', text: 'SSH 主机密钥已信任，需重新测试' }
    default: return { tone: 'muted', symbol: '?', text: 'SSH 尚未测试' }
  }
})
const description = computed(() => {
  const time = latest.value?.created_at
  return time && !loading.value && !loadFailed.value
    ? `${appearance.value.text}（${new Date(time).toLocaleString('zh-CN')}）`
    : appearance.value.text
})

function invalidate() {
  clearTimeout(timer)
  return ++requestId
}

function isOlder(record: ConnectionTest) {
  const previous = latest.value
  if (!previous) return false
  if (record.created_at !== previous.created_at) return record.created_at < previous.created_at
  if (record.id !== previous.id) return record.id < previous.id
  // 并行查询的旧响应不能将已完成的测试恢复为排队或运行中。
  return previous.status !== 'queued' && previous.status !== 'running' &&
    (record.status === 'queued' || record.status === 'running')
}

function poll(record: ConnectionTest, current: number) {
  if (record.status !== 'queued' && record.status !== 'running') return
  timer = setTimeout(async () => {
    try {
      const result = await getConnectionTest(record.id)
      if (current !== requestId) return
      if (isOlder(result)) return
      latest.value = result
      poll(result, current)
    } catch {
      if (current !== requestId) return
      loadFailed.value = true
      showSystemError()
    }
  }, POLL_INTERVAL_MS)
}

async function load() {
  const current = invalidate()
  loading.value = true
  loadFailed.value = false
  try {
    const records = await listConnectionTests('host', props.host.id)
    if (current !== requestId) return
    const record = records[0]
    if (!record) latest.value = null
    else if (!isOlder(record)) latest.value = record
    if (latest.value) poll(latest.value, current)
  } catch {
    if (current !== requestId) return
    loadFailed.value = true
    showSystemError()
  } finally {
    if (current === requestId) loading.value = false
  }
}

watch(() => props.host, load, { immediate: true })
watch(() => props.updatedRecord, (record) => {
  if (!record || record.target_type !== 'host' || record.target_id !== props.host.id) return
  // 查看或信任旧记录时，不覆盖列表中更新的测试状态。
  if (isOlder(record)) return
  const current = invalidate()
  latest.value = record
  loading.value = false
  loadFailed.value = false
  poll(record, current)
})
onUnmounted(invalidate)
</script>

<template>
  <ElTooltip :content="description" placement="top">
    <span class="host-ssh-status" :class="`is-${appearance.tone}`" role="img" :aria-label="description" tabindex="0">
      <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
        <circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="1.5" />
        <path v-if="appearance.symbol === '✓'" d="M6 10l2.5 2.5L14 7" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
        <path v-else-if="appearance.symbol === '×'" d="M7 7l6 6M13 7l-6 6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
        <g v-else-if="appearance.symbol === '?'">
          <path d="M7.5 8a2.5 2.5 0 0 1 5 0c0 1.5-2.5 1.5-2.5 3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          <circle cx="10" cy="14.5" r="0.75" fill="currentColor" />
        </g>
        <text v-else x="10" y="10.5" text-anchor="middle" dominant-baseline="middle" fill="currentColor">{{ appearance.symbol }}</text>
      </svg>
    </span>
  </ElTooltip>
</template>

<style scoped>
.host-ssh-status { display: inline-flex; flex: 0 0 18px; width: 18px; height: 18px; vertical-align: middle; }
.host-ssh-status svg { width: 100%; height: 100%; }
.host-ssh-status text { font-size: 13px; font-weight: 600; }
.host-ssh-status.is-muted { color: var(--ui-text-muted); }
.host-ssh-status.is-info { color: var(--ui-info); }
.host-ssh-status.is-success { color: var(--ui-success); }
.host-ssh-status.is-danger { color: var(--ui-danger); }
.host-ssh-status.is-warning { color: var(--ui-warning); }
.host-ssh-status:focus-visible { outline: 2px solid var(--ui-primary); outline-offset: 2px; }
</style>
