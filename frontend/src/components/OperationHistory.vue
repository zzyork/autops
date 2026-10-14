<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElLoading, ElOption, ElSelect, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { listOperationTasks } from '@/api/operations'
import { showRequestError } from '@/components/feedback'
import ListPagination from '@/components/ListPagination.vue'
import { DEFAULT_PAGE_SIZE } from '@/components/pagination'
import { operationTime, statusType, taskLabels } from '@/components/operationDisplay'
import type { OperationModule, OperationModuleId, OperationTask } from '@/types/operations'

const props = defineProps<{ module: OperationModuleId; modules: OperationModule[]; revision: number }>()
const emit = defineEmits<{ select: [id: string] }>()
const vLoading = ElLoading.directive
const filter = ref<OperationModuleId | null>(props.module)
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)
const tasks = ref<OperationTask[]>([])
const total = ref(0)
const loading = ref(false)
const loaded = ref(false)
let requestId = 0
let active = true

async function load() {
  const current = ++requestId
  loading.value = true
  try {
    const result = await listOperationTasks(filter.value, page.value, pageSize.value)
    if (!active || current !== requestId) return
    const lastPage = Math.max(1, Math.ceil(result.total / pageSize.value))
    if (page.value > lastPage) { page.value = lastPage; void load(); return }
    tasks.value = result.items
    total.value = result.total
    loaded.value = true
  } catch {
    if (!active || current !== requestId) return
    loaded.value = false
    showRequestError()
  } finally {
    if (active && current === requestId) loading.value = false
  }
}
function changeFilter(value: string) {
  filter.value = value === '' ? null : value as OperationModuleId
  page.value = 1
  loaded.value = false
  void load()
}
function changePage() { loaded.value = false; void load() }
watch(() => props.revision, () => { if (active) void load() })
onMounted(() => { void load() })
onUnmounted(() => { active = false; requestId++ })
</script>

<template>
  <section class="host-section operation-section" aria-label="运维任务历史">
    <div class="section-header"><h2>任务历史</h2></div>
    <div class="host-toolbar"><span></span><div class="host-toolbar-right"><label class="operation-filter">模块 <ElSelect :model-value="filter ?? ''" :disabled="loading" aria-label="筛选运维模块" @update:model-value="changeFilter"><ElOption label="全部模块" value="" /><ElOption v-for="item in modules" :key="item.id" :label="item.title" :value="item.id" /></ElSelect></label><ElButton :loading="loading" @click="load">刷新</ElButton></div></div>
    <div v-loading="loading" class="host-table-wrap">
      <ElTable v-if="loaded" :data="tasks" row-key="id" class="host-table" empty-text="暂无历史任务">
        <ElTableColumn label="任务" min-width="180"><template #default="{ row }"><ElButton link type="primary" class="operation-link" @click="emit('select', row.id)">{{ row.title }}</ElButton></template></ElTableColumn>
        <ElTableColumn label="模块" min-width="110"><template #default="{ row }">{{ modules.find((item) => item.id === row.module)?.title ?? row.module }}</template></ElTableColumn>
        <ElTableColumn label="状态" width="110"><template #default="{ row }"><ElTag :type="statusType(row.status)" size="small">{{ taskLabels[row.status as OperationTask['status']] }}</ElTag></template></ElTableColumn>
        <ElTableColumn label="主机" min-width="160"><template #default="{ row }">{{ row.hosts.map((host: OperationTask['hosts'][number]) => host.host_name).join('、') }}</template></ElTableColumn>
        <ElTableColumn label="创建时间" min-width="170"><template #default="{ row }">{{ operationTime(row.created_at) }}</template></ElTableColumn>
        <ElTableColumn label="操作" width="100" fixed="right"><template #default="{ row }"><ElButton link type="primary" @click="emit('select', row.id)">查看详情</ElButton></template></ElTableColumn>
      </ElTable>
      <div v-else-if="!loading" class="inspection-retry"><ElButton @click="load">重试加载历史记录</ElButton></div>
    </div>
    <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :total-known="loaded && !loading" :disabled="loading || !loaded" @change="changePage" />
  </section>
</template>
