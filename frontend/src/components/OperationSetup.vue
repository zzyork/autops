<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { ElAlert, ElButton, ElCheckbox, ElInput, ElInputNumber, ElOption, ElRadioButton, ElRadioGroup, ElSelect } from 'element-plus'
import type { Host } from '@/types/api'
import type { OperationAction, OperationField, OperationInspectInput, OperationModuleId, OperationPlanInput, OperationValue } from '@/types/operations'

const props = defineProps<{
  module: OperationModuleId
  actions: OperationAction[]
  hosts: Host[]
  busy: boolean
  inspecting: boolean
  hostsReady: boolean
  fixedHost?: Host
  initialAction?: string
}>()
const emit = defineEmits<{
  changed: []
  inspect: [input: OperationInspectInput]
  prepare: [input: OperationPlanInput]
}>()

const mode = ref<'single' | 'multiple'>('single')
const formId = useId()
const singleHost = ref<number | null>(null)
const multipleHosts = ref<number[]>([])
const sudo = ref(false)
const actionId = ref('')
const params = ref<Record<string, OperationValue>>({})
const error = ref('')
const invalid = ref<string | null>(null)
const action = computed(() => props.actions.find((item) => item.id === actionId.value))
const hostIds = computed(() => props.fixedHost ? [props.fixedHost.id] : mode.value === 'single' ? (singleHost.value === null ? [] : [singleHost.value]) : multipleHosts.value)

watch(() => [props.actions, props.initialAction] as const, ([actions, initialAction]) => { actionId.value = initialAction ? actions.find((item) => item.id === initialAction)?.id ?? '' : actions[0]?.id ?? '' }, { immediate: true })
watch(action, (next) => {
  params.value = Object.fromEntries((next?.fields ?? []).map((field) => [field.key, field.default ?? (field.kind === 'boolean' ? false : field.kind === 'number' || field.kind === 'select' ? null : '')]))
}, { immediate: true, flush: 'sync' })
watch(mode, () => { singleHost.value = null; multipleHosts.value = [] })
watch([mode, singleHost, multipleHosts, sudo, actionId, params], () => {
  error.value = ''
  invalid.value = null
  emit('changed')
}, { deep: true, flush: 'sync' })

function updateParam(field: OperationField, value: OperationValue) {
  params.value = { ...params.value, [field.key]: value }
}

function inspect() {
  if (!props.hostsReady || hostIds.value.length !== 1 || props.busy || props.inspecting) return
  emit('inspect', { module: props.module, host_id: hostIds.value[0]!, sudo: sudo.value })
}

function prepare() {
  if (!props.hostsReady || !action.value || props.busy) return
  if (!hostIds.value.length) {
    invalid.value = 'hosts'
    error.value = '请选择至少一台主机。'
    return
  }
  if (hostIds.value.length > 16) {
    invalid.value = 'hosts'
    error.value = '每份计划最多选择 16 台主机。'
    return
  }
  const values: Record<string, OperationValue> = {}
  for (const field of action.value.fields) {
    const value = params.value[field.key]
    if (field.required && (value === null || value === undefined || typeof value === 'string' && !value.trim())) {
      invalid.value = field.key
      error.value = `请填写${field.label}。`
      return
    }
    if (field.kind === 'number' && value !== null && (typeof value !== 'number' || !Number.isFinite(value))) {
      invalid.value = field.key
      error.value = `${field.label}必须为有效数字。`
      return
    }
    if (field.kind === 'select' && value !== null && !field.options?.some((option) => option.value === value)) {
      invalid.value = field.key
      error.value = `请选择有效的${field.label}。`
      return
    }
    values[field.key] = typeof value === 'string' ? value.trim() : value ?? null
  }
  emit('prepare', { module: props.module, action: action.value.id, host_ids: [...hostIds.value], params: values, sudo: sudo.value })
}
</script>

