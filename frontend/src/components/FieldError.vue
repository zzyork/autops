<script setup lang="ts">
defineProps<{ id: string; message: string }>()
</script>

<template>
  <p v-if="message" :id="id" class="field-error" role="alert">
    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="1.5" />
      <path d="M10 5.5v5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      <circle cx="10" cy="14" r="0.9" fill="currentColor" />
    </svg>
    <span>{{ message }}</span>
  </p>
</template>

<style scoped>
.field-error { display: flex; align-items: flex-start; gap: var(--ui-space-2); margin: 0; color: var(--ui-danger); font-size: var(--ui-font-size-small); line-height: var(--ui-line-height-small); overflow-wrap: anywhere; }
.field-error svg { flex: none; width: var(--ui-icon-size); height: var(--ui-icon-size); margin-top: 2px; }
</style>
