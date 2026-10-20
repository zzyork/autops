<script setup lang="ts">
import { provide } from 'vue'
import { useRouter } from 'vue-router'
import ConsoleLayout from '@/components/ConsoleLayout.vue'
import WorkspaceTabs from '@/components/WorkspaceTabs.vue'
import SSHIdentityDialog from '@/components/SSHIdentityDialog.vue'
import { createWorkspace, workspaceKey } from '@/components/workspace'

const workspace = createWorkspace(useRouter())
provide(workspaceKey, workspace)
</script>

<template>
  <ConsoleLayout>
    <WorkspaceTabs />
  </ConsoleLayout>
  <SSHIdentityDialog />
</template>
