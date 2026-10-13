<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElCheckbox, ElDialog, ElTable, ElTableColumn } from 'element-plus'
import { getConnectionTest, startConnectionTest } from '@/api/ssh_connections'
import { getJumpHost } from '@/api/jump_hosts'
import { showSystemError } from '@/components/feedback'
import { SSH_STATUS_UNAVAILABLE, sshTestDisplay } from '@/components/sshTestDisplay'
import TestStatus from '@/components/TestStatus.vue'
import type { ConnectionTest, ConnectionTestChallenge, Host, JumpHost } from '@/types/api'

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
const started = ref(false)
const confirmed = ref(false)
const jumpHosts = ref<JumpHost[]>([])
const loadingScope = ref(false)
const scopeLoaded = ref(false)
const CONCURRENCY = 4
const POLL_INTERVAL_MS = 800
let generation = 0
const waits = new Map<ReturnType<typeof setTimeout>, () => void>()
const completed = computed(() => rows.value.filter((row) => row.record && !isActive(row.record)).length)
const newTrustCount = computed(() => rows.value.reduce((count, row) => count + (row.record ? row.record.auto_trusted_keys.length : 0), 0))
const jumpHostCount = computed(() => new Set(rows.value.map((row) => row.host.jump_host_id).filter((id) => id !== null)).size)
const pendingIdentities = computed(() => {
  const identities = new Map<string, ConnectionTestChallenge>()
  for (const row of rows.value) {
    const challenge = row.record?.status === 'awaiting_trust' ? row.record.challenge : null
    if (challenge) identities.set(`${challenge.target_type}:${challenge.target_id}:${challenge.address}:${challenge.port}:${challenge.fingerprint}`, challenge)
  }
  return [...identities.values()]
})
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
  if (started.value || !scopeLoaded.value || !rows.value.length || !confirmed.value) return
  const current = generation
  started.value = true
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
async function loadScope() {
  if (loadingScope.value || started.value) return
  const current = generation
  loadingScope.value = true
  scopeLoaded.value = false
  confirmed.value = false
  const ids = [...new Set(rows.value.flatMap((row) => row.host.jump_host_id === null ? [] : [row.host.jump_host_id]))]
  try {
    const result = await Promise.all(ids.map(getJumpHost))
    if (current !== generation) return
    jumpHosts.value = result
    scopeLoaded.value = true
  } catch {
    if (current === generation) showSystemError()
  } finally {
    if (current === generation) loadingScope.value = false
  }
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
  started.value = false
  stopped.value = false
  confirmed.value = false
  jumpHosts.value = []
  loadingScope.value = false
  scopeLoaded.value = false
  void loadScope()
})
onUnmounted(reset)
</script>

