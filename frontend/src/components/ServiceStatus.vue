<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElAlert, ElButton, ElTag } from 'element-plus'
import { getHealth } from '@/api/health'

const state = ref<'pending' | 'online' | 'offline'>('pending')
const loading = ref(false)
const error = ref('')
const lastChecked = ref('尚未检查')
const label = computed(() => ({ pending: '等待检查', online: '连接正常', offline: '连接失败' })[state.value])

async function checkHealth() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const health = await getHealth()
    if (health.status !== 'ok') throw new Error('服务返回了异常状态')
    state.value = 'online'
  } catch (cause) {
    state.value = 'offline'
    error.value = cause instanceof Error && cause.message.startsWith('请求失败')
      ? cause.message
      : '暂时无法连接服务，请稍后重试。'
  } finally {
    loading.value = false
    lastChecked.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  }
}

onMounted(checkHealth)
</script>

<template>
  <section class="service-panel" aria-labelledby="service-title" aria-live="polite">
    <div class="panel-heading">
      <span class="eyebrow">服务状态</span>
      <ElTag :type="state === 'online' ? 'success' : state === 'offline' ? 'danger' : 'info'" effect="plain">
        {{ label }}
      </ElTag>
    </div>
    <h2 id="service-title">{{ state === 'online' ? '一切就绪。' : state === 'offline' ? '服务暂未就绪。' : '正在连接服务…' }}</h2>
    <p>检查服务连接，让每一次操作都有可靠的起点。</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <div class="panel-footer">
      <span>最近检查 · {{ lastChecked }}</span>
      <ElButton type="primary" :loading="loading" @click="checkHealth">重新检查</ElButton>
    </div>
  </section>
</template>
