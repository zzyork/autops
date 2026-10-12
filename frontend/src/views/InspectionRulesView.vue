<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElButton, ElDialog, ElLoading, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { getInspectionCatalog, updateInspectionCatalog } from '@/api/inspections'
import AssetsLayout from '@/components/AssetsLayout.vue'
import InspectionConfigForm from '@/components/InspectionConfigForm.vue'
import { showSystemError } from '@/components/feedback'
import type { InspectionCatalog, InspectionConfig } from '@/types/inspections'
import '@/styles/inspections.css'

const vLoading = ElLoading.directive
const catalog = ref<InspectionCatalog | null>(null)
const loading = ref(false)
const loaded = ref(false)
const editing = ref(false)
const saving = ref(false)
const draft = ref<InspectionConfig | null>(null)
const configForm = ref<InstanceType<typeof InspectionConfigForm> | null>(null)
let active = true
let request = 0
const thresholds = computed(() => {
  if (!catalog.value) return []
  const values = catalog.value.defaults.thresholds
  return [
    { name: 'CPU', warning: values.cpu_warning, critical: values.cpu_critical },
    { name: '内存', warning: values.mem_warning, critical: values.mem_critical },
    { name: '磁盘', warning: values.disk_warning, critical: values.disk_critical },
    { name: 'Swap', warning: values.swap_warning, critical: values.swap_critical },
  ]
})
async function loadRules() {
  if (saving.value) return
  const current = ++request
  loading.value = true
  try {
    const result = await getInspectionCatalog()
    if (!active || current !== request) return
    catalog.value = result
    loaded.value = true
  } catch {
    if (!active || current !== request) return
    loaded.value = false
    showSystemError()
  } finally {
    if (active && current === request) loading.value = false
  }
}
function openEditor() {
  if (!loaded.value || !catalog.value || loading.value) return
  const defaults = catalog.value.defaults
  draft.value = {
    thresholds: { ...defaults.thresholds },
    command_timeout_seconds: defaults.command_timeout_seconds,
    host_timeout_seconds: defaults.host_timeout_seconds,
    services: defaults.services.map((service) => ({ ...service, candidates: [...service.candidates] })),
  }
  editing.value = true
}
async function saveRules() {
  if (saving.value || !editing.value || !configForm.value) return
  if (!configForm.value.validate()) return
  const body = configForm.value.normalized()
  const current = ++request
  loading.value = false
  saving.value = true
  try {
    const result = await updateInspectionCatalog(body)
    if (!active || current !== request) return
    catalog.value = result
    loaded.value = true
    editing.value = false
  } catch {
    if (active && current === request) showSystemError()
  } finally {
    if (active && current === request) saving.value = false
  }
}
onMounted(() => { void loadRules() })
onUnmounted(() => { active = false; request++ })
</script>

<template>
  <AssetsLayout title="巡检规则" section="巡检管理">
    <main class="assets-main">
      <div class="assets-heading"><h1>巡检规则</h1></div>
      <section v-loading="loading" class="host-section" aria-label="巡检规则">
        <div class="host-toolbar"><div class="inspection-rules-actions"><ElButton type="primary" :disabled="!loaded || loading || editing" @click="openEditor">编辑规则</ElButton><span class="inspection-muted">保存后仅影响后续新任务，历史规则快照不变。</span></div><ElButton :loading="loading" :disabled="editing || saving" @click="loadRules">刷新</ElButton></div>
        <div v-if="loaded && catalog" class="inspection-detail">
          <section aria-label="检查项">
            <div class="section-header"><h2>检查项</h2></div>
            <div class="host-table-wrap"><ElTable :data="catalog.checks" row-key="id" class="host-table" empty-text="暂无检查项">
              <ElTableColumn prop="title" label="检查项" width="180" />
              <ElTableColumn prop="description" label="检查内容" min-width="400" />
            </ElTable></div>
          </section>
          <section aria-label="资源阈值">
            <div class="section-header"><h2>资源阈值</h2></div>
            <div class="host-table-wrap"><ElTable :data="thresholds" row-key="name" class="host-table">
              <ElTableColumn prop="name" label="资源" min-width="180" />
              <ElTableColumn label="警告阈值"><template #default="{ row }">{{ row.warning }}%</template></ElTableColumn>
              <ElTableColumn label="严重阈值"><template #default="{ row }">{{ row.critical }}%</template></ElTableColumn>
            </ElTable></div>
            <p class="inspection-muted">达到阈值触发对应结论；无 Swap 时不产生 Swap 阈值告警。</p>
          </section>
          <section aria-label="执行时限">
            <div class="section-header"><h2>执行时限</h2></div>
            <div class="inspection-detail-meta"><span>单命令 {{ catalog.defaults.command_timeout_seconds }} 秒</span><span>单主机 {{ catalog.defaults.host_timeout_seconds }} 秒</span></div>
          </section>
          <section aria-label="服务判定">
            <div class="section-header"><h2>服务判定</h2></div>
            <div class="host-table-wrap"><ElTable :data="catalog.defaults.services" class="host-table" empty-text="暂无服务规则">
              <ElTableColumn prop="name" label="服务名称" min-width="180" />
              <ElTableColumn label="候选单元" min-width="300"><template #default="{ row }">{{ row.candidates.join('、') }}</template></ElTableColumn>
              <ElTableColumn label="要求" width="100"><template #default="{ row }"><ElTag :type="row.required ? 'warning' : 'info'" size="small">{{ row.required ? '必需' : '可选' }}</ElTag></template></ElTableColumn>
            </ElTable></div>
            <p class="inspection-muted">必需服务未安装、已找到但未加载或未运行的服务产生警告；未安装的可选服务不代表正常运行。</p>
          </section>
        </div>
        <p v-else-if="!loading" class="inspection-retry">规则未加载。<ElButton @click="loadRules">重试</ElButton></p>
      </section>
    </main>
    <ElDialog :model-value="editing" align-center title="编辑巡检规则" width="min(720px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving" @update:model-value="!saving && (editing = $event)">
      <InspectionConfigForm v-if="draft" ref="configForm" v-model="draft" />
      <template #footer><ElButton :disabled="saving" @click="editing = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="saveRules">保存</ElButton></template>
    </ElDialog>
  </AssetsLayout>
</template>
