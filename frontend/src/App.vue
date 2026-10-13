<script setup lang="ts">
import { provide } from 'vue'
import { useRouter } from 'vue-router'
import AssetsLayout from '@/components/AssetsLayout.vue'
import WorkspaceTabs from '@/components/WorkspaceTabs.vue'
import { createWorkspace, workspaceKey } from '@/components/workspace'

const workspace = createWorkspace(useRouter())
provide(workspaceKey, workspace)
</script>

<template>
  <AssetsLayout title="控制台">
    <WorkspaceTabs />
  </AssetsLayout>
</template>
