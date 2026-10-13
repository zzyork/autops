<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ElButton, ElLoading, ElMessageBox, ElTable, ElTableColumn, ElTag } from 'element-plus'
import AssetsLayout from '@/components/AssetsLayout.vue'
import ModelConnectionDialog from '@/components/ModelConnectionDialog.vue'
import { deleteConnection, listConnections, testConnection } from '@/api/ai'
import { showRequestError } from '@/components/feedback'
import type { CapabilityStatus, ModelConnection } from '@/types/ai'
import '@/styles/ai.css'

const vLoading = ElLoading.directive
const connections = ref<ModelConnection[]>([])
const loaded = ref(false)
const loading = ref(false)
const editing = ref<ModelConnection | null>(null)
const dialog = ref(false)
const operating = ref<number | null>(null)
let active = true
let sequence = 0
const statusLabel: Record<CapabilityStatus, string> = { untested: '未测试', passed: '已通过', failed: '未通过' }
const statusType: Record<CapabilityStatus, 'info' | 'success' | 'danger'> = { untested: 'info', passed: 'success', failed: 'danger' }

async function load() {
  const current = ++sequence
  loading.value = true
  try {
    const items = await listConnections()
    if (!active || current !== sequence) return
    connections.value = items
    loaded.value = true
  } catch {
    if (!active || current !== sequence) return
    loaded.value = false
    showRequestError()
  } finally {
    if (active && current === sequence) loading.value = false
  }
}
function open(connection: ModelConnection | null) { editing.value = connection; dialog.value = true }
async function test(connection: ModelConnection) {
  if (operating.value !== null) return
  operating.value = connection.id
  try {
    const updated = await testConnection(connection.id)
    if (!active) return
    connections.value = connections.value.map((item) => item.id === updated.id ? updated : item)
  } catch { if (active) showRequestError() }
  finally { if (active) operating.value = null }
}
async function remove(connection: ModelConnection) {
  if (operating.value !== null) return
  operating.value = connection.id
  try {
    await ElMessageBox.confirm(`确定删除模型连接“${connection.name}”吗？已有会话可能引用此连接，此操作不可撤销。`, '删除模型连接', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'delete-confirm-button',
    })
  } catch { operating.value = null; return }
  try {
    await deleteConnection(connection.id)
    if (active) void load()
  } catch { if (active) showRequestError() }
  finally { if (active) operating.value = null }
}
onMounted(() => { void load() })
onUnmounted(() => { active = false; sequence++ })
</script>

<template>
  <AssetsLayout title="模型配置" section="配置管理">
    <main class="assets-main">
      <div class="assets-heading"><h1>模型配置</h1></div>
      <section class="host-section" aria-label="模型连接">
        <div class="host-toolbar"><ElButton type="primary" @click="open(null)">新增连接</ElButton><ElButton :loading="loading" @click="load">刷新</ElButton></div>
        <div v-loading="loading" class="host-table-wrap">
          <ElTable v-if="loaded" :data="connections" class="host-table" empty-text="暂无模型连接">
            <ElTableColumn label="连接名称" min-width="170"><template #default="{ row }"><strong>{{ row.name }}</strong><ElTag v-if="row.is_default" size="small" class="ai-default-tag">主模型</ElTag><ElTag v-if="row.is_backup" size="small" type="info" class="ai-default-tag">备用模型</ElTag></template></ElTableColumn>
            <ElTableColumn label="协议 / 模型" min-width="190"><template #default="{ row }">{{ row.protocol === 'anthropic' ? 'Anthropic' : 'OpenAI 兼容' }}<div class="host-secondary">{{ row.model }}</div></template></ElTableColumn>
            <ElTableColumn label="服务地址" min-width="240"><template #default="{ row }"><span class="ai-address">{{ row.base_url }}</span></template></ElTableColumn>
            <ElTableColumn label="密钥" width="90"><template #default="{ row }">{{ row.has_api_key ? '已配置' : '无密钥' }}</template></ElTableColumn>
            <ElTableColumn label="对话 / 工具" width="200"><template #default="{ row }"><ElTag :type="statusType[(row as ModelConnection).chat_status]" size="small">对话 {{ statusLabel[(row as ModelConnection).chat_status] }}</ElTag> <ElTag :type="statusType[(row as ModelConnection).tool_status]" size="small">工具 {{ statusLabel[(row as ModelConnection).tool_status] }}</ElTag></template></ElTableColumn>
            <ElTableColumn label="操作" width="192" fixed="right"><template #default="{ row }"><ElButton link type="primary" :loading="operating === row.id" :disabled="operating !== null" @click="test(row as ModelConnection)">测试能力</ElButton><ElButton link type="primary" :disabled="operating !== null" @click="open(row as ModelConnection)">编辑</ElButton><ElButton link type="danger" :disabled="operating !== null" @click="remove(row as ModelConnection)">删除</ElButton></template></ElTableColumn>
          </ElTable>
          <p v-else-if="!loading" class="inspection-retry">连接列表未加载。<ElButton @click="load">重试</ElButton></p>
        </div>
      </section>
      <p class="ai-data-notice">模型服务会收到用户对话，以及完成请求所需的资产信息和巡检结果。请确认服务地址和数据处理范围后再使用。</p>
    </main>
    <ModelConnectionDialog v-model="dialog" :connection="editing" @saved="load" />
  </AssetsLayout>
</template>