<template>
  <section class="host-section operation-section" aria-label="操作配置">
    <div class="section-header"><h2>操作配置</h2></div>
    <div class="asset-form">
      <div v-if="fixedHost" class="field"><span>目标主机</span><strong>{{ fixedHost.name }} · {{ fixedHost.address }}</strong></div>
      <template v-else>
        <div class="field"><span>目标范围 <em>*</em></span><ElRadioGroup v-model="mode" :disabled="busy" aria-label="目标范围"><ElRadioButton value="single">单台主机</ElRadioButton><ElRadioButton value="multiple">多台主机</ElRadioButton></ElRadioGroup></div>
        <label v-if="mode === 'single'" class="field" :class="{ 'is-error': invalid === 'hosts' }"><span>主机 <em>*</em></span><ElSelect v-model="singleHost" filterable :disabled="!hostsReady || busy" :aria-invalid="invalid === 'hosts'" placeholder="选择主机" class="full-width"><ElOption v-for="host in hosts" :key="host.id" :label="`${host.name} · ${host.address}`" :value="host.id" /></ElSelect></label>
        <div v-else class="field" :class="{ 'is-error': invalid === 'hosts' }"><label :for="`${formId}-hosts`">主机 <em>*</em></label><ElSelect :id="`${formId}-hosts`" v-model="multipleHosts" multiple :multiple-limit="16" filterable collapse-tags :disabled="!hostsReady || busy" :aria-invalid="invalid === 'hosts'" placeholder="选择多台主机" class="full-width"><ElOption v-for="host in hosts" :key="host.id" :label="`${host.name} · ${host.address}`" :value="host.id" /></ElSelect><span class="ssh-field-hint">已选 {{ multipleHosts.length }} / 16 台；读取现状仅支持单台。</span></div>
      </template>
      <div class="field"><ElCheckbox v-model="sudo" :disabled="busy" label="使用免密 sudo（需目标主机已配置）" /></div>
      <div class="operation-actions"><ElButton :loading="inspecting" :disabled="!hostsReady || busy || hostIds.length !== 1" @click="inspect">读取现状</ElButton><span v-if="hostIds.length > 1" class="ssh-field-hint">读取现状须仅选一台主机。</span></div>
      <div class="form-section-title">计划参数</div>
      <label v-if="!initialAction" class="field"><span>操作 <em>*</em></span><ElSelect v-model="actionId" :disabled="busy" class="full-width" aria-label="操作"><ElOption v-for="item in actions" :key="item.id" :label="item.title" :value="item.id" /></ElSelect></label>
      <p v-if="action" class="ssh-field-hint">{{ action.description }}</p>
      <div v-if="action" class="field-grid">
        <div v-for="field in action.fields" :key="field.key" class="field" :class="{ 'is-error': invalid === field.key }">
          <label v-if="field.kind !== 'boolean'" :for="`${formId}-${field.key}`">{{ field.label }} <em v-if="field.required">*</em></label>
          <ElInput v-if="field.kind === 'text' || field.kind === 'textarea'" :id="`${formId}-${field.key}`" :model-value="String(params[field.key] ?? '')" :type="field.kind === 'textarea' ? 'textarea' : 'text'" :rows="3" :disabled="busy" :aria-invalid="invalid === field.key" @update:model-value="updateParam(field, $event)" />
          <ElInputNumber v-else-if="field.kind === 'number'" :id="`${formId}-${field.key}`" :model-value="typeof params[field.key] === 'number' ? params[field.key] as number : undefined" :controls="false" :disabled="busy" :aria-invalid="invalid === field.key" class="full-width" @update:model-value="updateParam(field, $event ?? null)" />
          <ElSelect v-else-if="field.kind === 'select'" :id="`${formId}-${field.key}`" :model-value="params[field.key]" :disabled="busy" :aria-invalid="invalid === field.key" placeholder="请选择" class="full-width" @update:model-value="updateParam(field, $event)"><ElOption v-for="option in field.options ?? []" :key="String(option.value)" :label="option.label" :value="option.value" /></ElSelect>
          <ElCheckbox v-else :id="`${formId}-${field.key}`" :model-value="params[field.key] === true" :disabled="busy" @update:model-value="updateParam(field, $event === true)">{{ field.label }} <em v-if="field.required">*</em></ElCheckbox>
          <span v-if="field.description" class="ssh-field-hint">{{ field.description }}</span>
        </div>
      </div>
      <ElAlert v-if="action?.destructive" title="此操作可能修改或清除目标主机上的现有数据，请在计划中核对影响。" type="warning" :closable="false" show-icon />
      <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <div class="operation-actions"><ElButton type="primary" :loading="busy" :disabled="!hostsReady || !action" @click="prepare">准备计划</ElButton></div>
    </div>
  </section>
</template>
