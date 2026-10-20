<script setup lang="ts">
import { onUnmounted, reactive, ref, useId, watch } from 'vue'
import { ElButton, ElDialog, ElInput, ElOption, ElSelect, ElSwitch } from 'element-plus'
import { createConnection, updateConnection } from '@/api/ai'
import { showRequestError } from '@/components/feedback'
import FieldError from '@/components/FieldError.vue'
import { focusFormFeedback } from '@/components/formFeedback'
import type { ModelConnection, ModelConnectionInput } from '@/types/ai'

const props = defineProps<{ modelValue: boolean; connection: ModelConnection | null; copySource?: ModelConnection | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [] }>()
const form = reactive<ModelConnectionInput>({ name: '', protocol: 'openai_compatible', base_url: '', model: '', api_key: '', is_default: false, is_backup: false })
const saving = ref(false)
const error = ref('')
const invalidField = ref<'name' | 'base_url' | 'model' | null>(null)
const formRoot = ref<HTMLElement | null>(null)
const errorId = useId()
let revision = 0
onUnmounted(() => { revision++ })

watch(() => [props.modelValue, props.connection, props.copySource] as const, () => {
  revision++
  if (!props.modelValue) return
  const source = props.connection ?? props.copySource
  Object.assign(form, source ? {
    name: source.name, protocol: source.protocol, base_url: source.base_url,
    model: source.model, api_key: '', is_default: source.is_default, is_backup: source.is_backup,
  } : { name: '', protocol: 'openai_compatible', base_url: '', model: '', api_key: '', is_default: false, is_backup: false })
  saving.value = false
  error.value = ''
  invalidField.value = null
}, { immediate: true })

async function save() {
  if (saving.value) return
  if (!form.name.trim() || !form.base_url.trim() || !form.model.trim()) {
    invalidField.value = !form.name.trim() ? 'name' : !form.base_url.trim() ? 'base_url' : 'model'
    error.value = '请填写名称、服务地址和模型 ID。'
    focusFormFeedback(formRoot.value)
    return
  }
  let url: URL
  try { url = new URL(form.base_url.trim()) } catch { invalidField.value = 'base_url'; error.value = '请输入有效的 HTTP/HTTPS 服务地址。'; focusFormFeedback(formRoot.value); return }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    invalidField.value = 'base_url'
    error.value = '服务地址只能使用 HTTP/HTTPS，不能包含凭据、查询或片段。'
    focusFormFeedback(formRoot.value)
    return
  }
  error.value = ''
  invalidField.value = null
  saving.value = true
  const current = revision
  const input: ModelConnectionInput = { ...form, name: form.name.trim(), base_url: form.base_url.trim(), model: form.model.trim() }
  try {
    if (props.connection) await updateConnection(props.connection.id, input)
    else await createConnection(input)
    if (current !== revision) return
    emit('update:modelValue', false)
    emit('saved')
  } catch {
    if (current === revision) showRequestError()
  } finally {
    if (current === revision) saving.value = false
  }
}
</script>

<template>
  <ElDialog :model-value="modelValue" :title="connection ? '编辑模型连接' : '新增模型连接'" width="min(var(--ui-dialog-width), calc(100vw - 32px))" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving" @update:model-value="emit('update:modelValue', $event)">
    <div ref="formRoot" class="asset-form ai-model-form">
      <label class="field" :class="{ 'is-error': invalidField === 'name' }"><span>名称 <em>*</em></span><ElInput v-model="form.name" maxlength="100" placeholder="连接名称" :aria-invalid="invalidField === 'name'" :aria-describedby="invalidField === 'name' ? `${errorId}-name` : undefined" @input="error = ''; invalidField = null" /></label>
      <FieldError v-if="invalidField === 'name'" :id="`${errorId}-name`" :message="error" />
      <label class="field"><span>协议 <em>*</em></span><ElSelect v-model="form.protocol"><ElOption label="OpenAI 兼容" value="openai_compatible" /><ElOption label="Anthropic" value="anthropic" /></ElSelect></label>
      <label class="field" :class="{ 'is-error': invalidField === 'base_url' }"><span>服务地址 <em>*</em></span><ElInput v-model="form.base_url" placeholder="https://example.com/v1" :aria-invalid="invalidField === 'base_url'" :aria-describedby="invalidField === 'base_url' ? `${errorId}-url` : undefined" @input="error = ''; invalidField = null" /></label>
      <FieldError v-if="invalidField === 'base_url'" :id="`${errorId}-url`" :message="error" />
      <label class="field" :class="{ 'is-error': invalidField === 'model' }"><span>模型 ID <em>*</em></span><ElInput v-model="form.model" placeholder="模型标识" :aria-invalid="invalidField === 'model'" :aria-describedby="invalidField === 'model' ? `${errorId}-model` : undefined" @input="error = ''; invalidField = null" /></label>
      <FieldError v-if="invalidField === 'model'" :id="`${errorId}-model`" :message="error" />
      <label class="field"><span>API Key</span><ElInput v-model="form.api_key" type="password" show-password autocomplete="new-password" :placeholder="connection?.has_api_key ? '留空保留已保存的密钥' : '本地服务可留空'" /></label>
      <p v-if="!connection && copySource?.has_api_key" class="host-secondary">已保存的 API Key 无法复制，请重新填写。</p>
      <label class="ai-default-field">设为主模型 <ElSwitch v-model="form.is_default" @change="form.is_default && (form.is_backup = false)" /></label>
      <label class="ai-default-field">设为备用模型 <ElSwitch v-model="form.is_backup" @change="form.is_backup && (form.is_default = false)" /></label>
    </div>
    <template #footer><ElButton :disabled="saving" @click="emit('update:modelValue', false)">取消</ElButton><ElButton type="primary" :loading="saving" @click="save">保存</ElButton></template>
  </ElDialog>
</template>
