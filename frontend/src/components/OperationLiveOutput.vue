<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ElButton, ElOption, ElSelect, ElTag } from 'element-plus'
import { hostLabels, statusType, stepLabels } from './operationDisplay'
import DisclosurePanel from './DisclosurePanel.vue'
import type { OperationSnapshot, OperationTask } from '@/types/operations'

const props = defineProps<{ task: OperationTask; snapshot: OperationSnapshot | null; hostId: number; allowedHostId?: number; state: 'idle' | 'connecting' | 'connected' | 'disconnected' | 'done'; detailsPending?: boolean }>()
const emit = defineEmits<{ 'update:hostId': [id: number]; reconnect: [] }>()
const stepPosition = ref<number | null>(null)
const expanded = ref(true)
const output = ref<HTMLElement | null>(null)
const following = ref(true)
const selectedHost = computed(() => props.task.hosts.find((host) => host.host_id === props.hostId))
const liveHost = computed(() => props.snapshot?.hosts.find((host) => host.host_id === props.hostId))
const steps = computed(() => liveHost.value?.steps ?? selectedHost.value?.steps.map((step, position) => ({ ...step, position, stdout: step.stdout ?? '', stderr: step.stderr ?? '' })) ?? [])
const selectedStep = computed(() => steps.value.find((step) => step.position === stepPosition.value)
  ?? steps.value.find((step) => step.status === 'running')
  ?? steps.value.filter((step) => step.status !== 'pending').at(-1)
  ?? steps.value[0])
watch(() => [props.task.id, props.hostId], () => { stepPosition.value = null; following.value = true })
watch(() => [selectedStep.value?.stdout, selectedStep.value?.stderr], async () => {
  if (!following.value || !expanded.value) return
  await nextTick()
  output.value?.scrollTo({ top: output.value.scrollHeight })
}, { flush: 'post' })
function trackScroll() {
  const element = output.value
  if (element) following.value = element.scrollHeight - element.scrollTop - element.clientHeight < 24
}
function follow() { following.value = true; output.value?.scrollTo({ top: output.value.scrollHeight }) }
</script>

<template>
  <section class="host-section operation-section" aria-label="执行输出">
    <div class="section-header"><h2>执行输出</h2><span role="status">{{ detailsPending ? '已收到任务终态，详情待获取' : state === 'connecting' ? '连接中' : state === 'disconnected' ? '实时查看已断开' : state === 'connected' ? '实时查看中' : state === 'done' || task.status !== 'queued' && task.status !== 'running' ? '执行已结束' : '查看已暂停' }}</span></div>
    <div class="operation-actions">
      <label v-if="allowedHostId === undefined && task.hosts.length > 1">主机 <ElSelect :model-value="hostId" :disabled="detailsPending" aria-label="输出主机" @update:model-value="emit('update:hostId', $event)"><ElOption v-for="host in task.hosts" :key="host.host_id" :label="host.host_name" :value="host.host_id" /></ElSelect></label>
      <ElTag v-if="liveHost || selectedHost" :type="statusType((liveHost ?? selectedHost)!.status)">{{ hostLabels[(liveHost ?? selectedHost)!.status] }}</ElTag>
      <ElButton v-if="(state === 'disconnected' || state === 'idle') && (task.status === 'queued' || task.status === 'running')" @click="emit('reconnect')">重新连接</ElButton>
    </div>
    <div v-if="steps.length" class="operation-actions operation-step-picker"><label>步骤 <ElSelect :model-value="selectedStep?.position" aria-label="输出步骤" @update:model-value="stepPosition = $event"><ElOption v-for="step in steps" :key="step.position" :label="step.title" :value="step.position" /></ElSelect></label><ElTag v-if="selectedStep" :type="statusType(selectedStep.status)">{{ stepLabels[selectedStep.status] }}</ElTag></div>
    <DisclosurePanel v-model="expanded" label="日志">
      <div ref="output" class="operation-live-scroll" tabindex="0" aria-label="命令输出" @scroll="trackScroll">
        <template v-if="selectedStep"><div v-if="selectedStep.stdout" class="operation-output"><span>标准输出</span><pre>{{ selectedStep.stdout }}</pre></div><div v-if="selectedStep.stderr" class="operation-output operation-error"><span>错误输出</span><pre>{{ selectedStep.stderr }}</pre></div><p v-if="!selectedStep.stdout && !selectedStep.stderr">{{ selectedStep.status === 'running' ? '执行中，暂无输出' : selectedStep.status === 'pending' ? '等待执行' : '此步骤无输出' }}</p><span v-if="selectedStep.exit_status !== null">退出码 {{ selectedStep.exit_status }}</span></template>
        <p v-else>{{ task.status === 'queued' ? '等待执行' : '暂无步骤输出' }}</p>
      </div>
      <ElButton v-if="!following" @click="follow">回到底部</ElButton>
    </DisclosurePanel>
  </section>
</template>
