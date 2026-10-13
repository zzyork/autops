<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ElButton, ElForm, ElLoading } from 'element-plus'
import { getInspectionCatalog, updateInspectionCatalog } from '@/api/inspections'
import AssetsLayout from '@/components/AssetsLayout.vue'
import InspectionConfigForm from '@/components/InspectionConfigForm.vue'
import { showSystemError } from '@/components/feedback'
import type { InspectionCatalog, InspectionConfig } from '@/types/inspections'
import '@/styles/inspections.css'

const vLoading = ElLoading.directive
const loading = ref(false)
const loaded = ref(false)
const saving = ref(false)
const draft = ref<InspectionConfig | null>(null)
const configForm = ref<InstanceType<typeof InspectionConfigForm> | null>(null)
const formRevision = ref(0)
let active = true
let request = 0
function applyRules(result: InspectionCatalog) {
  const defaults = result.defaults
  draft.value = {
    thresholds: { ...defaults.thresholds },
    command_timeout_seconds: defaults.command_timeout_seconds,
    host_timeout_seconds: defaults.host_timeout_seconds,
    services: defaults.services.map((service) => ({ ...service, candidates: [...service.candidates] })),
    logs: { ...defaults.logs, paths: [...defaults.logs.paths] },
  }
  loaded.value = true
  formRevision.value++
}
async function loadRules() {
  if (saving.value) return
  const current = ++request
  loading.value = true
  try {
    const result = await getInspectionCatalog()
    if (!active || current !== request) return
    applyRules(result)
  } catch {
    if (!active || current !== request) return
    loaded.value = false
    showSystemError()
  } finally {
    if (active && current === request) loading.value = false
  }
}
async function saveRules() {
  if (saving.value || loading.value || !loaded.value || !configForm.value) return
  if (!configForm.value.validate()) return
  const body = configForm.value.normalized()
  const current = ++request
  loading.value = false
  saving.value = true
  try {
    const result = await updateInspectionCatalog(body)
    if (!active || current !== request) return
    applyRules(result)
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
        <div class="host-toolbar"><div class="inspection-rules-actions"><ElButton type="primary" :loading="saving" :disabled="!loaded || loading" @click="saveRules">保存</ElButton><span class="inspection-muted">修改后点击保存生效；刷新会重新加载已保存的规则。</span></div><ElButton :loading="loading" :disabled="saving" @click="loadRules">刷新</ElButton></div>
        <fieldset v-if="loaded && draft" :disabled="loading || saving" class="inspection-rules-form" aria-label="编辑巡检规则">
          <ElForm :disabled="loading || saving" @submit.prevent="saveRules">
            <InspectionConfigForm :key="formRevision" ref="configForm" v-model="draft" />
          </ElForm>
          <p class="inspection-muted">达到阈值触发对应结论；无 Swap 时不产生 Swap 阈值告警。</p>
          <p class="inspection-muted">必需服务未安装、已找到但未加载或未运行的服务产生警告；未安装的可选服务不代表正常运行。</p>
        </fieldset>
        <p v-else-if="!loading" class="inspection-retry">规则未加载。<ElButton @click="loadRules">重试</ElButton></p>
      </section>
    </main>
  </AssetsLayout>
</template>

<style scoped>
.inspection-rules-form { min-width: 0; margin: 0; padding: 0; border: 0; }
</style>
