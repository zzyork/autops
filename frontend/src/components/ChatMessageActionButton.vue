<script setup lang="ts">
import { ref } from 'vue'
import { ElButton, ElTooltip } from 'element-plus'

const props = defineProps<{
  label: string
  disabled?: boolean
  loading?: boolean
  primary?: boolean
  nativeType?: 'button' | 'submit'
}>()
const emit = defineEmits<{ click: [event: MouseEvent] }>()
const tooltip = ref<InstanceType<typeof ElTooltip> | null>(null)
const button = ref<InstanceType<typeof ElButton> | null>(null)

function click(event: MouseEvent): void {
  if (props.disabled || props.loading) return
  tooltip.value?.onClose(event)
  emit('click', event)
}

function focus(): void {
  const element = button.value?.ref
  if (element && !element.disabled) element.focus()
}

defineExpose({ focus })
</script>

<template>
  <!-- Tooltip 不接管 Enter / Space，保留按钮的原生键盘操作。 -->
  <ElTooltip ref="tooltip" :content="label" placement="top" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
    <span class="ai-message-action-trigger" @focusin="tooltip?.onOpen($event)" @focusout="tooltip?.onClose($event)">
      <ElButton
        ref="button"
        class="ai-message-action-button"
        :text="!primary"
        :type="primary ? 'primary' : undefined"
        :native-type="nativeType ?? 'button'"
        :disabled="disabled"
        :loading="loading"
        :aria-label="label"
        @click="click"
      >
        <slot v-if="!loading" />
      </ElButton>
    </span>
  </ElTooltip>
</template>

<style scoped>
.ai-message-action-trigger {
  display: inline-flex;
  flex: none;
}

.ai-message-action-button.el-button {
  width: var(--ui-icon-control-size);
  height: var(--ui-icon-control-size);
  min-height: var(--ui-icon-control-size);
  padding: var(--ui-space-1);
}

.ai-message-action-button.el-button.is-text {
  --el-button-text-color: var(--ui-text-secondary);
  --el-button-hover-text-color: var(--ui-primary);
}
</style>
