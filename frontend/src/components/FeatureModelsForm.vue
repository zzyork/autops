<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, useId } from 'vue'
import { ElButton, ElInputNumber, ElMessage, ElOption, ElSelect } from 'element-plus'
import { getFeatureModels, updateFeatureModels } from '@/api/ai'
import FieldError from '@/components/FieldError.vue'
import { showRequestError } from '@/components/feedback'
import { focusFormFeedback, vNativeFieldAria } from '@/components/formFeedback'
import { MAX_OUTPUT_TOKENS, MIN_OUTPUT_TOKENS } from '@/types/ai'
import type { FeatureModelsConfig, ModelConnection } from '@/types/ai'

const props = defineProps<{ connections: ModelConnection[]; connectionsLoaded: boolean; connectionsLoading: boolean }>()
const emit = defineEmits<{ configured: [config: FeatureModelsConfig | null] }>()
const draft = ref<FeatureModelsConfig>({
  chat_connection_id: null,
  inspection_report_connection_id: null,
  chat_max_tokens: 1024,
  inspection_report_max_tokens: 32_768,
})
const tokenFields = [
  { key: 'chat_max_tokens', label: 'AI 对话最大响应 token' },
  { key: 'inspection_report_max_tokens', label: '巡检报告最大响应 token' },
] as const
type TokenField = (typeof tokenFields)[number]['key']
const formId = useId()
const formRoot = ref<HTMLFormElement | null>(null)
const fieldErrors = ref<Partial<Record<TokenField, string>>>({})
const fieldId = (field: TokenField) => `${formId}-${field}`
const loaded = ref(false)
const loading = ref(false)
const saving = ref(false)
const disabled = computed(() => !props.connectionsLoaded || props.connectionsLoading || saving.value)
const primary = computed(() => props.connections.find((item) => item.is_default))
const chatChoice = computed<number | 'primary'>({
  get: () => draft.value.chat_connection_id ?? 'primary',
  set: (value) => { draft.value.chat_connection_id = value === 'primary' ? null : value },
})
const reportChoice = computed<number | 'primary'>({
  get: () => draft.value.inspection_report_connection_id ?? 'primary',
  set: (value) => { draft.value.inspection_report_connection_id = value === 'primary' ? null : value },
})
let active = true
let sequence = 0

function missing(id: number | null) {
  return id !== null && props.connectionsLoaded && !props.connections.some((item) => item.id === id)
}
function connectionLabel(item: ModelConnection) {
  return `${item.name} / ${item.model}`
}
function clearField(field: TokenField) {
  delete fieldErrors.value[field]
}
function validate(): boolean {
  const invalid: Partial<Record<TokenField, string>> = {}
  for (const field of tokenFields) {
    const value = draft.value[field.key]
    if (!Number.isSafeInteger(value) || value < MIN_OUTPUT_TOKENS || value > MAX_OUTPUT_TOKENS) {
      invalid[field.key] = '请填写 1,024–65,535 之间的整数。'
    }
  }
  fieldErrors.value = invalid
  if (Object.keys(invalid).length) {
    focusFormFeedback(formRoot.value)
    return false
  }
  return true
}
async function load() {
  if (saving.value) return
  const current = ++sequence
  loaded.value = false
  loading.value = true
  emit('configured', null)
  try {
    const config = await getFeatureModels()
    if (!active || current !== sequence) return
    draft.value = { ...config }
    fieldErrors.value = {}
    loaded.value = true
    emit('configured', config)
  } catch {
    if (active && current === sequence) showRequestError()
  } finally {
    if (active && current === sequence) loading.value = false
  }
}
async function save() {
  if (saving.value || loading.value || !loaded.value || !props.connectionsLoaded || props.connectionsLoading) return
  if (!validate()) return
  const current = ++sequence
  saving.value = true
  try {
    const config = await updateFeatureModels({ ...draft.value })
    if (!active || current !== sequence) return
    draft.value = { ...config }
    emit('configured', config)
    ElMessage({ message: '保存成功', type: 'success', placement: 'top', offset: 16, duration: 3000, grouping: true })
  } catch {
    if (active && current === sequence) showRequestError()
  } finally {
    if (active && current === sequence) saving.value = false
  }
}
onMounted(() => { void load() })
onUnmounted(() => { active = false; sequence++ })
</script>

