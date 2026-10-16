<script setup lang="ts">
import { inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { ElTabPane, ElTabs } from 'element-plus'
import HostOperationsPage from '@/components/HostOperationsPage.vue'
import HostnameOperationForm from '@/components/HostnameOperationForm.vue'
import OperationsWorkbench from '@/components/OperationsWorkbench.vue'
import { showNavigationBlocked } from '@/components/feedback'
import type { OperationModuleId } from '@/types/operations'
import { workspaceVisibleKey } from '@/components/workspace'
import '@/styles/operations.css'

const route = useRoute()
const router = useRouter()
const workspaceVisible = inject(workspaceVisibleKey, ref(true))
const sections = ['hostname', 'upgrade', 'repositories', 'firewall', 'kernel', 'system', 'disk']
const section = ref(typeof route.query.section === 'string' && sections.includes(route.query.section) ? route.query.section : 'hostname')
watch(() => route.query.section, (value) => { if (typeof value === 'string' && sections.includes(value)) section.value = value })
function sectionChanged(value: string | number) {
  const next = String(value)
  if (next !== route.query.section) void router.replace({ path: route.path, query: { ...route.query, section: next, taskId: undefined } })
}
const repositoryActions = ['list_repos', 'add_repo', 'update_repo', 'delete_repo']
const modules: { id: OperationModuleId; title: string }[] = [
  { id: 'firewall', title: '防火墙管理' },
  { id: 'kernel', title: '内核参数' },
  { id: 'system', title: '系统优化' },
  { id: 'disk', title: '磁盘管理' },
]

function canSwitchSection() {
  if (!document.body.classList.contains('el-popup-parent--hidden')) return true
  showNavigationBlocked()
  return false
}
</script>

<template>
  <HostOperationsPage>
    <template #default="{ host }">
      <main :key="host.id" class="assets-main operations-main">
        <div class="assets-heading"><h1>服务器运维</h1></div>
        <div class="host-section server-operation-target"><strong>{{ host.name }}</strong><span>{{ host.address }}</span></div>
        <ElTabs v-model="section" :before-leave="canSwitchSection" aria-label="服务器运维分类" @tab-change="sectionChanged">
          <ElTabPane label="修改主机名" name="hostname" lazy>
            <HostnameOperationForm :host="host" :visible="workspaceVisible && section === 'hostname'" />
          </ElTabPane>
          <ElTabPane label="软件包升级" name="upgrade" lazy>
            <OperationsWorkbench module="packages" :fixed-host="host" initial-action="upgrade_all" section="upgrade" :visible="workspaceVisible && section === 'upgrade'" embedded />
          </ElTabPane>
          <ElTabPane label="软件仓库" name="repositories" lazy>
            <OperationsWorkbench module="packages" :fixed-host="host" :allowed-actions="repositoryActions" section="repositories" :visible="workspaceVisible && section === 'repositories'" embedded />
          </ElTabPane>
          <ElTabPane v-for="item in modules" :key="item.id" :label="item.title" :name="item.id" lazy>
            <OperationsWorkbench :module="item.id" :fixed-host="host" :section="item.id" :visible="workspaceVisible && section === item.id" embedded />
          </ElTabPane>
        </ElTabs>
      </main>
    </template>
  </HostOperationsPage>
</template>
