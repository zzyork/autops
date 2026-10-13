<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { getConnectionTest, listConnectionTests } from '@/api/ssh_connections'
import { showSystemError } from '@/components/feedback'
import { SSH_STATUS_UNAVAILABLE, sshTestDisplay } from '@/components/sshTestDisplay'
import TestStatus from '@/components/TestStatus.vue'
import type { ConnectionTest, Host } from '@/types/api'

const props = defineProps<{ host: Host; updatedRecord: ConnectionTest | null }>()
const POLL_INTERVAL_MS = 800
const latest = ref<ConnectionTest | null>(null)
const loading = ref(true)
const loadFailed = ref(false)
let requestId = 0
let timer: ReturnType<typeof setTimeout> | undefined

const appearance = computed(() => {
  if (loadFailed.value) return { status: 'unavailable' as const, description: SSH_STATUS_UNAVAILABLE }
  if (loading.value) return { status: 'pending' as const, description: '正在查询 SSH 状态' }
  return latest.value ? sshTestDisplay(latest.value.status) : { status: 'untested' as const, description: 'SSH 尚未测试' }
})
const description = computed(() => {
  const time = latest.value?.created_at
  return time && !loading.value && !loadFailed.value
    ? `${appearance.value.description}（${new Date(time).toLocaleString('zh-CN')}）`
    : appearance.value.description
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
  <TestStatus :status="appearance.status" :description="description" />
</template>
