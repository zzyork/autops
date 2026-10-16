<script setup lang="ts">
import { computed, provide, shallowReactive, watch } from 'vue'
import { routeLocationKey, type RouteLocationNormalizedLoaded } from 'vue-router'
import { workspaceVisibleKey } from './workspace'

const props = defineProps<{ location: RouteLocationNormalizedLoaded; active: boolean }>()
// 每个已打开页面使用自己的路由，避免后台详情响应其他标签的参数变化。
const location = shallowReactive({ ...props.location })
provide(routeLocationKey, location)
provide(workspaceVisibleKey, computed(() => props.active))
watch(() => props.location, (value) => Object.assign(location, value), { flush: 'sync' })
</script>

<template>
  <div class="workspace-page">
    <RouterView :route="location" />
  </div>
</template>
