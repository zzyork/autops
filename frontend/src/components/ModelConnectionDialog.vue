<script setup lang="ts">
import { onUnmounted, reactive, ref, watch } from 'vue'
import { ElButton, ElDialog, ElInput, ElOption, ElSelect, ElSwitch } from 'element-plus'
import { createConnection, updateConnection } from '@/api/ai'
import { showRequestError } from '@/components/feedback'
import type { ModelConnection, ModelConnectionInput } from '@/types/ai'

const props = defineProps<{ modelValue: boolean; connection: ModelConnection | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [] }>()
const form = reactive<ModelConnectionInput>({ name: '', protocol: 'openai_compatible', base_url: '', model: '', api_key: '', is_default: false, is_backup: false })
const saving = ref(false)
const error = ref('')
const invalidField = ref<'name' | 'base_url' | 'model' | null>(null)
let revision = 0
onUnmounted(() => { revision++ })

watch(() => [props.modelValue, props.connection] as const, () => {
  revision++
  if (!props.modelValue) return
  Object.assign(form, props.connection ? {
    name: props.connection.name, protocol: props.connection.protocol, base_url: props.connection.base_url,
    model: props.connection.model, api_key: '', is_default: props.connection.is_default, is_backup: props.connection.is_backup,
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
    return
  }
  let url: URL
  try { url = new URL(form.base_url.trim()) } catch { invalidField.value = 'base_url'; error.value = '请输入有效的 HTTP/HTTPS 服务地址。'; return }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    invalidField.value = 'base_url'
    error.value = '服务地址只能使用 HTTP/HTTPS，不能包含凭据、查询或片段。'
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
  <ElDialog :model-value="modelValue" :title="connection ? '编辑模型连接' : '新增模型连接'" width="min(440px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving" @update:model-value="emit('update:modelValue', $event)">
    <div class="asset-form ai-model-form">
      <label class="field" :class="{ 'is-error': invalidField === 'name' }"><span>名称 <em>*</em></span><ElInput v-model="form.name" maxlength="100" placeholder="连接名称" @input="error = ''; invalidField = null" /></label>
      <label class="field"><span>协议 <em>*</em></span><ElSelect v-model="form.protocol"><ElOption label="OpenAI 兼容" value="openai_compatible" /><ElOption label="Anthropic" value="anthropic" /></ElSelect></label>
      <label class="field" :class="{ 'is-error': invalidField === 'base_url' }"><span>服务地址 <em>*</em></span><ElInput v-model="form.base_url" placeholder="https://example.com/v1" @input="error = ''; invalidField = null" /></label>
      <label class="field" :class="{ 'is-error': invalidField === 'model' }"><span>模型 ID <em>*</em></span><ElInput v-model="form.model" placeholder="模型标识" @input="error = ''; invalidField = null" /></label>
      <label class="field"><span>API Key</span><ElInput v-model="form.api_key" type="password" show-password autocomplete="new-password" :placeholder="connection?.has_api_key ? '留空保留已保存的密钥' : '本地服务可留空'" /></label>
      <label class="ai-default-field">设为主模型 <ElSwitch v-model="form.is_default" @change="form.is_default && (form.is_backup = false)" /></label>
      <label class="ai-default-field">设为备用模型 <ElSwitch v-model="form.is_backup" @change="form.is_backup && (form.is_default = false)" /></label>
      <p v-if="error" class="ssh-field-error" role="alert">{{ error }}</p>
    </div>
    <template #footer><ElButton :disabled="saving" @click="emit('update:modelValue', false)">取消</ElButton><ElButton type="primary" :loading="saving" @click="save">保存</ElButton></template>
  </ElDialog>
</template>
