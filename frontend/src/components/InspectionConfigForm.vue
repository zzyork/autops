<script setup lang="ts">
import { ref, useId } from 'vue'
import { ElButton, ElCheckbox, ElInput, ElInputNumber } from 'element-plus'
import FieldError from '@/components/FieldError.vue'
import { focusFormFeedback, vNativeFieldAria } from '@/components/formFeedback'
import type { InspectionConfig, ServiceSpec, Thresholds } from '@/types/inspections'

const config = defineModel<InspectionConfig>({ required: true })
type ConfigField = keyof Thresholds | 'command_timeout_seconds' | 'host_timeout_seconds' | 'log_days' | 'log_lines' | 'log_paths'
type ServiceField = 'name' | 'candidates'
const formId = useId()
const formRoot = ref<HTMLElement | null>(null)
const fieldErrors = ref<Partial<Record<ConfigField, string>>>({})
const serviceErrors = ref<Record<number, Partial<Record<ServiceField, string>>>>({})
const fieldId = (field: ConfigField) => `${formId}-${field}`
const serviceId = (index: number, field: ServiceField) => `${formId}-service-${index}-${field}`
function clearField(field: ConfigField) { delete fieldErrors.value[field] }
function clearServiceField(index: number, field: ServiceField) { delete serviceErrors.value[index]?.[field] }
function clearServiceNames() {
  const names = new Set<string>()
  for (const [index, service] of config.value.services.entries()) {
    const name = service.name.trim()
    if (name && name.length <= 100 && !names.has(name)) clearServiceField(index, 'name')
    names.add(name)
  }
}
const thresholdFields: { label: string; warning: keyof Thresholds; critical: keyof Thresholds }[] = [
  { label: 'CPU', warning: 'cpu_warning', critical: 'cpu_critical' },
  { label: '内存', warning: 'mem_warning', critical: 'mem_critical' },
  { label: '磁盘', warning: 'disk_warning', critical: 'disk_critical' },
  { label: 'Swap', warning: 'swap_warning', critical: 'swap_critical' },
]
function clearCriticalFeedback(field: (typeof thresholdFields)[number]) {
  clearField(field.critical)
  const warning = config.value.thresholds[field.warning]
  const critical = config.value.thresholds[field.critical]
  if (Number.isFinite(warning) && warning >= 0 && warning <= 100 && warning <= critical) clearField(field.warning)
}
function clearHostTimeoutFeedback() {
  clearField('host_timeout_seconds')
  const command = config.value.command_timeout_seconds
  const host = config.value.host_timeout_seconds
  if (Number.isInteger(command) && command >= 2 && command <= 120 &&
    Number.isInteger(host) && host >= 10 && host <= 600 && command <= host) clearField('command_timeout_seconds')
}
const UNIT_NAME = /^[A-Za-z0-9_][A-Za-z0-9_.@-]{0,127}$/
const LOG_PATH = /^\/var\/log\/[^\x00-\x1f\x7f]+$/

function updateCandidates(index: number, value: string) {
  config.value.services[index]!.candidates = value.split(',').map((item) => item.trim())
  clearServiceField(index, 'candidates')
}
function addService() {
  if (config.value.services.length >= 30) return
  config.value.services.push({ name: '', candidates: [''], required: false })
  serviceErrors.value = {}
}
function removeService(index: number) {
  config.value.services.splice(index, 1)
  serviceErrors.value = {}
}
function updatePaths(value: string) {
  config.value.logs.paths = value === '' ? [] : value.split('\n')
  clearField('log_paths')
}
function validate(): boolean {
  const current = config.value
  const invalid: Partial<Record<ConfigField, string>> = {}
  const invalidServices: Record<number, Partial<Record<ServiceField, string>>> = {}
  for (const field of thresholdFields) {
    const warning = current.thresholds[field.warning]
    const critical = current.thresholds[field.critical]
    if (!Number.isFinite(warning) || warning < 0 || warning > 100 || warning > critical) invalid[field.warning] = `${field.label} 警告阈值须为 0-100，且不能高于严重值。`
    if (!Number.isFinite(critical) || critical < 0 || critical > 100) invalid[field.critical] = `${field.label} 严重阈值须为 0-100。`
  }
  const command = current.command_timeout_seconds
  const host = current.host_timeout_seconds
  if (!Number.isInteger(command) || command < 2 || command > 120 || (Number.isInteger(host) && host >= 10 && host <= 600 && command > host)) invalid.command_timeout_seconds = '命令时限须为 2-120 秒，且不能超过主机时限。'
  if (!Number.isInteger(host) || host < 10 || host > 600) invalid.host_timeout_seconds = '主机时限须为 10-600 秒。'
  const names = new Set<string>()
  for (const [index, service] of current.services.entries()) {
    const name = service.name.trim()
    if (!name || name.length > 100 || names.has(name)) {
      invalidServices[index] = { name: '服务名称须填写、不超过 100 字符且不能重复。' }
    }
    names.add(name)
    if (service.candidates.length < 1 || service.candidates.length > 5 ||
      service.candidates.some((candidate) => !UNIT_NAME.test(candidate)) || new Set(service.candidates).size !== service.candidates.length) {
      invalidServices[index] = { ...invalidServices[index], candidates: `服务 ${index + 1} 须填写 1-5 个不重复的有效候选单元名（以英文逗号分隔）。` }
    }
  }
  const { days, lines, paths } = current.logs
  if (!Number.isInteger(days) || days < 1 || days > 365) invalid.log_days = '日志范围须为 1-365 天。'
  if (!Number.isInteger(lines) || lines < 1 || lines > 200) invalid.log_lines = '每来源行数须为 1-200。'
  if (paths.length > 12 || new Set(paths).size !== paths.length || paths.some((path) => path.length > 240 || !LOG_PATH.test(path) || path.slice('/var/log/'.length).split('/').some((part) => !part || part === '.' || part === '..'))) {
    invalid.log_paths = '日志路径最多 12 条，须为 /var/log/ 下不重复的规范路径（每行一条、每条不超过 240 字符）。'
  }
  fieldErrors.value = invalid
  serviceErrors.value = invalidServices
  if (Object.keys(invalid).length || Object.keys(invalidServices).length) {
    focusFormFeedback(formRoot.value)
    return false
  }
  return true
}
function normalized(): InspectionConfig {
  return {
    ...config.value,
    thresholds: { ...config.value.thresholds },
    services: config.value.services.map((service: ServiceSpec) => ({ ...service, name: service.name.trim(), candidates: [...service.candidates] })),
    logs: { ...config.value.logs, paths: [...config.value.logs.paths] },
  }
}
defineExpose({ validate, normalized })
</script>

