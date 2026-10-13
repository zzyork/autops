<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElDialog, ElTable, ElTableColumn } from 'element-plus'
import { getConnectionTest, startConnectionTest } from '@/api/ssh_connections'
import { showSystemError } from '@/components/feedback'
import { SSH_STATUS_UNAVAILABLE, sshTestDisplay } from '@/components/sshTestDisplay'
import TestStatus from '@/components/TestStatus.vue'
import type { ConnectionTest, Host } from '@/types/api'

const props = defineProps<{ modelValue: boolean; hosts: Host[] }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'record-updated': [record: ConnectionTest]
  inspect: [host: Host]
}>()
interface Row { host: Host; record: ConnectionTest | null; state: 'pending' | 'submitting' | 'submitted' | 'unavailable' }
const rows = ref<Row[]>([])
const running = ref(false)
const stopped = ref(false)
const CONCURRENCY = 4
const POLL_INTERVAL_MS = 800
let generation = 0
const waits = new Map<ReturnType<typeof setTimeout>, () => void>()
const completed = computed(() => rows.value.filter((row) => row.record && !isActive(row.record)).length)
function isActive(record: ConnectionTest) { return record.status === 'queued' || record.status === 'running' }
function reset() {
  generation++
  for (const [timer, resolve] of waits) { clearTimeout(timer); resolve() }
  waits.clear()
  running.value = false
}
function pause() {
  return new Promise<void>((resolve) => {
    const timer = setTimeout(() => { waits.delete(timer); resolve() }, POLL_INTERVAL_MS)
    waits.set(timer, resolve)
  })
}
function update(row: Row, record: ConnectionTest) {
  row.record = record
  emit('record-updated', record)
}
async function start() {
  const current = generation
  running.value = true
  stopped.value = false
  let next = 0
  async function worker() {
    while (current === generation && !stopped.value) {
      const row = rows.value[next++]
      if (!row) return
      row.state = 'submitting'
      try {
        const record = await startConnectionTest({ target_type: 'host', target_id: row.host.id, version: row.host.version })
        if (current !== generation) return
        row.state = 'submitted'
        update(row, record)
        while (row.record && isActive(row.record) && current === generation) {
          await pause()
          if (current !== generation) return
          const latest = await getConnectionTest(record.id)
          if (current !== generation) return
          update(row, latest)
        }
      } catch {
        if (current !== generation) return
        row.state = 'unavailable'
        stopped.value = true
        showSystemError()
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker))
  if (current === generation) running.value = false
}
function rowDisplay(row: Row) {
  if (row.state === 'unavailable') return { status: 'unavailable' as const, label: row.record ? SSH_STATUS_UNAVAILABLE : '未能提交', description: row.record ? SSH_STATUS_UNAVAILABLE : 'SSH 连接测试未能提交' }
  if (!row.record) return stopped.value && row.state !== 'submitting'
    ? { status: 'untested' as const, label: '未提交', description: 'SSH 连接测试未提交' }
    : { status: 'pending' as const, label: row.state === 'submitting' ? '提交中' : '待提交', description: row.state === 'submitting' ? 'SSH 连接测试提交中' : 'SSH 连接测试待提交' }
  return sshTestDisplay(row.record.status)
}
watch(() => props.modelValue, (visible) => {
  reset()
  if (!visible) return
  rows.value = props.hosts.map((host) => ({ host: { ...host }, record: null, state: 'pending' }))
  void start()
})
onUnmounted(reset)
</script>

<template>
  <ElDialog :model-value="modelValue" title="批量测试连接" width="720px" align-center :close-on-click-modal="false" @update:model-value="emit('update:modelValue', $event)">
    <p class="batch-summary">共 {{ rows.length }} 台，已完成 {{ completed }} 台{{ running ? '，测试进行中' : '' }}。</p>
    <p v-if="stopped" class="batch-summary">后续提交已停止，可通过单台连接测试查看或重新测试。</p>
    <ElTable :data="rows" max-height="420">
      <ElTableColumn label="主机" min-width="160"><template #default="{ row }"><span :title="(row as Row).host.name">{{ (row as Row).host.name }}</span><div class="host-secondary">{{ (row as Row).host.address }}</div></template></ElTableColumn>
      <ElTableColumn label="状态" min-width="140"><template #default="{ row }"><span class="batch-test-status"><TestStatus :status="rowDisplay(row as Row).status" :description="`${(row as Row).host.name}：${rowDisplay(row as Row).description}`" />{{ rowDisplay(row as Row).label }}</span></template></ElTableColumn>
      <ElTableColumn label="操作" width="100"><template #default="{ row }"><ElButton link type="primary" :disabled="(row as Row).state === 'submitting' || ((row as Row).state === 'submitted' && !!((row as Row).record && isActive((row as Row).record!)))" @click="emit('inspect', (row as Row).host)">查看详情</ElButton></template></ElTableColumn>
    </ElTable>
    <p class="batch-summary">关闭弹窗会停止提交后续主机，已提交的测试继续执行。</p>
    <template #footer><ElButton @click="emit('update:modelValue', false)">关闭</ElButton></template>
  </ElDialog>
</template>

<style scoped>
.batch-summary { margin: 0 0 16px; color: var(--ui-text-secondary); }
.batch-test-status { display: inline-flex; align-items: center; gap: 8px; }
</style>
