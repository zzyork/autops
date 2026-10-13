import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/ai/chat' },
    { path: '/ai/chat', name: 'ai-chat', component: () => import('@/views/ChatView.vue') },
    { path: '/ai/connections', redirect: '/settings/models' },
    { path: '/settings', redirect: '/settings/models' },
    { path: '/settings/models', name: 'model-settings', component: () => import('@/views/ModelConnectionsView.vue') },
    { path: '/settings/inspection-rules', name: 'inspection-rules', component: () => import('@/views/InspectionRulesView.vue') },
    { path: '/assets', redirect: '/assets/hosts' },
    { path: '/assets/hosts', name: 'hosts', component: () => import('@/views/HostsView.vue') },
    { path: '/assets/jump-hosts', name: 'jump-hosts', component: () => import('@/views/JumpHostsView.vue') },
    { path: '/assets/ssh-keys', name: 'ssh-keys', component: () => import('@/views/SSHKeysView.vue') },
    { path: '/assets/groups', name: 'host-groups', component: () => import('@/views/HostGroupsView.vue') },
    { path: '/inspections', name: 'inspections', component: () => import('@/views/InspectionsView.vue') },
    { path: '/inspections/records', name: 'inspection-records', component: () => import('@/views/InspectionRecordsView.vue') },
    { path: '/inspections/rules', redirect: '/settings/inspection-rules' },
    { path: '/:pathMatch(.*)*', redirect: '/ai/chat' },
  ],
})
