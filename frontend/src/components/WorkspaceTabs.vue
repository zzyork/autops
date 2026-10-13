<script setup lang="ts">
import { ElTabPane, ElTabs } from 'element-plus'
import { useWorkspace } from './workspace'
import WorkspacePage from './WorkspacePage.vue'

const { tabs, activeKey, select, close, canSwitch } = useWorkspace()
function remove(name: string | number) {
  void close(String(name))
}
</script>

<template>
  <div class="console-tabs" aria-label="已打开页面">
    <ElTabs :model-value="activeKey" type="card" :before-leave="canSwitch" @tab-change="select(String($event))" @tab-remove="remove">
      <ElTabPane v-for="tab in tabs" :key="tab.key" :name="tab.key" :label="tab.title" :closable="tabs.length > 1">
        <template #label><span class="console-tab-title" :title="tab.title">{{ tab.title }}</span></template>
        <WorkspacePage :location="tab.location" />
      </ElTabPane>
    </ElTabs>
  </div>
</template>
