<script setup lang="ts">
import { computed } from 'vue'
import { ElTooltip } from 'element-plus'
import type { TestStatus } from '@/types/testStatus'
import type { ExecutionState } from '@/types/executionStatus'

const props = withDefaults(defineProps<{
  status: TestStatus
  description: string
  label?: string
  focusable?: boolean
  tooltipVisible?: boolean
}>(), {
  label: '',
  focusable: true,
  tooltipVisible: undefined,
})

const EXECUTION_STATES: Record<TestStatus, ExecutionState | null> = {
  untested: 'not-started',
  queued: 'not-started',
  pending: 'in-progress',
  passed: 'completed',
  failed: 'incomplete',
  warning: null,
  unavailable: null,
}
const executionState = computed(() => EXECUTION_STATES[props.status])
</script>

<template>
  <ElTooltip :content="description" placement="top" :trigger="['hover', 'focus']" :visible="tooltipVisible">
    <span
      class="test-status ui-execution-status"
      :class="[`is-${status}`, { 'has-label': label, 'ui-execution-notice': label }]"
      :data-execution-state="executionState"
      role="img"
      :aria-label="description"
      :tabindex="focusable ? 0 : undefined"
    >
      <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
        <circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="1.5" />
        <path v-if="status === 'passed'" d="M6 10l2.5 2.5L14 7" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
        <path v-else-if="status === 'failed'" d="M7 7l6 6M13 7l-6 6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
        <path v-else-if="status === 'queued'" d="M6 10h8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
        <g v-else-if="status === 'untested' || status === 'unavailable'">
          <path d="M7.5 8a2.5 2.5 0 0 1 5 0c0 1.5-2.5 1.5-2.5 3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          <circle cx="10" cy="14.5" r="0.75" fill="currentColor" />
        </g>
        <g v-else-if="status === 'pending'" fill="currentColor">
          <circle cx="6.5" cy="10" r="0.9" />
          <circle cx="10" cy="10" r="0.9" />
          <circle cx="13.5" cy="10" r="0.9" />
        </g>
        <text v-else x="10" y="10.5" text-anchor="middle" dominant-baseline="middle" fill="currentColor">!</text>
      </svg>
      <span v-if="label">{{ label }}</span>
    </span>
  </ElTooltip>
</template>

<style scoped>
.test-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 var(--ui-inline-control-height);
  width: var(--ui-inline-control-height);
  height: var(--ui-inline-control-height);
  vertical-align: middle;
}

.test-status.has-label {
  flex: initial;
  width: auto;
  height: auto;
  min-height: var(--ui-inline-control-height);
  max-width: 100%;
  gap: var(--ui-space-2);
}

.test-status svg {
  flex: none;
  width: 18px;
  height: 18px;
}

.test-status text {
  font-size: var(--ui-font-size-code);
  font-weight: 600;
}

.test-status.is-unavailable {
  color: var(--ui-text-muted);
}

.test-status.is-warning {
  color: var(--ui-warning);
}

.test-status:focus-visible {
  outline: var(--ui-focus-width) solid var(--ui-primary);
  outline-offset: var(--ui-focus-offset);
}
</style>
