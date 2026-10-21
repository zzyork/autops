<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElLoading, ElMessageBox, ElTable, ElTableColumn, ElTag } from 'element-plus'
import ModelConnectionDialog from '@/components/ModelConnectionDialog.vue'
import FeatureModelsForm from '@/components/FeatureModelsForm.vue'
import TestStatus from '@/components/TestStatus.vue'
import ListPagination from '@/components/ListPagination.vue'
import { useServerPagination } from '@/components/serverPagination'
import { deleteConnection, listConnections, listConnectionsPage, testConnection } from '@/api/ai'
import { showRequestError } from '@/components/feedback'
import type { FeatureModelsConfig, ModelConnection } from '@/types/ai'
import type { TestStatus as TestStatusValue } from '@/types/testStatus'
import '@/styles/ai.css'

const vLoading = ElLoading.directive
const { items: connections, page, pageSize, total, loading, loadFailed, refresh, resetPage } = useServerPagination(listConnectionsPage)
const loaded = ref(false)
const allConnections = ref<ModelConnection[]>([])
const allLoaded = ref(false)
const allLoading = ref(false)
const editing = ref<ModelConnection | null>(null)
const copying = ref<ModelConnection | null>(null)
const dialog = ref(false)
const operating = ref<number | null>(null)
const testing = ref<number | null>(null)
const featureModels = ref<FeatureModelsConfig | null>(null)
let active = true
let allSequence = 0
watch(loading, (busy) => {
  if (busy) { loaded.value = false; return }
  if (!loadFailed.value) loaded.value = true
})
function testStatus(connection: ModelConnection): TestStatusValue {
  if (testing.value === connection.id) return 'pending'
  if (connection.chat_status === 'passed' && connection.tool_status === 'passed') return 'passed'
  if (connection.chat_status === 'failed' || connection.tool_status === 'failed') return 'failed'
  return 'untested'
}
function testDescription(connection: ModelConnection): string {
  switch (testStatus(connection)) {
    case 'pending': return '正在测试模型是否支持 AI 运维'
    case 'passed': return '测试通过'
    case 'failed': return '测试未通过'
    default: return '尚未测试'
  }
}

async function loadAll() {
  const current = ++allSequence
  allLoaded.value = false
  allLoading.value = true
  try {
    const items = await listConnections()
    if (!active || current !== allSequence) return
    allConnections.value = items
    allLoaded.value = true
  } catch {
    if (!active || current !== allSequence) return
    showRequestError()
  } finally {
    if (active && current === allSequence) allLoading.value = false
  }
}
function load() {
  if (testing.value !== null) return
  void refresh()
  void loadAll()
}
function saved() {
  if (!editing.value) resetPage()
  load()
}
function open(connection: ModelConnection | null) {
  editing.value = connection
  copying.value = null
  dialog.value = true
}
function copy(connection: ModelConnection) {
  editing.value = null
  copying.value = connection
  dialog.value = true
}
async function test(connection: ModelConnection) {
  if (operating.value !== null) return
  operating.value = connection.id
  testing.value = connection.id
  try {
    const updated = await testConnection(connection.id)
    if (!active) return
    connections.value = connections.value.map((item) => item.id === updated.id ? updated : item)
    void loadAll()
    await refresh()
  } catch { if (active) showRequestError() }
  finally { if (active) { operating.value = null; testing.value = null } }
}
async function remove(connection: ModelConnection) {
  if (operating.value !== null || !featureModels.value || featureModels.value.chat_connection_id === connection.id || featureModels.value.inspection_report_connection_id === connection.id) return
  operating.value = connection.id
  try {
    await ElMessageBox.confirm(`确定删除模型连接“${connection.name}”吗？已有会话可能引用此连接，此操作不可撤销。`, '删除模型连接', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'delete-confirm-button',
    })
  } catch { operating.value = null; return }
  try {
    await deleteConnection(connection.id)
    if (active) load()
  } catch { if (active) showRequestError() }
  finally { if (active) operating.value = null }
}
onMounted(() => { void loadAll() })
onUnmounted(() => { active = false; allSequence++ })
</script>

<template>
    <main class="console-main">
      <section class="ui-panel" aria-label="模型连接">
        <div class="ui-toolbar"><ElButton type="primary" @click="open(null)">新增连接</ElButton><ElButton :loading="loading || allLoading" :disabled="testing !== null" @click="load">刷新</ElButton></div>
        <div v-loading="loading" class="ui-table-wrap">
          <ElTable v-if="loaded" :data="connections" class="ui-table" empty-text="暂无模型连接">
            <ElTableColumn label="连接名称" min-width="170"><template #default="{ row }"><strong>{{ row.name }}</strong><ElTag v-if="row.is_default" size="small" class="ai-default-tag">主模型</ElTag><ElTag v-if="row.is_backup" size="small" type="info" class="ai-default-tag">备用模型</ElTag></template></ElTableColumn>
            <ElTableColumn label="协议 / 模型" min-width="190"><template #default="{ row }">{{ row.protocol === 'anthropic' ? 'Anthropic' : 'OpenAI 兼容' }}<div class="ui-item-secondary">{{ row.model }}</div></template></ElTableColumn>
            <ElTableColumn label="服务地址" min-width="240"><template #default="{ row }"><span class="ai-address">{{ row.base_url }}</span></template></ElTableColumn>
            <ElTableColumn label="密钥" width="90"><template #default="{ row }">{{ row.has_api_key ? '已配置' : '无密钥' }}</template></ElTableColumn>
            <ElTableColumn label="测试状态" width="100" align="center"><template #default="{ row }"><TestStatus :status="testStatus(row as ModelConnection)" :description="testDescription(row as ModelConnection)" /></template></ElTableColumn>
            <ElTableColumn label="操作" width="248" fixed="right"><template #default="{ row }"><ElButton link type="primary" :loading="operating === row.id" :disabled="operating !== null" @click="test(row as ModelConnection)">测试</ElButton><ElButton link type="primary" :disabled="operating !== null" @click="open(row as ModelConnection)">编辑</ElButton><ElButton link type="primary" :disabled="operating !== null" @click="copy(row as ModelConnection)">复制</ElButton><ElButton link type="danger" :disabled="operating !== null || !featureModels || featureModels.chat_connection_id === row.id || featureModels.inspection_report_connection_id === row.id" :title="!featureModels ? '功能配置未加载' : featureModels.chat_connection_id === row.id || featureModels.inspection_report_connection_id === row.id ? '已被独立功能引用，请先修改功能配置' : '删除连接'" @click="remove(row as ModelConnection)">删除</ElButton></template></ElTableColumn>
          </ElTable>
          <p v-else-if="!loading" class="ui-load-retry">连接列表未加载。<ElButton @click="load">重试</ElButton></p>
        </div>
        <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :total-known="loaded && !loading" :disabled="loading || !loaded || operating !== null" />
      </section>
      <FeatureModelsForm :connections="allConnections" :connections-loaded="allLoaded" :connections-loading="allLoading" @configured="featureModels = $event" />
      <p class="ai-data-notice">模型服务会收到用户对话，以及完成请求所需的资产信息和巡检结果。请确认服务地址和数据处理范围后再使用。</p>
    </main>
    <ModelConnectionDialog v-model="dialog" :connection="editing" :copy-source="copying" @saved="saved" />
</template>
