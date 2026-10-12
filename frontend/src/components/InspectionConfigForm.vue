<script setup lang="ts">
import { ref } from 'vue'
import { ElAlert, ElButton, ElCheckbox, ElInput, ElInputNumber } from 'element-plus'
import type { InspectionConfig, ServiceSpec, Thresholds } from '@/types/inspections'

const config = defineModel<InspectionConfig>({ required: true })
const error = ref('')
const thresholdFields: { label: string; warning: keyof Thresholds; critical: keyof Thresholds }[] = [
  { label: 'CPU', warning: 'cpu_warning', critical: 'cpu_critical' },
  { label: '内存', warning: 'mem_warning', critical: 'mem_critical' },
  { label: '磁盘', warning: 'disk_warning', critical: 'disk_critical' },
  { label: 'Swap', warning: 'swap_warning', critical: 'swap_critical' },
]
const UNIT_NAME = /^[A-Za-z0-9_][A-Za-z0-9_.@-]{0,127}$/

function updateCandidates(index: number, value: string) {
  config.value.services[index]!.candidates = value.split(',').map((item) => item.trim())
  error.value = ''
}
function addService() {
  if (config.value.services.length >= 30) return
  config.value.services.push({ name: '', candidates: [''], required: false })
  error.value = ''
}
function removeService(index: number) {
  config.value.services.splice(index, 1)
  error.value = ''
}
function validate(): boolean {
  const current = config.value
  for (const field of thresholdFields) {
    const warning = current.thresholds[field.warning]
    const critical = current.thresholds[field.critical]
    if (!Number.isFinite(warning) || !Number.isFinite(critical) || warning < 0 || critical > 100 || warning > critical) {
      error.value = `${field.label} 阈值须为 0-100，且警告值不能高于严重值。`
      return false
    }
  }
  const command = current.command_timeout_seconds
  const host = current.host_timeout_seconds
  if (!Number.isInteger(command) || command < 2 || command > 120 || !Number.isInteger(host) || host < 10 || host > 600 || command > host) {
    error.value = '命令时限须为 2-120 秒，主机时限须为 10-600 秒，且命令时限不能超过主机时限。'
    return false
  }
  const names = new Set<string>()
  for (const service of current.services) {
    const name = service.name.trim()
    if (!name || name.length > 100 || names.has(name)) {
      error.value = '服务名称须填写、不超过 100 字符且不能重复。'
      return false
    }
    names.add(name)
    if (service.candidates.length < 1 || service.candidates.length > 5 ||
      service.candidates.some((candidate) => !UNIT_NAME.test(candidate)) || new Set(service.candidates).size !== service.candidates.length) {
      error.value = `服务“${name}”须填写 1-5 个不重复的有效候选单元名（以英文逗号分隔）。`
      return false
    }
  }
  error.value = ''
  return true
}
function normalized(): InspectionConfig {
  return {
    ...config.value,
    thresholds: { ...config.value.thresholds },
    services: config.value.services.map((service: ServiceSpec) => ({ ...service, name: service.name.trim(), candidates: [...service.candidates] })),
  }
}
defineExpose({ validate, normalized })
</script>

<template>
  <div class="inspection-config asset-form">
    <div class="form-section-title">资源阈值（%）</div>
    <div class="inspection-thresholds">
      <div v-for="field in thresholdFields" :key="field.label" class="inspection-threshold-row">
        <span>{{ field.label }}</span>
        <label class="field"><span>警告</span><ElInputNumber v-model="config.thresholds[field.warning]" :min="0" :max="100" :controls="false" class="full-width" @change="error = ''" /></label>
        <label class="field"><span>严重</span><ElInputNumber v-model="config.thresholds[field.critical]" :min="0" :max="100" :controls="false" class="full-width" @change="error = ''" /></label>
      </div>
    </div>
    <div class="form-section-title">执行时限</div>
    <div class="field-grid">
      <label class="field"><span>单命令时限（秒）</span><ElInputNumber v-model="config.command_timeout_seconds" :min="2" :max="120" :controls="false" class="full-width" @change="error = ''" /></label>
      <label class="field"><span>单主机时限（秒）</span><ElInputNumber v-model="config.host_timeout_seconds" :min="10" :max="600" :controls="false" class="full-width" @change="error = ''" /></label>
    </div>
    <div class="form-section-title inspection-section-heading"><span>服务检查</span><ElButton :disabled="config.services.length >= 30" @click="addService">添加服务</ElButton></div>
    <div class="inspection-service-list">
      <div v-for="(service, index) in config.services" :key="index" class="inspection-service-row">
        <label class="field"><span>服务名称</span><ElInput v-model="service.name" maxlength="100" @input="error = ''" /></label>
        <label class="field"><span>候选单元名（逗号分隔）</span><ElInput :model-value="service.candidates.join(', ')" @update:model-value="updateCandidates(index, $event)" /></label>
        <ElCheckbox v-model="service.required" class="inspection-required">必需</ElCheckbox>
        <ElButton type="danger" link :aria-label="`删除服务 ${service.name || index + 1}`" @click="removeService(index)">删除</ElButton>
      </div>
      <p v-if="!config.services.length" class="inspection-muted">不检查服务</p>
    </div>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon />
  </div>
</template>
