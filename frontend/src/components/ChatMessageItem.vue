<script setup lang="ts">
import { ElTag } from 'element-plus'
import type { ChatMessage } from '@/types/ai'

defineProps<{
  message: ChatMessage
  resultConfirmed: boolean
}>()
</script>

<template>
  <div class="ai-message" :class="`ai-message-${message.role}`">
    <span class="ai-message-role">
      {{ message.role === 'user' ? '你' : '助手' }}
      <ElTag
        v-if="message.status !== 'completed'"
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
    <p>{{ message.content }}</p>
  </div>
</template>
