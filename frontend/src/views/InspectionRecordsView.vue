<script setup lang="ts">
import AssetsLayout from '@/components/AssetsLayout.vue'
import InspectionTaskList from '@/components/InspectionTaskList.vue'
</script>

<template>
  <AssetsLayout title="巡检记录" section="巡检管理">
    <main class="assets-main">
      <div class="assets-heading"><h1>巡检记录</h1></div>
      <InspectionTaskList records />
    </main>
  </AssetsLayout>
</template>
