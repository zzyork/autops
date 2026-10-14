<script setup lang="ts">
import { ref } from 'vue'
import { ElButton, ElDialog } from 'element-plus'
import OperationsWorkbench from '@/components/OperationsWorkbench.vue'
import type { Host } from '@/types/api'

defineProps<{ modelValue: boolean; host: Host | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const busy = ref(false)

function updateVisible(visible: boolean) {
  if (!visible && busy.value) return
  emit('update:modelValue', visible)
}
</script>

<template>
  <ElDialog :model-value="modelValue" append-to-body align-center :title="host ? `更改主机名 · ${host.name}` : '更改主机名'" width="min(1000px, 94vw)" class="hostname-operation-dialog" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" destroy-on-close @update:model-value="updateVisible">
    <OperationsWorkbench v-if="modelValue && host" module="hostname" :fixed-host="host" initial-action="set" embedded @busy="busy = $event" />
    <template #footer><ElButton :disabled="busy" @click="updateVisible(false)">关闭</ElButton></template>
  </ElDialog>
</template>
