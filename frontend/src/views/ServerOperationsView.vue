<script setup lang="ts">
import { ref } from 'vue'
import { ElAlert, ElTabPane, ElTabs } from 'element-plus'
import HostOperationsPage from '@/components/HostOperationsPage.vue'
import HostnameOperationForm from '@/components/HostnameOperationForm.vue'
import OperationsWorkbench from '@/components/OperationsWorkbench.vue'
import { showNavigationBlocked } from '@/components/feedback'
import type { OperationModuleId } from '@/types/operations'
import '@/styles/operations.css'

const section = ref('hostname')
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
        <ElTabs v-model="section" :before-leave="canSwitchSection" aria-label="服务器运维分类">
          <ElTabPane label="修改主机名" name="hostname" lazy>
            <HostnameOperationForm :host="host" />
          </ElTabPane>
          <ElTabPane label="软件包升级" name="upgrade" lazy>
            <ElAlert title="升级当前主机的所有软件包，可能影响运行中的服务；请核对计划后确认执行。" type="warning" :closable="false" show-icon />
            <OperationsWorkbench module="packages" :fixed-host="host" initial-action="upgrade_all" embedded />
          </ElTabPane>
          <ElTabPane label="软件仓库" name="repositories" lazy>
            <OperationsWorkbench module="packages" :fixed-host="host" :allowed-actions="repositoryActions" embedded />
          </ElTabPane>
          <ElTabPane v-for="item in modules" :key="item.id" :label="item.title" :name="item.id" lazy>
            <OperationsWorkbench :module="item.id" :fixed-host="host" embedded />
          </ElTabPane>
        </ElTabs>
      </main>
    </template>
  </HostOperationsPage>
</template>