<template>
  <ElDialog :model-value="modelValue" title="批量测试连接" width="720px" align-center :close-on-click-modal="false" @update:model-value="emit('update:modelValue', $event)">
    <div class="batch-policy">
      <p class="batch-summary">本次范围：下列 {{ rows.length }} 台主机及其关联的 {{ jumpHostCount }} 台跳板机。</p>
      <p v-if="loadingScope" class="batch-summary">正在读取跳板机范围…</p>
      <div v-else-if="scopeLoaded && jumpHosts.length" class="batch-jump-hosts" aria-label="本次关联跳板机">
        <p v-for="jump in jumpHosts" :key="jump.id">跳板机：{{ jump.name }} · {{ jump.address }}:{{ jump.port }}</p>
      </div>
      <ElButton v-else-if="!scopeLoaded" @click="loadScope">重新读取范围</ElButton>
      <p class="batch-warning">首次连接自动保存服务器公钥并继续测试，已有密钥变化仍会拦截。首次信任无法辨别服务器是否被冒充，请仅在可信网络使用。</p>
      <ElCheckbox v-model="confirmed" :disabled="started || !scopeLoaded">我确认对上述范围启用首次自动信任，接受首次连接的身份风险</ElCheckbox>
      <ElButton v-if="!started" type="primary" :disabled="!scopeLoaded || !rows.length || !confirmed" @click="start">开始测试</ElButton>
    </div>
    <p class="batch-summary">共 {{ rows.length }} 台，已完成 {{ completed }} 台{{ running ? '，测试进行中' : '' }}。</p>
    <p v-if="started" class="batch-summary">本次新增信任 {{ newTrustCount }} 个服务器身份（含跳板机）；信任记录不代表连接测试成功。</p>
    <p v-if="stopped" class="batch-summary">后续提交已停止，可通过单台连接测试查看或重新测试。</p>
    <ElTable :data="rows" max-height="420">
      <ElTableColumn label="主机" min-width="160"><template #default="{ row }"><span :title="(row as Row).host.name">{{ (row as Row).host.name }}</span><div class="host-secondary">{{ (row as Row).host.vip || (row as Row).host.address }}:{{ (row as Row).host.port }}</div></template></ElTableColumn>
      <ElTableColumn label="状态" min-width="140"><template #default="{ row }"><span class="batch-test-status"><TestStatus :status="rowDisplay(row as Row).status" :description="`${(row as Row).host.name}：${rowDisplay(row as Row).description}`" />{{ rowDisplay(row as Row).label }}</span></template></ElTableColumn>
      <ElTableColumn label="新增信任" width="90"><template #default="{ row }">{{ (row as Row).record ? (row as Row).record!.auto_trusted_keys.length : '—' }}</template></ElTableColumn>
      <ElTableColumn label="操作" width="100"><template #default="{ row }"><ElButton link type="primary" :disabled="!started || (row as Row).state === 'submitting' || ((row as Row).state === 'submitted' && !!((row as Row).record && isActive((row as Row).record!)))" @click="emit('inspect', (row as Row).host)">查看详情</ElButton></template></ElTableColumn>
    </ElTable>
    <section v-if="pendingIdentities.length" class="batch-identities" aria-label="待核对的服务器身份">
      <h2>待核对的服务器身份</h2>
      <p class="batch-summary">共用跳板机的相同指纹已合并；密钥变化不会自动覆盖，请通过主机详情独立核对。</p>
      <div v-for="identity in pendingIdentities" :key="`${identity.target_type}:${identity.target_id}:${identity.fingerprint}`" class="batch-identity">
        <p>{{ identity.target_type === 'jump_host' ? '跳板机' : '目标主机' }} · {{ identity.address }}:{{ identity.port }} · {{ identity.key_type }}</p>
        <p>原指纹：{{ identity.previous_fingerprint ?? '无（首次连接）' }}</p>
        <p>新指纹：{{ identity.fingerprint }}</p>
      </div>
    </section>
    <p class="batch-summary">关闭弹窗会停止提交后续主机，已提交的测试继续执行。</p>
    <template #footer><ElButton @click="emit('update:modelValue', false)">关闭</ElButton></template>
  </ElDialog>
</template>

<style scoped>
.batch-summary { margin: 0 0 16px; color: var(--ui-text-secondary); }
.batch-test-status { display: inline-flex; align-items: center; gap: 8px; }
.batch-policy { display: grid; gap: 8px; margin-bottom: 16px; }
.batch-policy .batch-summary { margin: 0; }
.batch-policy .el-button { justify-self: start; }
.batch-policy .el-checkbox { height: auto; white-space: normal; }
.batch-policy .el-checkbox :deep(.el-checkbox__label) { white-space: normal; }
.batch-warning { margin: 0; color: var(--ui-warning); }
.batch-jump-hosts { max-height: 100px; overflow: auto; overflow-wrap: anywhere; }
.batch-jump-hosts p { margin: 0 0 4px; color: var(--ui-text-secondary); }
.batch-identities { margin: 16px 0; max-height: 200px; overflow: auto; }
.batch-identities h2 { margin: 0 0 8px; font-size: 14px; }
.batch-identity { padding: 8px 12px; border: 1px solid var(--ui-border); background: var(--ui-warning-soft); overflow-wrap: anywhere; }
.batch-identity + .batch-identity { margin-top: 8px; }
.batch-identity p { margin: 0 0 4px; }
</style>
