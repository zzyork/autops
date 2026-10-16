<script setup lang="ts">
import { onMounted, onUnmounted, ref, useId, watch } from 'vue'
import { ElButton, ElTag } from 'element-plus'
import { getOperationBlockers, getOperationTask, resolveOperationHost } from '@/api/operations'
import { HttpError } from '@/api/http'
import { showRequestError } from './feedback'
import ListPagination from './ListPagination.vue'
import OperationTaskDetail from './OperationTaskDetail.vue'
import type { OperationBlocker, OperationTask } from '@/types/operations'

const props = defineProps<{ hostId: number }>()
const emit = defineEmits<{ loaded: [ready: boolean, total: number]; busy: [value: boolean] }>()
const blockers = ref<OperationBlocker[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const ready = ref(false)
const expanded = ref(false)
const listId = `operation-blockers-${useId()}`
const detail = ref<OperationTask | null>(null)
const resolving = ref<number | null>(null)
let request = 0
let active = true
async function refresh(reset = false): Promise<boolean> {
  if (reset) page.value = 1
  const current = ++request
  loading.value = true
  ready.value = false
  emit('loaded', false, total.value)
  try {
    const result = await getOperationBlockers(props.hostId, page.value, pageSize.value)
    if (!active || current !== request) return false
    if (page.value > 1 && result.total <= (page.value - 1) * pageSize.value) return refresh(true)
    blockers.value = result.items
    total.value = result.total
    ready.value = true
    emit('loaded', true, result.total)
    return result.total === 0
  } catch (error) { if (active && current === request) showRequestError(error); return false }
  finally { if (active && current === request) loading.value = false }
}
async function open(id: string) {
  try {
    const task = await getOperationTask(id)
    if (!task.hosts.some((host) => host.host_id === props.hostId && host.status === 'unknown' && !host.resolved_at)) throw new HttpError()
    detail.value = task
  } catch (error) { showRequestError(error) }
}
async function resolve(id: string, hostId: number, note: string) {
  if (resolving.value !== null || detail.value?.id !== id || hostId !== props.hostId) return
  resolving.value = hostId
  emit('busy', true)
  try {
    detail.value = await resolveOperationHost(id, hostId, note)
    await refresh(true)
  } catch (error) { showRequestError(error) }
  finally { resolving.value = null; emit('busy', false) }
}
watch(() => props.hostId, () => { detail.value = null; void refresh(true) })
onMounted(() => { void refresh(true) })
onUnmounted(() => { active = false; request++ })
defineExpose({ refresh })
</script>

<template>
  <section v-if="!ready || total" class="host-section operation-section" aria-label="未确认结果">
    <div class="section-header"><h2>未确认结果</h2><ElTag v-if="ready" type="warning">{{ total }} 条待核对</ElTag><ElButton v-if="ready" @click="refresh(true)">刷新</ElButton></div>
    <p v-if="!ready">{{ loading ? '读取中…' : '未能读取阻塞记录' }}</p>
    <template v-else-if="total">
      <ElButton :aria-expanded="expanded" :aria-controls="listId" @click="expanded = !expanded">{{ expanded ? '收起' : '展开' }}未确认结果</ElButton>
      <div :id="listId" v-if="expanded">
        <div v-for="item in blockers" :key="item.task_id" class="operation-host-head"><span>{{ item.title }} · {{ new Date(item.confirmed_at).toLocaleString('zh-CN') }}</span><ElButton @click="open(item.task_id)">核对未确认结果</ElButton></div>
        <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :disabled="loading" @change="refresh()" />
      </div>
    </template>
    <ElButton v-if="!loading && !ready" @click="refresh(true)">重新查询</ElButton>
  </section>
  <OperationTaskDetail v-if="detail" :task="detail" :allowed-host-id="hostId" :resolving-host-id="resolving" show-step-evidence @resolve="resolve" @dialog-open="emit('busy', $event)" @busy="emit('busy', $event)" />
</template>
