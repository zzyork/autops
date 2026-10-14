<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCheckbox, ElDialog, ElInput, ElTag } from 'element-plus'
import { hostLabels, operationTime, statusType, stepLabels, taskLabels } from '@/components/operationDisplay'
import type { OperationAction, OperationTask } from '@/types/operations'

const props = defineProps<{ task: OperationTask; action?: OperationAction; canConfirm?: boolean; confirming?: boolean; resolvingHostId?: number | null }>()
const emit = defineEmits<{ confirm: [id: string]; resolve: [id: string, hostId: number, note: string] }>()
const dialog = ref(false)
const acknowledged = ref(false)
const resolveHostId = ref<number | null>(null)
const resolutionNote = ref('')
const remoteStopped = ref(false)
const resolving = computed(() => resolveHostId.value !== null && props.resolvingHostId === resolveHostId.value)
const noteValid = computed(() => resolutionNote.value.trim().length >= 5 && resolutionNote.value.trim().length <= 500)
watch(() => props.task.status, (status) => { if (status !== 'planned') dialog.value = false })
watch(() => props.task.id, () => { dialog.value = false; resolveHostId.value = null })
watch(() => props.task.hosts.find((host) => host.host_id === resolveHostId.value)?.resolved_at, (resolved) => {
  if (resolved) resolveHostId.value = null
})
watch(dialog, (open) => { if (!open) acknowledged.value = false })
watch(resolveHostId, (id) => { if (id === null) { resolutionNote.value = ''; remoteStopped.value = false } })
function closeResolution(open: boolean) {
  if (!open && !resolving.value) resolveHostId.value = null
}
function submitResolution() {
  if (resolveHostId.value === null || resolving.value || !remoteStopped.value || !noteValid.value) return
  emit('resolve', props.task.id, resolveHostId.value, resolutionNote.value.trim())
}
function parameterName(key: string) { return props.action?.fields.find((field) => field.key === key)?.label ?? key }
function parameterValue(value: string | number | boolean | null) {
  return value === null ? '未填写' : typeof value === 'boolean' ? value ? '是' : '否' : String(value)
}
</script>

