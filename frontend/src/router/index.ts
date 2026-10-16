import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/ai/chat' },
    { path: '/ai/chat', name: 'ai-chat', meta: { title: 'AI 对话' }, component: () => import('@/views/ChatView.vue') },
    { path: '/ai/connections', redirect: '/settings/models' },
    { path: '/settings', redirect: '/settings/models' },
    { path: '/settings/models', name: 'model-settings', meta: { title: '模型配置' }, component: () => import('@/views/ModelConnectionsView.vue') },
    { path: '/settings/inspection-rules', name: 'inspection-rules', meta: { title: '巡检规则' }, component: () => import('@/views/InspectionRulesView.vue') },
    { path: '/assets', redirect: '/assets/hosts' },
    { path: '/assets/hosts', name: 'hosts', meta: { title: '主机管理' }, component: () => import('@/views/HostsView.vue') },
    { path: '/assets/jump-hosts', name: 'jump-hosts', meta: { title: '跳板机管理' }, component: () => import('@/views/JumpHostsView.vue') },
    { path: '/assets/ssh-keys', name: 'ssh-keys', meta: { title: 'SSH 密钥管理' }, component: () => import('@/views/SSHKeysView.vue') },
    { path: '/assets/groups', name: 'host-groups', meta: { title: '分组管理' }, component: () => import('@/views/HostGroupsView.vue') },
    { path: '/inspections', name: 'inspections', meta: { title: '巡检任务' }, component: () => import('@/views/InspectionsView.vue') },
    { path: '/inspections/records', name: 'inspection-records', meta: { title: '巡检记录' }, component: () => import('@/views/InspectionRecordsView.vue') },
    { path: '/inspections/records/:taskId', name: 'inspection-record-detail', meta: { title: '巡检详情' }, component: () => import('@/views/InspectionRecordDetailView.vue') },
    { path: '/inspections/rules', redirect: '/settings/inspection-rules' },
    { path: '/operations/hostname', redirect: '/assets/hosts' },
    { path: '/operations/packages', name: 'operation-packages', meta: { title: '软件仓库' }, component: () => import('@/views/PackagesOperationsView.vue') },
    { path: '/operations/firewall', name: 'operation-firewall', meta: { title: '防火墙管理' }, component: () => import('@/views/FirewallOperationsView.vue') },
    { path: '/operations/kernel', name: 'operation-kernel', meta: { title: '内核参数' }, component: () => import('@/views/KernelOperationsView.vue') },
    { path: '/operations/system', name: 'operation-system', meta: { title: '系统优化' }, component: () => import('@/views/SystemOperationsView.vue') },
    { path: '/operations/disk', name: 'operation-disk', meta: { title: '磁盘管理' }, component: () => import('@/views/DiskOperationsView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/ai/chat' },
  ],
})
