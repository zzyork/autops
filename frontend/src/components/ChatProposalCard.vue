<script setup lang="ts">
import { ElButton, ElTag } from 'element-plus'
import type { InspectionProposal } from '@/types/ai'
import type { CheckId } from '@/types/inspections'

defineProps<{ proposal: InspectionProposal; busy: boolean }>()
const emit = defineEmits<{ decide: [id: string, approve: boolean] }>()
const labels: Record<CheckId, string> = {
  server_info: '基础信息', system_resources: '系统资源', service_status: '服务状态', network_info: '网络信息', log_error: '错误日志',
}
</script>

<template>
  <section class="ai-proposal" :aria-label="`巡检计划 ${proposal.name}`">
    <div class="ai-card-heading"><strong>{{ proposal.name }}</strong><ElTag :type="proposal.status === 'confirmed' ? 'success' : proposal.status === 'cancelled' ? 'info' : 'warning'" size="small">{{ proposal.status === 'confirmed' ? '已确认' : proposal.status === 'cancelled' ? '已拒绝' : '待确认' }}</ElTag></div>
    <template v-if="proposal.status === 'pending'">
      <p>检查项：{{ proposal.checks.map((id) => labels[id]).join('、') }}</p>
      <div class="ai-proposal-hosts"><div v-for="host in proposal.hosts" :key="host.id">{{ host.name }} · {{ host.address }} <span class="ui-text-muted">(ID {{ host.id }} / 版本 {{ host.version }})</span></div></div>
    </template>
    <div v-if="proposal.status === 'pending'" class="ai-proposal-actions"><ElButton :disabled="busy" @click="emit('decide', proposal.id, false)">拒绝</ElButton><ElButton type="primary" :loading="busy" :disabled="busy" @click="emit('decide', proposal.id, true)">确认并执行巡检</ElButton></div>
  </section>
</template>
