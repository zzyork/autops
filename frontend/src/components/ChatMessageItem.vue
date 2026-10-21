<script setup lang="ts">
import { ElTag } from 'element-plus'
import ChatMarkdownContent from '@/components/ChatMarkdownContent.vue'
import type { ChatMessage } from '@/types/ai'

defineProps<{
  message: Pick<ChatMessage, 'role' | 'content'> & { status?: ChatMessage['status'] }
  resultConfirmed?: boolean
}>()
</script>

<template>
  <div class="ai-message" :class="`ai-message-${message.role}`">
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
    <ChatMarkdownContent v-if="message.role === 'assistant'" class="ai-message-content" :content="message.content" />
    <p v-else class="ai-message-content ai-message-text">{{ message.content }}</p>
  </div>
</template>
