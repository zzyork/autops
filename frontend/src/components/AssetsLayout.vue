<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import '@/styles/assets.css'

withDefaults(defineProps<{ title: string; section?: string }>(), { section: '资产管理' })
const route = useRoute()
const menuCollapsed = ref(false)
const assetsExpanded = ref(true)
const inspectionsExpanded = ref(true)
const settingsExpanded = ref(true)
</script>

<template>
  <div class="workspace assets-page" :class="{ 'menu-collapsed': menuCollapsed }">
    <header class="topbar console-topbar">
      <RouterLink to="/ai/chat" class="brand" aria-label="autops AI 对话"><span class="brand-mark">a.</span>autops</RouterLink>
      <span class="console-version">v0.1</span>
    </header>
    <aside class="console-sidebar" aria-label="主导航">
      <div class="console-sidebar-heading"><span v-if="!menuCollapsed">控制台</span><button class="menu-toggle" type="button" :aria-label="menuCollapsed ? '展开菜单' : '收起菜单'" :aria-expanded="!menuCollapsed" @click="menuCollapsed = !menuCollapsed"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg></button></div>
      <nav aria-label="AI 运维">
        <RouterLink to="/ai/chat" class="console-menu-item console-menu-root" aria-label="AI 对话" title="AI 对话"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h16v13H9l-5 4V4zM8 9h8M8 13h5" /></svg><span v-if="!menuCollapsed">AI 对话</span></RouterLink>
      </nav>
      <button class="console-menu-label" type="button" :aria-expanded="assetsExpanded" aria-controls="assets-navigation" :aria-label="assetsExpanded ? '收起资产管理菜单' : '展开资产管理菜单'" title="资产管理" @click="assetsExpanded = !assetsExpanded">
        <svg class="console-menu-label-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 9 5v8l-9 5-9-5V8zM3 8l9 5 9-5M12 13v8M7.5 5.5l9 5" /></svg>
        <span v-if="!menuCollapsed">资产管理</span>
        <svg v-if="!menuCollapsed" class="console-menu-label-arrow" viewBox="0 0 24 24" aria-hidden="true"><path :d="assetsExpanded ? 'M6 9l6 6 6-6' : 'M9 6l6 6-6 6'" /></svg>
      </button>
      <nav v-show="assetsExpanded" id="assets-navigation" aria-label="资产管理">
      <RouterLink to="/assets/hosts" class="console-menu-item" aria-label="主机管理" title="主机管理"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="1" /><path d="M8 21h8M12 16v5M3 12h18" /></svg><span v-if="!menuCollapsed">主机管理</span></RouterLink>
      <RouterLink to="/assets/jump-hosts" class="console-menu-item" aria-label="跳板机管理" title="跳板机管理"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="1" /><path d="M6 7h12M6 12h12M6 17h12M3 4v16M21 4v16" /></svg><span v-if="!menuCollapsed">跳板机管理</span></RouterLink>
      <RouterLink to="/assets/ssh-keys" class="console-menu-item" aria-label="SSH 密钥管理" title="SSH 密钥管理"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="8" cy="9" r="4" /><path d="M11 12l9 9m-4-4 2-2m-5-1 2-2" /></svg><span v-if="!menuCollapsed">SSH 密钥管理</span></RouterLink>
      <RouterLink to="/assets/groups" class="console-menu-item" aria-label="分组管理" title="分组管理"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7V4h6l2 3h10v13H3z" /></svg><span v-if="!menuCollapsed">分组管理</span></RouterLink>
      </nav>
      <button class="console-menu-label" type="button" :aria-expanded="inspectionsExpanded" aria-controls="inspections-navigation" :aria-label="inspectionsExpanded ? '收起巡检管理菜单' : '展开巡检管理菜单'" title="巡检管理" @click="inspectionsExpanded = !inspectionsExpanded">
        <svg class="console-menu-label-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v15H4zM8 10l2 2 4-4M8 16h8" /></svg>
        <span v-if="!menuCollapsed">巡检管理</span>
        <svg v-if="!menuCollapsed" class="console-menu-label-arrow" viewBox="0 0 24 24" aria-hidden="true"><path :d="inspectionsExpanded ? 'M6 9l6 6 6-6' : 'M9 6l6 6-6 6'" /></svg>
      </button>
      <nav v-show="inspectionsExpanded" id="inspections-navigation" aria-label="巡检管理">
        <RouterLink to="/inspections" class="console-menu-item" aria-label="巡检任务" title="巡检任务"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v15H4zM8 10l2 2 4-4M8 16h8" /></svg><span v-if="!menuCollapsed">巡检任务</span></RouterLink>
        <RouterLink to="/inspections/records" class="console-menu-item" aria-label="巡检记录" title="巡检记录"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h14v18H5zM8 7h8M8 12h8M8 17h5" /></svg><span v-if="!menuCollapsed">巡检记录</span></RouterLink>
      </nav>
      <button class="console-menu-label" type="button" :aria-expanded="settingsExpanded" aria-controls="settings-navigation" :aria-label="settingsExpanded ? '收起配置管理菜单' : '展开配置管理菜单'" title="配置管理" @click="settingsExpanded = !settingsExpanded">
        <svg class="console-menu-label-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v14H4zM8 9h8M8 13h8M8 17h4" /></svg>
        <span v-if="!menuCollapsed">配置管理</span>
        <svg v-if="!menuCollapsed" class="console-menu-label-arrow" viewBox="0 0 24 24" aria-hidden="true"><path :d="settingsExpanded ? 'M6 9l6 6 6-6' : 'M9 6l6 6-6 6'" /></svg>
      </button>
      <nav v-show="settingsExpanded" id="settings-navigation" aria-label="配置管理">
        <RouterLink to="/settings/models" class="console-menu-item" aria-label="模型配置" title="模型配置"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v14H4zM8 9h8M8 13h8M8 17h4" /></svg><span v-if="!menuCollapsed">模型配置</span></RouterLink>
        <RouterLink to="/settings/inspection-rules" class="console-menu-item" aria-label="巡检规则" title="巡检规则"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6" /></svg><span v-if="!menuCollapsed">巡检规则</span></RouterLink>
      </nav>
    </aside>
    <div class="console-content">
      <div class="console-breadcrumb"><span>{{ route.path.startsWith('/settings/') ? '配置管理' : section }}</span><span class="breadcrumb-separator">/</span><strong>{{ title }}</strong></div>
      <slot />
    </div>
  </div>
</template>
