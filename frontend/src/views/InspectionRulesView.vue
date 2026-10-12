<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElButton, ElLoading, ElTable, ElTableColumn, ElTag } from 'element-plus'
import { getInspectionCatalog } from '@/api/inspections'
import AssetsLayout from '@/components/AssetsLayout.vue'
import { showSystemError } from '@/components/feedback'
import type { InspectionCatalog } from '@/types/inspections'
import '@/styles/inspections.css'

const vLoading = ElLoading.directive
const catalog = ref<InspectionCatalog | null>(null)
const loading = ref(false)
const loaded = ref(false)
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
onMounted(() => { void loadRules() })
onUnmounted(() => { active = false; request++ })
</script>

<template>
  <AssetsLayout title="巡检规则" section="巡检管理">
    <main class="assets-main">
      <div class="assets-heading"><h1>巡检规则</h1></div>
      <section v-loading="loading" class="host-section" aria-label="巡检规则">
        <div class="host-toolbar"><span class="inspection-muted">统一默认规则，创建单次任务时不可调整。</span><ElButton :loading="loading" @click="loadRules">刷新</ElButton></div>
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
  </AssetsLayout>
</template>
