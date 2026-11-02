<script setup lang="ts">
import { onMounted, ref, useId } from 'vue'
import { ElInput } from 'element-plus'
import ChatMessageActionButton from '@/components/ChatMessageActionButton.vue'
import FieldError from '@/components/FieldError.vue'
import { focusFormFeedback } from '@/components/formFeedback'

const props = defineProps<{ busy: boolean; disabled: boolean; requestError: string; sessionsLoading: boolean }>()
const emit = defineEmits<{ submit: [content: string]; close: []; refreshSessions: [] }>()
const draft = defineModel<string>({ required: true })
const error = ref('')
const formRoot = ref<HTMLElement | null>(null)
const editor = ref<InstanceType<typeof ElInput> | null>(null)
const inputId = useId()
const MAX_MESSAGE_LENGTH = 8000

onMounted(() => {
  editor.value?.focus()
  formRoot.value?.scrollIntoView({ block: 'nearest' })
})

function submit(): void {
  if (props.busy || props.disabled) return
  const content = draft.value.trim()
  if (!content || content.length > MAX_MESSAGE_LENGTH) {
    error.value = `消息须填写且不超过 ${MAX_MESSAGE_LENGTH} 字符。`
    focusFormFeedback(formRoot.value)
    return
  }
  error.value = ''
  emit('submit', content)
}

function handleKeydown(event: Event): void {
  if (!(event instanceof KeyboardEvent) || event.isComposing || event.keyCode === 229) return
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    close()
    return
  }
  if (event.key !== 'Enter' || !(event.ctrlKey || event.metaKey)) return
  event.preventDefault()
  submit()
}

function close(): void {
  if (!props.busy) emit('close')
}
</script>

<template>
  <form ref="formRoot" class="ai-message-content ai-message-editor" aria-label="编辑消息" @submit.prevent="submit" @keydown="handleKeydown">
    <ElInput
      :id="inputId"
      ref="editor"
      v-model="draft"
      type="textarea"
      :autosize="{ minRows: 3, maxRows: 12 }"
      :maxlength="MAX_MESSAGE_LENGTH"
      show-word-limit
      :disabled="busy"
      name="edited_message"
      autocomplete="off"
      aria-label="编辑消息内容"
      :aria-invalid="!!error"
      :aria-describedby="`${inputId}-hint${error ? ` ${inputId}-error` : ''}`"
      @input="error = ''"
    />
    <FieldError v-if="error" :id="`${inputId}-error`" :message="error" />
    <p :id="`${inputId}-hint`" class="ui-field-hint">在新分支发送，原对话会保留。Ctrl / ⌘ + Enter 发送，Esc 取消。</p>
    <div v-if="requestError" class="ai-message-edit-recovery">
      <p class="ai-message-action-error" role="alert">{{ requestError }}</p>
      <ChatMessageActionButton label="刷新会话列表" :loading="sessionsLoading" :disabled="busy || sessionsLoading" @click="emit('refreshSessions')">
        <svg class="ai-message-action-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20 7v5h-5M4 17v-5h5M6.1 6.1A8 8 0 0 1 20 12M4 12a8 8 0 0 0 13.9 5.9" /></svg>
      </ChatMessageActionButton>
    </div>
    <p v-else-if="disabled && !busy" class="ui-field-hint" role="status">当前会话暂不可操作，请先确认运行状态。</p>
    <div class="ai-message-editor-actions" role="group" aria-label="编辑操作">
      <ChatMessageActionButton label="取消编辑" :disabled="busy" @click="close">
        <svg class="ai-message-action-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m6 6 12 12M18 6 6 18" /></svg>
      </ChatMessageActionButton>
      <ChatMessageActionButton label="在新分支发送" primary native-type="submit" :loading="busy" :disabled="disabled || busy || !draft.trim()">
        <svg class="ai-message-action-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 20V4m-6 6 6-6 6 6" /></svg>
      </ChatMessageActionButton>
    </div>
  </form>
</template>
