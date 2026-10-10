<script setup lang="ts">
import { ref } from 'vue'
import '@/styles/assets.css'

defineProps<{ title: string }>()
const menuCollapsed = ref(false)
</script>

<template>
  <div class="workspace assets-page" :class="{ 'menu-collapsed': menuCollapsed }">
    <header class="topbar console-topbar">
      <RouterLink to="/assets/hosts" class="brand" aria-label="autops 资产管理"><span class="brand-mark">a.</span>autops</RouterLink>
      <span class="console-title">运维控制台</span><span class="console-version">v0.1</span>
    </header>
    <aside class="console-sidebar" aria-label="主导航">
      <div class="console-sidebar-heading"><span v-if="!menuCollapsed">控制台</span><button class="menu-toggle" type="button" :aria-label="menuCollapsed ? '展开菜单' : '收起菜单'" :aria-expanded="!menuCollapsed" @click="menuCollapsed = !menuCollapsed"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg></button></div>
      <div v-if="!menuCollapsed" class="console-menu-label">资产管理</div>
      <RouterLink to="/assets/hosts" class="console-menu-item" aria-label="主机管理" title="主机管理"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="1" /><path d="M8 21h8M12 16v5M3 12h18" /></svg><span v-if="!menuCollapsed">主机管理</span></RouterLink>
      <RouterLink to="/assets/jump-hosts" class="console-menu-item" aria-label="跳板机管理" title="跳板机管理"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="1" /><path d="M6 7h12M6 12h12M6 17h12M3 4v16M21 4v16" /></svg><span v-if="!menuCollapsed">跳板机管理</span></RouterLink>
      <RouterLink to="/assets/groups" class="console-menu-item" aria-label="分组管理" title="分组管理"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7V4h6l2 3h10v13H3z" /></svg><span v-if="!menuCollapsed">分组管理</span></RouterLink>
    </aside>
    <div class="console-content">
      <div class="console-breadcrumb"><span>资产管理</span><span class="breadcrumb-separator">/</span><strong>{{ title }}</strong></div>
      <slot />
    </div>
  </div>
</template>
