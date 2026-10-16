<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElButton, ElCheckbox, ElDialog } from 'element-plus'
import DisclosurePanel from './DisclosurePanel.vue'
import { operationImpacts, preflightEvidence } from './operationDisplay'
import type { OperationAction, OperationTask } from '@/types/operations'

const props = defineProps<{ task: OperationTask | null; action?: OperationAction; confirming: boolean }>()
const emit = defineEmits<{ close: []; closed: []; confirm: [id: string] }>()
const acknowledged = ref(false)
watch(() => props.task?.id, () => { acknowledged.value = false })
const impact = computed(() => props.task ? operationImpacts[props.task.module][props.task.action] : '')
function close() { if (!props.confirming) emit('close') }
function valueLabel(value: string | number | boolean | null) {
  return value === null ? '未填写' : typeof value === 'boolean' ? value ? '是' : '否' : String(value)
}
</script>

<template>
  <ElDialog :model-value="!!task" append-to-body align-center :title="`确认${task?.title ?? '操作'}`" width="min(720px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!confirming" :show-close="!confirming" @update:model-value="close" @closed="emit('closed')">
    <div v-if="task" class="operation-confirm">
      <div><strong>目标</strong>：{{ task.hosts.map((host) => `${host.host_name} (${host.address})`).join('、') }}</div>
      <div><strong>范围</strong>：{{ task.title }}</div>
      <dl v-if="Object.keys(task.params).length" class="operation-params"><div v-for="(value, key) in task.params" :key="key"><dt>{{ action?.fields.find((field) => field.key === key)?.label ?? key }}</dt><dd>{{ valueLabel(value) }}</dd></div></dl>
      <p class="operation-warning">{{ impact }}</p>
      <DisclosurePanel v-if="task.hosts.some((host) => preflightEvidence(host.before) || host.steps.length)" label="预检详情">
        <div v-for="host in task.hosts" :key="host.host_id" class="operation-output"><strong>{{ host.host_name }}</strong><pre v-if="preflightEvidence(host.before)">{{ preflightEvidence(host.before) }}</pre><span v-for="(step, index) in host.steps" :key="index">{{ step.title }}　</span></div>
      </DisclosurePanel>
      <ElCheckbox v-model="acknowledged" :disabled="confirming">我已核对目标、参数与影响，并确认执行</ElCheckbox>
    </div>
    <template #footer><ElButton :disabled="confirming" @click="close">取消</ElButton><ElButton type="primary" :loading="confirming" :disabled="!acknowledged || !task" @click="task && emit('confirm', task.id)">确认{{ task?.title }}</ElButton></template>
  </ElDialog>
</template>
