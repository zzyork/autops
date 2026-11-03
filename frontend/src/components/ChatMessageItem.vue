<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElTag } from 'element-plus'
import ChatMessageActionButton from '@/components/ChatMessageActionButton.vue'
import ChatMarkdownContent from '@/components/ChatMarkdownContent.vue'
import type { ChatMessage } from '@/types/ai'

const props = defineProps<{
  message: Pick<ChatMessage, 'role' | 'content'> & Partial<Pick<ChatMessage, 'id' | 'status'>>
  resultConfirmed?: boolean
  actionsDisabled?: boolean
  retryable?: boolean
  editing?: boolean
}>()
const emit = defineEmits<{ edit: []; retry: []; branch: [] }>()
const editAction = ref<InstanceType<typeof ChatMessageActionButton> | null>(null)
const copyState = ref<'idle' | 'copying' | 'copied' | 'failed' | 'unavailable'>('idle')
const copyFeedback = computed(() => {
  if (copyState.value === 'copied') return '已复制'
  if (copyState.value === 'failed') return '复制失败，请检查浏览器剪贴板权限。'
  if (copyState.value === 'unavailable') return '当前环境不支持剪贴板复制，请使用 HTTPS 或 localhost。'
  return ''
})
let active = true
onUnmounted(() => { active = false })

watch(() => props.editing, (editing, wasEditing) => {
  if (!editing && wasEditing) editAction.value?.focus()
}, { flush: 'post' })

watch(() => props.message.content, () => { copyState.value = 'idle' })

async function copy(): Promise<void> {
  if (copyState.value === 'copying') return
  if (!navigator.clipboard?.writeText) {
    copyState.value = 'unavailable'
    return
  }
  copyState.value = 'copying'
  const content = props.message.content
  try {
    await navigator.clipboard.writeText(content)
    if (active && props.message.content === content) copyState.value = 'copied'
  } catch {
    if (active && props.message.content === content) copyState.value = 'failed'
  }
}
</script>

<template>
  <div class="ai-message" :class="[`ai-message-${message.role}`, { 'ai-message-editing': editing }]">
    <span class="ai-message-role">
      {{ message.role === 'user' ? '你' : '助手' }}
      <ElTag
        v-if="message.status && message.status !== 'completed'"
        type="info"
        size="small"
        class="ui-execution-status"
        :data-execution-state="message.status === 'interrupted' || resultConfirmed ? 'incomplete' : undefined"
      >
        <template v-if="message.status === 'interrupted'">已中断</template>
        <template v-else-if="resultConfirmed">发送失败</template>
        <template v-else>发送状态待确认</template>
      </ElTag>
    </span>
    <slot v-if="editing" name="editor" />
    <ChatMarkdownContent v-else-if="message.role === 'assistant'" class="ai-message-content" :content="message.content" />
    <p v-else class="ai-message-content ai-message-text">{{ message.content }}</p>
    <div v-if="message.id && !editing" class="ai-message-actions" role="group" aria-label="消息操作">
      <ChatMessageActionButton label="复制" :disabled="copyState === 'copying'" @click="copy">
        <svg class="ai-message-action-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M15 6V4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h2" /></svg>
      </ChatMessageActionButton>
      <ChatMessageActionButton v-if="message.role === 'user'" ref="editAction" label="编辑" :disabled="actionsDisabled" @click="emit('edit')">
        <svg class="ai-message-action-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m15 5 4 4M4 20l5-1L21 7a2.8 2.8 0 0 0-4-4L5 15l-1 5Z" /></svg>
      </ChatMessageActionButton>
      <ChatMessageActionButton v-if="retryable" label="重试" :disabled="actionsDisabled" @click="emit('retry')">
        <svg class="ai-message-action-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20 7v5h-5M4 17v-5h5M6.1 6.1A8 8 0 0 1 20 12M4 12a8 8 0 0 0 13.9 5.9" /></svg>
      </ChatMessageActionButton>
      <ChatMessageActionButton label="分支对话" :disabled="actionsDisabled" @click="emit('branch')">
        <svg class="ai-message-action-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="6" cy="5" r="2" /><circle cx="6" cy="19" r="2" /><circle cx="18" cy="5" r="2" /><path d="M6 7v10M18 7a6 6 0 0 1-6 6H6" /></svg>
      </ChatMessageActionButton>
    </div>
    <p v-if="copyFeedback && !editing" class="ai-message-action-feedback" :class="{ 'ai-message-action-error': copyState !== 'copied' }" role="status">{{ copyFeedback }}</p>
  </div>
</template>
