<script setup lang="ts">
import { provide, shallowReactive, watch } from 'vue'
import { routeLocationKey, type RouteLocationNormalizedLoaded } from 'vue-router'

const props = defineProps<{ location: RouteLocationNormalizedLoaded }>()
// 每个已打开页面使用自己的路由，避免后台详情响应其他标签的参数变化。
const location = shallowReactive({ ...props.location })
provide(routeLocationKey, location)
watch(() => props.location, (value) => Object.assign(location, value), { flush: 'sync' })
</script>

<template>
  <div class="workspace-page">
    <RouterView :route="location" />
  </div>
</template>
