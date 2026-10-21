<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElButton, ElOption, ElSelect } from 'element-plus'
import { getFeatureModels, updateFeatureModels } from '@/api/ai'
import { showRequestError } from '@/components/feedback'
import type { FeatureModelsConfig, ModelConnection } from '@/types/ai'

const props = defineProps<{ connections: ModelConnection[]; connectionsLoaded: boolean; connectionsLoading: boolean }>()
const emit = defineEmits<{ configured: [config: FeatureModelsConfig | null] }>()
const draft = ref<FeatureModelsConfig>({ chat_connection_id: null, inspection_report_connection_id: null })
const loaded = ref(false)
const loading = ref(false)
const saving = ref(false)
const primary = computed(() => props.connections.find((item) => item.is_default))
const chatChoice = computed<number | 'primary'>({
  get: () => draft.value.chat_connection_id ?? 'primary',
  set: (value) => { draft.value.chat_connection_id = value === 'primary' ? null : value },
})
const reportChoice = computed<number | 'primary'>({
  get: () => draft.value.inspection_report_connection_id ?? 'primary',
  set: (value) => { draft.value.inspection_report_connection_id = value === 'primary' ? null : value },
})
let active = true
let sequence = 0

function missing(id: number | null) {
  return id !== null && props.connectionsLoaded && !props.connections.some((item) => item.id === id)
}
function connectionLabel(item: ModelConnection) {
  return `${item.name} / ${item.model}`
}
async function load() {
  if (saving.value) return
  const current = ++sequence
  loaded.value = false
  loading.value = true
  emit('configured', null)
  try {
    const config = await getFeatureModels()
    if (!active || current !== sequence) return
    draft.value = { ...config }
    loaded.value = true
    emit('configured', config)
  } catch {
    if (active && current === sequence) showRequestError()
  } finally {
    if (active && current === sequence) loading.value = false
  }
}
async function save() {
  if (saving.value || loading.value || !loaded.value || !props.connectionsLoaded || props.connectionsLoading) return
  const current = ++sequence
  saving.value = true
  try {
    const config = await updateFeatureModels({ ...draft.value })
    if (!active || current !== sequence) return
    draft.value = { ...config }
    emit('configured', config)
  } catch {
    if (active && current === sequence) showRequestError()
  } finally {
    if (active && current === sequence) saving.value = false
  }
}
onMounted(() => { void load() })
onUnmounted(() => { active = false; sequence++ })
</script>

<template>
  <section class="ui-panel ai-feature-section" aria-label="独立功能模型">
    <div class="section-header"><h2>独立功能模型</h2><ElButton :loading="loading" :disabled="saving" @click="load">刷新</ElButton></div>
    <p v-if="loading" class="ui-text-muted">正在读取功能配置...</p>
    <p v-else-if="!loaded" class="ui-load-retry">功能配置未加载。<ElButton @click="load">重试</ElButton></p>
    <form v-else class="ui-form ai-feature-form" @submit.prevent="save">
      <div class="field-grid">
        <div class="field">
          <label for="feature-chat-model">AI 对话与运维工具 <em>*</em></label>
          <ElSelect id="feature-chat-model" v-model="chatChoice" :disabled="!connectionsLoaded || connectionsLoading || saving">
            <ElOption :label="`沿用主模型（${primary ? `${primary.name} / ${primary.model}` : '未设置主模型'}）`" value="primary" />
            <ElOption v-for="item in connections" :key="item.id" :label="connectionLabel(item)" :value="item.id" />
            <ElOption v-if="missing(draft.chat_connection_id)" :label="`连接 #${draft.chat_connection_id} 已不存在`" :value="draft.chat_connection_id!" disabled />
          </ElSelect>
        </div>
        <div class="field">
          <label for="feature-report-model">巡检 AI 报告 <em>*</em></label>
          <ElSelect id="feature-report-model" v-model="reportChoice" :disabled="!connectionsLoaded || connectionsLoading || saving">
            <ElOption :label="`沿用主模型（${primary ? `${primary.name} / ${primary.model}` : '未设置主模型'}）`" value="primary" />
            <ElOption v-for="item in connections" :key="item.id" :label="connectionLabel(item)" :value="item.id" />
            <ElOption v-if="missing(draft.inspection_report_connection_id)" :label="`连接 #${draft.inspection_report_connection_id} 已不存在`" :value="draft.inspection_report_connection_id!" disabled />
          </ElSelect>
        </div>
      </div>
      <p v-if="!connectionsLoaded" class="ui-text-muted">连接列表未加载，暂不能修改或保存功能配置。</p>
      <div><ElButton native-type="submit" type="primary" :loading="saving" :disabled="!connectionsLoaded || connectionsLoading || loading">保存配置</ElButton></div>
    </form>
  </section>
</template>