<template>
  <div ref="formRoot" class="inspection-config asset-form">
    <div class="form-section-title">资源阈值（%）</div>
    <div class="inspection-thresholds">
      <div v-for="field in thresholdFields" :key="field.label" class="inspection-threshold-row">
        <span aria-hidden="true">{{ field.label }}</span>
        <div class="field" :class="{ 'is-error': !!fieldErrors[field.warning] }"><label :id="`${fieldId(field.warning)}-label`" :for="fieldId(field.warning)">{{ field.label }} 警告</label><ElInputNumber :id="fieldId(field.warning)" v-model="config.thresholds[field.warning]" v-native-field-aria :min="0" :max="100" :controls="false" class="full-width" role="group" :aria-labelledby="`${fieldId(field.warning)}-label`" :aria-invalid="!!fieldErrors[field.warning]" :aria-describedby="fieldErrors[field.warning] ? `${fieldId(field.warning)}-error` : undefined" @update:model-value="clearField(field.warning)" /><FieldError :id="`${fieldId(field.warning)}-error`" :message="fieldErrors[field.warning] || ''" /></div>
        <div class="field" :class="{ 'is-error': !!fieldErrors[field.critical] }"><label :id="`${fieldId(field.critical)}-label`" :for="fieldId(field.critical)">{{ field.label }} 严重</label><ElInputNumber :id="fieldId(field.critical)" v-model="config.thresholds[field.critical]" v-native-field-aria :min="0" :max="100" :controls="false" class="full-width" role="group" :aria-labelledby="`${fieldId(field.critical)}-label`" :aria-invalid="!!fieldErrors[field.critical]" :aria-describedby="fieldErrors[field.critical] ? `${fieldId(field.critical)}-error` : undefined" @update:model-value="clearCriticalFeedback(field)" /><FieldError :id="`${fieldId(field.critical)}-error`" :message="fieldErrors[field.critical] || ''" /></div>
      </div>
    </div>
    <div class="form-section-title">执行时限</div>
    <div class="field-grid">
      <div class="field" :class="{ 'is-error': !!fieldErrors.command_timeout_seconds }"><label :id="`${fieldId('command_timeout_seconds')}-label`" :for="fieldId('command_timeout_seconds')">单命令时限（秒）</label><ElInputNumber :id="fieldId('command_timeout_seconds')" v-model="config.command_timeout_seconds" v-native-field-aria :min="2" :max="120" :controls="false" class="full-width" role="group" :aria-labelledby="`${fieldId('command_timeout_seconds')}-label`" :aria-invalid="!!fieldErrors.command_timeout_seconds" :aria-describedby="fieldErrors.command_timeout_seconds ? `${fieldId('command_timeout_seconds')}-error` : undefined" @update:model-value="clearField('command_timeout_seconds')" /><FieldError :id="`${fieldId('command_timeout_seconds')}-error`" :message="fieldErrors.command_timeout_seconds || ''" /></div>
      <div class="field" :class="{ 'is-error': !!fieldErrors.host_timeout_seconds }"><label :id="`${fieldId('host_timeout_seconds')}-label`" :for="fieldId('host_timeout_seconds')">单主机时限（秒）</label><ElInputNumber :id="fieldId('host_timeout_seconds')" v-model="config.host_timeout_seconds" v-native-field-aria :min="10" :max="600" :controls="false" class="full-width" role="group" :aria-labelledby="`${fieldId('host_timeout_seconds')}-label`" :aria-invalid="!!fieldErrors.host_timeout_seconds" :aria-describedby="fieldErrors.host_timeout_seconds ? `${fieldId('host_timeout_seconds')}-error` : undefined" @update:model-value="clearHostTimeoutFeedback" /><FieldError :id="`${fieldId('host_timeout_seconds')}-error`" :message="fieldErrors.host_timeout_seconds || ''" /></div>
    </div>
    <div class="form-section-title inspection-section-heading"><span>服务检查</span><ElButton :disabled="config.services.length >= 30" @click="addService">添加服务</ElButton></div>
    <div class="inspection-service-list">
      <div v-for="(service, index) in config.services" :key="index" class="inspection-service-row">
        <div class="field" :class="{ 'is-error': !!serviceErrors[index]?.name }"><label :for="serviceId(index, 'name')">服务 {{ index + 1 }} 名称</label><ElInput :id="serviceId(index, 'name')" v-model="service.name" maxlength="100" :aria-invalid="!!serviceErrors[index]?.name" :aria-describedby="serviceErrors[index]?.name ? `${serviceId(index, 'name')}-error` : undefined" @input="clearServiceNames" /><FieldError :id="`${serviceId(index, 'name')}-error`" :message="serviceErrors[index]?.name || ''" /></div>
        <div class="field" :class="{ 'is-error': !!serviceErrors[index]?.candidates }"><label :for="serviceId(index, 'candidates')">候选单元名（逗号分隔）</label><ElInput :id="serviceId(index, 'candidates')" :model-value="service.candidates.join(', ')" :aria-invalid="!!serviceErrors[index]?.candidates" :aria-describedby="serviceErrors[index]?.candidates ? `${serviceId(index, 'candidates')}-error` : undefined" @update:model-value="updateCandidates(index, $event)" /><FieldError :id="`${serviceId(index, 'candidates')}-error`" :message="serviceErrors[index]?.candidates || ''" /></div>
        <ElCheckbox v-model="service.required" class="inspection-required">必需</ElCheckbox>
        <ElButton type="danger" link :aria-label="`删除服务 ${service.name || index + 1}`" @click="removeService(index)">删除</ElButton>
      </div>
      <p v-if="!config.services.length" class="inspection-muted">不检查服务</p>
    </div>
    <div class="form-section-title">错误日志</div>
    <div class="field-grid">
      <div class="field" :class="{ 'is-error': !!fieldErrors.log_days }"><label :id="`${fieldId('log_days')}-label`" :for="fieldId('log_days')">最近天数</label><ElInputNumber :id="fieldId('log_days')" v-model="config.logs.days" v-native-field-aria :min="1" :max="365" :controls="false" class="full-width" role="group" :aria-labelledby="`${fieldId('log_days')}-label`" :aria-invalid="!!fieldErrors.log_days" :aria-describedby="fieldErrors.log_days ? `${fieldId('log_days')}-error` : undefined" @update:model-value="clearField('log_days')" /><FieldError :id="`${fieldId('log_days')}-error`" :message="fieldErrors.log_days || ''" /></div>
      <div class="field" :class="{ 'is-error': !!fieldErrors.log_lines }"><label :id="`${fieldId('log_lines')}-label`" :for="fieldId('log_lines')">每来源最多行数</label><ElInputNumber :id="fieldId('log_lines')" v-model="config.logs.lines" v-native-field-aria :min="1" :max="200" :controls="false" class="full-width" role="group" :aria-labelledby="`${fieldId('log_lines')}-label`" :aria-invalid="!!fieldErrors.log_lines" :aria-describedby="fieldErrors.log_lines ? `${fieldId('log_lines')}-error` : undefined" @update:model-value="clearField('log_lines')" /><FieldError :id="`${fieldId('log_lines')}-error`" :message="fieldErrors.log_lines || ''" /></div>
    </div>
    <div class="field" :class="{ 'is-error': !!fieldErrors.log_paths }"><label :for="fieldId('log_paths')">/var/log/ 下日志路径（每行一条，最多 12 条）</label><ElInput :id="fieldId('log_paths')" type="textarea" :rows="6" :model-value="config.logs.paths.join('\n')" :aria-invalid="!!fieldErrors.log_paths" :aria-describedby="fieldErrors.log_paths ? `${fieldId('log_paths')}-error` : undefined" @update:model-value="updatePaths" /><FieldError :id="`${fieldId('log_paths')}-error`" :message="fieldErrors.log_paths || ''" /></div>
  </div>
</template>

<style scoped>
.field > label { display: block; }
</style>