<template>
  <section class="host-section operation-section" aria-label="任务详情">
    <div class="section-header"><h2>{{ canConfirm ? '计划预览' : '任务详情' }} · {{ task.title }}</h2><ElTag :type="statusType(task.status)">{{ taskLabels[task.status] }}</ElTag></div>
    <dl class="operation-meta"><div><dt>任务编号</dt><dd>{{ task.id }}</dd></div><div><dt>创建时间</dt><dd>{{ operationTime(task.created_at) }}</dd></div><div><dt>确认时间</dt><dd>{{ operationTime(task.confirmed_at) }}</dd></div><div><dt>完成时间</dt><dd>{{ operationTime(task.completed_at) }}</dd></div><div><dt>执行权限</dt><dd>{{ task.sudo ? '免密 sudo' : '不使用 sudo' }}</dd></div></dl>
    <ElAlert v-if="task.status === 'unknown'" title="任务结果未知；人工解除主机写操作阻塞不代表本次操作成功，也不会自动重试。" type="warning" :closable="false" show-icon />
    <ElAlert v-if="action?.destructive" :title="`破坏性影响：${action.description}。可能修改或清除目标主机上的现有数据，请逐台核对前置状态与步骤。`" type="warning" :closable="false" show-icon />
    <div class="operation-subsection"><h3>计划参数</h3><dl class="operation-params"><div v-for="(value, key) in task.params" :key="key"><dt>{{ parameterName(String(key)) }}</dt><dd>{{ parameterValue(value) }}</dd></div><div v-if="!Object.keys(task.params).length">无额外参数</div></dl></div>
    <div class="operation-subsection"><h3>目标、前置状态与步骤（{{ task.hosts.length }} 台）</h3>
      <div v-for="host in task.hosts" :key="host.host_id" class="operation-host-result">
        <div class="operation-host-head"><strong>{{ host.host_name }} · {{ host.address }}</strong><ElTag :type="statusType(host.status)" size="small">{{ hostLabels[host.status] }}</ElTag></div>
        <template v-if="host.status === 'unknown'">
          <ElAlert v-if="!host.resolved_at" title="该主机后续写操作已阻塞；必须人工带外核验远端进程已停止，才能解除阻塞。解除不表示本次操作成功，不会自动重试。" type="warning" :closable="false" show-icon />
          <div v-else class="operation-resolution"><span>已于 {{ operationTime(host.resolved_at) }} 人工核对远端进程停止并解除阻塞；本次操作结果仍未知。</span><div class="operation-output"><span>核对说明</span><pre>{{ host.resolution_note }}</pre></div></div>
          <div v-if="!host.resolved_at && task.status !== 'queued' && task.status !== 'running'" class="operation-actions"><ElButton :disabled="resolvingHostId != null" @click="resolveHostId = host.host_id">带外核对并解除阻塞</ElButton></div>
        </template>
        <div class="operation-output"><span>前置状态</span><pre>{{ host.before ?? '未记录' }}</pre></div>
        <div v-if="host.error" class="operation-output operation-error"><span>失败阶段 / 结果</span><pre>{{ host.error }}</pre></div>
        <ol class="operation-steps"><li v-for="(step, index) in host.steps" :key="index"><div class="operation-step-head"><strong>{{ step.title }}</strong><ElTag :type="statusType(step.status)" size="small">{{ stepLabels[step.status] }}</ElTag><span v-if="step.exit_status !== null">退出码 {{ step.exit_status }}</span></div><div v-if="step.stdout" class="operation-output"><span>标准输出</span><pre>{{ step.stdout }}</pre></div><div v-if="step.stderr" class="operation-output operation-error"><span>错误输出</span><pre>{{ step.stderr }}</pre></div></li></ol>
        <div v-if="host.after !== null" class="operation-output"><span>执行后核验</span><pre>{{ host.after }}</pre></div>
      </div>
    </div>
    <div v-if="canConfirm && task.status === 'planned'" class="operation-actions"><ElButton type="primary" :disabled="confirming" @click="dialog = true">核对并确认执行</ElButton></div>
    <ElDialog v-model="dialog" align-center title="确认执行运维计划" width="min(720px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!confirming" :show-close="!confirming">
      <div class="operation-confirm"><p>操作：{{ task.title }}；目标：{{ task.hosts.map((host) => `${host.host_name} (${host.address})`).join('、') }}</p><p>参数：{{ Object.entries(task.params).map(([key, value]) => `${parameterName(key)}=${parameterValue(value)}`).join('；') || '无额外参数' }}</p><p>权限：{{ task.sudo ? '免密 sudo' : '不使用 sudo' }}</p><p v-if="action?.destructive" class="operation-warning">破坏性影响：{{ action.description }}。目标主机上的现有数据或配置可能被修改或清除。</p><ElCheckbox v-model="acknowledged" :disabled="confirming">我已核对目标、参数、前置状态和步骤，并理解执行影响</ElCheckbox></div>
      <template #footer><ElButton :disabled="confirming" @click="dialog = false">取消</ElButton><ElButton type="primary" :loading="confirming" :disabled="!acknowledged" @click="emit('confirm', task.id)">确认执行</ElButton></template>
    </ElDialog>
    <ElDialog :model-value="resolveHostId !== null" align-center title="人工核对并解除写操作阻塞" width="min(440px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!resolving" :show-close="!resolving" @update:model-value="closeResolution">
      <div class="operation-confirm"><p>任务：{{ task.id }}</p><p>主机：{{ task.hosts.find((host) => host.host_id === resolveHostId)?.host_name }}</p><p>仅在带外确认远端进程已停止后解除该主机后续写操作阻塞。本次操作结果仍未知，不会自动重试。</p><label class="field" :class="{ 'is-error': resolutionNote.length > 0 && !noteValid }"><span>核对说明 <em>*</em></span><ElInput v-model="resolutionNote" type="textarea" :rows="4" maxlength="500" show-word-limit :disabled="resolving" :aria-invalid="resolutionNote.length > 0 && !noteValid" /></label><span v-if="resolutionNote.length > 0 && !noteValid" class="operation-field-error">核对说明至少填写 5 个字符。</span><ElCheckbox v-model="remoteStopped" :disabled="resolving">我已带外核对该主机远端进程已停止</ElCheckbox></div>
      <template #footer><ElButton :disabled="resolving" @click="resolveHostId = null">取消</ElButton><ElButton type="primary" :loading="resolving" :disabled="!remoteStopped || !noteValid" @click="submitResolution">解除阻塞</ElButton></template>
    </ElDialog>
  </section>
</template>
