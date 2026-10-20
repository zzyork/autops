<script setup lang="ts">
import { ref, useId } from 'vue'
import { ElButton } from 'element-plus'

const props = defineProps<{ label: string; context?: string }>()
const expanded = defineModel<boolean>({ default: false })
const contentId = `disclosure-${useId()}`
const button = ref<InstanceType<typeof ElButton>>()
const content = ref<HTMLElement>()

function toggle() {
  if (expanded.value && content.value?.contains(document.activeElement)) button.value?.$el.focus()
  expanded.value = !expanded.value
}
</script>

<template>
  <div class="ui-disclosure">
    <ElButton ref="button" native-type="button" class="ui-disclosure-toggle" :aria-expanded="expanded" :aria-controls="contentId" :aria-label="context ? `${expanded ? '收起' : '展开'}${label}：${props.context}` : undefined" @click="toggle">
      <svg class="ui-disclosure-arrow" :class="{ 'is-expanded': expanded }" viewBox="0 0 14 14" aria-hidden="true" focusable="false"><path d="m5 3 4 4-4 4" /></svg>
      <span>{{ expanded ? '收起' : '展开' }}{{ label }}</span>
    </ElButton>
    <div :id="contentId" ref="content" v-show="expanded" class="ui-disclosure-content">
      <slot v-if="expanded" />
    </div>
  </div>
</template>

<style scoped>
.ui-disclosure { min-width: 0; }
.ui-disclosure .ui-disclosure-toggle { --el-button-hover-bg-color: var(--ui-row-hover); min-height: 36px; height: auto; padding: var(--ui-space-2) var(--ui-space-3); white-space: normal; text-align: left; }
.ui-disclosure-toggle > :deep(span) { display: inline-flex; align-items: center; gap: var(--ui-space-2); }
.ui-disclosure-arrow { width: var(--ui-icon-size); height: var(--ui-icon-size); flex: none; fill: none; stroke: currentColor; stroke-width: 1.5; }
.ui-disclosure-arrow.is-expanded { transform: rotate(90deg); }
.ui-disclosure-content { margin-top: var(--ui-space-3); min-width: 0; }
</style>