<template>
  <section class="ui-panel ai-feature-section" aria-label="独立功能模型">
    <div class="section-header"><h2>独立功能模型</h2><ElButton :loading="loading" :disabled="saving" @click="load">刷新</ElButton></div>
    <p v-if="loading" class="ui-text-muted">正在读取功能配置...</p>
    <p v-else-if="!loaded" class="ui-load-retry">功能配置未加载。<ElButton @click="load">重试</ElButton></p>
    <form v-else ref="formRoot" class="ui-form ai-feature-form" novalidate @submit.prevent="save">
      <div class="field-grid">
        <div class="field">
          <label for="feature-chat-model">AI 对话与运维工具 <em>*</em></label>
          <ElSelect id="feature-chat-model" v-model="chatChoice" :disabled="disabled">
            <ElOption :label="`沿用主模型（${primary ? `${primary.name} / ${primary.model}` : '未设置主模型'}）`" value="primary" />
            <ElOption v-for="item in connections" :key="item.id" :label="connectionLabel(item)" :value="item.id" />
            <ElOption v-if="missing(draft.chat_connection_id)" :label="`连接 #${draft.chat_connection_id} 已不存在`" :value="draft.chat_connection_id!" disabled />
          </ElSelect>
        </div>
        <div class="field">
          <label for="feature-report-model">巡检 AI 报告 <em>*</em></label>
          <ElSelect id="feature-report-model" v-model="reportChoice" :disabled="disabled">
            <ElOption :label="`沿用主模型（${primary ? `${primary.name} / ${primary.model}` : '未设置主模型'}）`" value="primary" />
            <ElOption v-for="item in connections" :key="item.id" :label="connectionLabel(item)" :value="item.id" />
            <ElOption v-if="missing(draft.inspection_report_connection_id)" :label="`连接 #${draft.inspection_report_connection_id} 已不存在`" :value="draft.inspection_report_connection_id!" disabled />
          </ElSelect>
        </div>
      </div>
      <div class="field-grid">
        <div v-for="field in tokenFields" :key="field.key" class="field" :class="{ 'is-error': !!fieldErrors[field.key] }">
          <label :id="`${fieldId(field.key)}-label`" :for="fieldId(field.key)">{{ field.label }} <em>*</em></label>
          <ElInputNumber
            :id="fieldId(field.key)"
            :name="field.key"
            v-model="draft[field.key]"
            v-native-field-aria
            autocomplete="off"
            :min="MIN_OUTPUT_TOKENS"
            :max="MAX_OUTPUT_TOKENS"
            :controls="false"
            :disabled="disabled"
            class="full-width"
            role="group"
            :aria-labelledby="`${fieldId(field.key)}-label`"
            :aria-invalid="!!fieldErrors[field.key]"
            :aria-describedby="`${formId}-token-hint${fieldErrors[field.key] ? ` ${fieldId(field.key)}-error` : ''}`"
            @update:model-value="clearField(field.key)"
          />
          <FieldError :id="`${fieldId(field.key)}-error`" :message="fieldErrors[field.key] || ''" />
        </div>
      </div>
      <p :id="`${formId}-token-hint`" class="ui-field-hint">范围 1,024–65,535，请填写所用模型支持的输出额度。此值按单次模型调用计算，实际响应仍受响应大小和时限限制。</p>
      <p class="ui-field-hint">保存后用于后续对话请求和新提交的巡检报告；正在生成的内容沿用开始时的额度。</p>
      <p v-if="!connectionsLoaded" class="ui-text-muted">连接列表未加载，暂不能修改或保存功能配置。</p>
      <div><ElButton native-type="submit" type="primary" :loading="saving" :disabled="disabled || loading">保存配置</ElButton></div>
    </form>
  </section>
</template>
