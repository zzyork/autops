<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCheckbox, ElCheckboxGroup, ElDialog, ElInput, ElLoading, ElOption, ElSelect, ElTable, ElTableColumn } from 'element-plus'
import { listGroups, listHosts } from '@/api/assets'
import { createInspectionTask, getInspectionCatalog } from '@/api/inspections'
import { showSystemError } from '@/components/feedback'
import type { Host, HostGroup } from '@/types/api'
import type { CheckId, InspectionCatalog, InspectionInput, TaskDetail } from '@/types/inspections'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; created: [task: TaskDetail] }>()
const vLoading = ElLoading.directive
const MAX_HOSTS = 32
const hosts = ref<Host[]>([])
const groups = ref<HostGroup[]>([])
const catalog = ref<InspectionCatalog | null>(null)
const name = ref('')
const selectedHosts = ref<number[]>([])
const selectedChecks = ref<CheckId[]>([])
const groupId = ref<number | null>(null)
const loading = ref(false)
const loaded = ref(false)
const saving = ref(false)
const formError = ref('')
const invalidField = ref<'name' | 'hosts' | 'checks' | null>(null)
const visibleHosts = computed(() => hosts.value.filter((host) => groupId.value === null || host.group_id === groupId.value))
let session = 0

watch(() => props.modelValue, (visible) => {
  session++
  if (!visible) return
  hosts.value = []
  groups.value = []
  catalog.value = null
  name.value = ''
  selectedHosts.value = []
  selectedChecks.value = []
  groupId.value = null
  loaded.value = false
  loading.value = false
  saving.value = false
  formError.value = ''
  invalidField.value = null
  void loadOptions()
}, { immediate: true })
onUnmounted(() => { session++ })
watch([name, selectedHosts, selectedChecks], () => { formError.value = ''; invalidField.value = null })

async function loadOptions() {
  const current = session
  loading.value = true
  loaded.value = false
  try {
    const [hostList, groupList, definitions] = await Promise.all([listHosts('', null), listGroups(), getInspectionCatalog()])
    if (current !== session) return
    hosts.value = hostList
    groups.value = groupList
    catalog.value = definitions
    selectedChecks.value = definitions.checks.map((check) => check.id)
    loaded.value = true
  } catch {
    if (current === session) showSystemError()
  } finally {
    if (current === session) loading.value = false
  }
}

function groupName(id: number): string {
  return groups.value.find((group) => group.id === id)?.name ?? ''
}

function toggleHost(id: number, checked: string | number | boolean) {
  if (checked === true && !selectedHosts.value.includes(id) && selectedHosts.value.length < MAX_HOSTS) selectedHosts.value = [...selectedHosts.value, id]
  if (checked === false) selectedHosts.value = selectedHosts.value.filter((selected) => selected !== id)
}

async function submit() {
  if (!loaded.value || saving.value) return
  const taskName = name.value.trim()
  if (!taskName || taskName.length > 100) {
    invalidField.value = 'name'
    formError.value = '任务名称须填写且不超过 100 字符。'
    return
  }
  if (!selectedHosts.value.length || selectedHosts.value.length > MAX_HOSTS) {
    invalidField.value = 'hosts'
    formError.value = `请选择 1-${MAX_HOSTS} 台主机。`
    return
  }
  if (!selectedChecks.value.length) {
    invalidField.value = 'checks'
    formError.value = '请至少选择一个检查项。'
    return
  }
  const body: InspectionInput = {
    name: taskName,
    hosts: hosts.value.filter((host) => selectedHosts.value.includes(host.id)).map((host) => ({ id: host.id, version: host.version })),
    checks: [...selectedChecks.value],
  }
  const current = session
  saving.value = true
  try {
    const task = await createInspectionTask(body)
    if (current !== session) return
    emit('update:modelValue', false)
    emit('created', task)
  } catch {
    if (current === session) showSystemError()
  } finally {
    if (current === session) saving.value = false
  }
}
</script>

<template>
  <ElDialog :model-value="modelValue" align-center title="创建巡检任务" width="min(720px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving" @update:model-value="emit('update:modelValue', $event)">
    <div v-loading="loading" class="inspection-create asset-form">
      <template v-if="loaded && catalog">
        <label class="field" :class="{ 'is-error': invalidField === 'name' }"><span>任务名称 <em>*</em></span><ElInput v-model="name" maxlength="100" :aria-invalid="invalidField === 'name'" placeholder="输入任务名称" /></label>
        <div class="form-section-title">选择主机 <em>*</em></div>
        <div class="inspection-selection-head"><span>已选 {{ selectedHosts.length }} / {{ MAX_HOSTS }} 台</span><label class="field">分组筛选<ElSelect v-model="groupId" clearable :value-on-clear="null" placeholder="全部分组" class="inspection-group-select" aria-label="按分组筛选主机"><ElOption v-for="group in groups" :key="group.id" :label="group.name" :value="group.id" /></ElSelect></label></div>
        <div class="inspection-host-picker" :class="{ 'is-error': invalidField === 'hosts' }">
          <ElTable :data="visibleHosts" row-key="id" size="small" :empty-text="groupId === null ? '暂无主机' : '该分组暂无主机'">
            <ElTableColumn label="选择" width="65"><template #default="{ row }"><ElCheckbox :model-value="selectedHosts.includes(row.id)" :aria-label="`选择主机 ${row.name}`" :disabled="selectedHosts.length >= MAX_HOSTS && !selectedHosts.includes(row.id)" @change="toggleHost(row.id, $event)" /></template></ElTableColumn>
            <ElTableColumn label="主机" min-width="180"><template #default="{ row }"><strong>{{ row.name }}</strong><div class="host-address">{{ row.address }}</div></template></ElTableColumn>
            <ElTableColumn label="分组" min-width="110"><template #default="{ row }">{{ groupName((row as Host).group_id) }}</template></ElTableColumn>
          </ElTable>
        </div>
        <div class="form-section-title">检查项 <em>*</em></div>
        <ElCheckboxGroup v-model="selectedChecks" class="inspection-check-picker" :class="{ 'is-error': invalidField === 'checks' }" aria-label="检查项">
          <ElCheckbox v-for="check in catalog.checks" :key="check.id" :value="check.id"><span>{{ check.title }}</span><span class="inspection-muted">{{ check.description }}</span></ElCheckbox>
        </ElCheckboxGroup>
        <p class="inspection-muted">本次巡检使用统一默认规则。阈值、服务配置及执行时限可在“巡检规则”页面查看。</p>
        <ElAlert v-if="formError" :title="formError" type="error" :closable="false" show-icon />
      </template>
      <div v-else-if="!loading" class="inspection-retry"><ElButton @click="loadOptions">重试加载</ElButton></div>
    </div>
    <template #footer><ElButton :disabled="saving" @click="emit('update:modelValue', false)">取消</ElButton><ElButton type="primary" :loading="saving" :disabled="!loaded" @click="submit">创建任务</ElButton></template>
  </ElDialog>
</template>
