<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElButton, ElLoading } from 'element-plus'
import { getHost } from '@/api/assets'
import { showRequestError } from '@/components/feedback'
import OperationsWorkbench from '@/components/OperationsWorkbench.vue'
import type { Host } from '@/types/api'
import type { OperationModuleId } from '@/types/operations'

defineProps<{ module?: OperationModuleId }>()
const route = useRoute()
const vLoading = ElLoading.directive
const host = ref<Host | null>(null)
const loading = ref(false)
const hostId = computed(() => {
  const value = route.params.hostId
  const id = typeof value === 'string' && /^[1-9]\d*$/.test(value) ? Number(value) : NaN
  return Number.isSafeInteger(id) ? id : null
})
let request = 0
let active = true

async function loadHost() {
  const current = ++request
  host.value = null
  const id = hostId.value
  if (id === null) { loading.value = false; return }
  loading.value = true
  try {
    const result = await getHost(id)
    if (active && current === request) host.value = result
  } catch (error) {
    if (active && current === request) showRequestError(error)
  } finally {
    if (active && current === request) loading.value = false
  }
}

watch(() => route.params.hostId, () => { void loadHost() }, { immediate: true })
onUnmounted(() => { active = false; request++ })
</script>

<template>
  <template v-if="host"><slot :host="host"><OperationsWorkbench v-if="module" :key="`${module}-${host.id}`" :module="module" :fixed-host="host" /></slot></template>
  <main v-else v-loading="loading" class="assets-main" aria-label="加载运维主机">
    <template v-if="hostId === null"><p>主机地址无效，请从主机管理选择目标主机。</p><RouterLink to="/assets/hosts">返回主机管理</RouterLink></template>
    <ElButton v-else-if="!loading" @click="loadHost">重新加载主机</ElButton>
  </main>
</template>
