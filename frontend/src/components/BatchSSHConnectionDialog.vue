<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElDialog, ElTable, ElTableColumn } from 'element-plus'
import { startConnectionTest } from '@/api/ssh_connections'
import { getJumpHost } from '@/api/jump_hosts'
import { RequestCancelledError } from '@/api/http'
import { showSystemError } from '@/components/feedback'
import { ensureSSHIdentities } from '@/api/sshIdentity'
import { SSH_RESULT_UNAVAILABLE, SSH_RETEST_REQUIRED, sshTestDisplay } from '@/components/sshTestDisplay'
import TestStatus from '@/components/TestStatus.vue'
import { hostDisplayName } from '@/components/hostDisplay'
import type { ConnectionTestResult, Host, JumpHost } from '@/types/api'

const props = defineProps<{ modelValue: boolean; hosts: Host[] }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'status-changed': []
}>()
interface Row { host: Host; result: ConnectionTestResult | null; state: 'pending' | 'submitting' | 'submitted' | 'confirmed' | 'unavailable' }
const rows = ref<Row[]>([])
const running = ref(false)
const stopped = ref(false)
const started = ref(false)
const confirmedCount = ref(0)
const jumpHosts = ref<JumpHost[]>([])
const loadingScope = ref(false)
const scopeLoaded = ref(false)
const CONCURRENCY = 4
let generation = 0
const completed = computed(() => rows.value.filter((row) => row.result !== null).length)
const jumpHostCount = computed(() => new Set(rows.value.map((row) => row.host.jump_host_id).filter((id) => id !== null)).size)
function reset() {
  generation++
  running.value = false
}
async function start() {
  if (started.value || !scopeLoaded.value || !rows.value.length) return
  const current = generation
  const isCurrent = () => current === generation && props.modelValue && !stopped.value
  started.value = true
  running.value = true
  stopped.value = false
  confirmedCount.value = 0
  try {
    await ensureSSHIdentities(rows.value.map((row) => ({ target_type: 'host', target_id: row.host.id, version: row.host.version })), {
      isCurrent, onTrusted: () => emit('status-changed'),
    })
  } catch (error) {
    emit('status-changed')
    if (current === generation) {
      started.value = false
      stopped.value = true
      running.value = false
      showSystemError(error)
    }
    return
  }
  if (!isCurrent()) return
  let next = 0
  async function worker() {
    while (current === generation && !stopped.value) {
      const row = rows.value[next++]
      if (!row) return
      row.state = 'submitting'
      try {
        const result = await startConnectionTest({ target_type: 'host', target_id: row.host.id, version: row.host.version }, {
          isCurrent, onTrusted: () => emit('status-changed'),
        })
        emit('status-changed')
        if (current !== generation || !props.modelValue) return
        row.state = 'submitted'
        row.result = result
        if (!stopped.value && result.status === 'awaiting_trust') {
          try {
            await ensureSSHIdentities([{ target_type: 'host', target_id: row.host.id, version: row.host.version }], {
              isCurrent, onTrusted: () => {
                emit('status-changed')
                if (current === generation && props.modelValue) row.state = 'confirmed'
              },
            })
            if (current === generation && props.modelValue) {
              row.state = 'confirmed'
              confirmedCount.value++
            }
          } catch (error) {
            emit('status-changed')
            if (!isCurrent()) return
            stopped.value = true
            if (!(error instanceof RequestCancelledError)) showSystemError(error)
            return
          }
        }
      } catch (error) {
        emit('status-changed')
        if (current !== generation) return
        if (error instanceof RequestCancelledError) {
          stopped.value = true
          if (!row.result) row.state = 'pending'
          return
        }
        row.state = 'unavailable'
        stopped.value = true
        showSystemError(error)
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
  const ids = [...new Set(rows.value.flatMap((row) => row.host.jump_host_id === null ? [] : [row.host.jump_host_id]))]
  try {
    const result = await Promise.all(ids.map(getJumpHost))
    if (current !== generation) return
    jumpHosts.value = result
    scopeLoaded.value = true
  } catch (error) {
    if (current === generation) showSystemError(error)
  } finally {
    if (current === generation) loadingScope.value = false
  }
}
function rowDisplay(row: Row) {
  if (row.state === 'unavailable') return SSH_RESULT_UNAVAILABLE
  if (row.state === 'confirmed') return SSH_RETEST_REQUIRED
  if (!row.result) {
    if (row.state === 'submitting') {
      return { status: 'pending' as const, label: '提交中', description: 'SSH 连接测试提交中' }
    }
    if (stopped.value) {
      return { status: 'queued' as const, label: '未提交', description: 'SSH 连接测试未提交' }
    }
    return { status: 'queued' as const, label: '待提交', description: 'SSH 连接测试待提交' }
  }
  return sshTestDisplay(row.result.status)
}
watch(() => props.modelValue, (visible) => {
  reset()
  if (!visible) return
  rows.value = props.hosts.map((host) => ({ host: { ...host }, result: null, state: 'pending' }))
  started.value = false
  stopped.value = false
  confirmedCount.value = 0
  jumpHosts.value = []
  loadingScope.value = false
  scopeLoaded.value = false
  void loadScope()
})
onUnmounted(reset)
</script>

<template>
  <ElDialog :model-value="modelValue" title="批量测试连接" width="min(var(--ui-dialog-width), calc(100vw - 32px))" align-center :close-on-click-modal="false" @update:model-value="emit('update:modelValue', $event)">
    <div class="batch-policy">
      <p class="batch-summary">本次范围：下列 {{ rows.length }} 台主机及其关联的 {{ jumpHostCount }} 台跳板机。</p>
      <p v-if="loadingScope" class="batch-summary">正在读取跳板机范围…</p>
      <div v-else-if="scopeLoaded && jumpHosts.length" class="batch-jump-hosts" aria-label="本次关联跳板机">
        <p v-for="jump in jumpHosts" :key="jump.id">跳板机：{{ jump.name }} · {{ jump.address }}:{{ jump.port }}</p>
      </div>
      <ElButton v-else-if="!scopeLoaded" @click="loadScope">重新读取范围</ElButton>
      <ElButton v-if="!started" type="primary" :disabled="!scopeLoaded || !rows.length" @click="start">开始测试</ElButton>
    </div>
    <p class="batch-summary ui-execution-status" :data-execution-state="running ? 'in-progress' : undefined">
      共 {{ rows.length }} 台，已返回结果 {{ completed }} 台{{ running ? '，测试进行中' : '' }}。
    </p>
    <p
      v-if="stopped || confirmedCount"
      class="batch-summary ui-execution-status ui-execution-notice"
      :data-execution-state="stopped ? 'aborted' : undefined"
    >{{ stopped ? '后续提交已停止' : '身份已确认' }}，请重新开始测试。</p>
    <ElTable :data="rows" max-height="420">
      <ElTableColumn label="主机" min-width="160">
        <template #default="{ row }">
          <span :title="hostDisplayName((row as Row).host)">{{ hostDisplayName((row as Row).host) }}</span>
          <div class="ui-item-secondary">{{ (row as Row).host.vip || (row as Row).host.address }}:{{ (row as Row).host.port }}</div>
        </template>
      </ElTableColumn>
      <ElTableColumn label="状态" min-width="140">
        <template #default="{ row }">
          <TestStatus
            :status="rowDisplay(row as Row).status"
            :description="`${hostDisplayName((row as Row).host)}：${rowDisplay(row as Row).description}`"
            :label="rowDisplay(row as Row).label"
          />
        </template>
      </ElTableColumn>
    </ElTable>
    <p class="batch-summary">关闭弹窗会停止提交后续主机，正在测试的主机仍会完成。</p>
    <template #footer><ElButton @click="emit('update:modelValue', false)">关闭</ElButton></template>
  </ElDialog>
</template>

<style scoped>
.batch-summary {
  margin: 0 0 var(--ui-space-4);
}

.batch-summary:not([data-execution-state]) {
  color: var(--ui-text-secondary);
}

.batch-policy { display: grid; gap: var(--ui-space-2); margin-bottom: var(--ui-space-4); }
.batch-policy .batch-summary { margin: 0; }
.batch-policy .el-button { justify-self: start; margin-left: 0; }
.batch-jump-hosts { max-height: 100px; overflow: auto; overflow-wrap: anywhere; }
.batch-jump-hosts p { margin: 0 0 var(--ui-space-1); color: var(--ui-text-secondary); }
</style>
