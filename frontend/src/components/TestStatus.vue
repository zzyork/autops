<script setup lang="ts">
import { ElTooltip } from 'element-plus'
import type { TestStatus } from '@/types/testStatus'

withDefaults(defineProps<{ status: TestStatus; description: string; focusable?: boolean; tooltipVisible?: boolean }>(), {
  focusable: true,
  tooltipVisible: undefined,
})
</script>

<template>
  <ElTooltip :content="description" placement="top" :trigger="['hover', 'focus']" :visible="tooltipVisible">
    <span class="test-status" :class="`is-${status}`" role="img" :aria-label="description" :tabindex="focusable ? 0 : undefined">
      <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
        <circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="1.5" />
        <path v-if="status === 'passed'" d="M6 10l2.5 2.5L14 7" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
        <path v-else-if="status === 'failed'" d="M7 7l6 6M13 7l-6 6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
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
    </span>
  </ElTooltip>
</template>

<style scoped>
.test-status { display: inline-flex; align-items: center; justify-content: center; flex: 0 0 var(--ui-inline-control-height); width: var(--ui-inline-control-height); height: var(--ui-inline-control-height); vertical-align: middle; }
.test-status svg { width: 18px; height: 18px; }
.test-status text { font-size: var(--ui-font-size-code); font-weight: 600; }
.test-status.is-untested, .test-status.is-unavailable { color: var(--ui-text-muted); }
.test-status.is-pending { color: var(--ui-info); }
.test-status.is-passed { color: var(--ui-success); }
.test-status.is-failed { color: var(--ui-danger); }
.test-status.is-warning { color: var(--ui-warning); }
.test-status:focus-visible {
  outline: var(--ui-focus-width) solid var(--ui-primary);
  outline-offset: var(--ui-focus-offset);
}
</style>
