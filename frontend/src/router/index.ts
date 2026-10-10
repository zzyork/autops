import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/assets/hosts' },
    { path: '/assets', redirect: '/assets/hosts' },
    { path: '/assets/hosts', name: 'hosts', component: () => import('@/views/HostsView.vue') },
    { path: '/assets/jump-hosts', name: 'jump-hosts', component: () => import('@/views/JumpHostsView.vue') },
    { path: '/assets/ssh-keys', name: 'ssh-keys', component: () => import('@/views/SSHKeysView.vue') },
    { path: '/assets/groups', name: 'host-groups', component: () => import('@/views/HostGroupsView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/assets/hosts' },
  ],
})
