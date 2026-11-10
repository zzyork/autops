<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElButton } from 'element-plus'
import InspectionAnalysisReport from '@/components/InspectionAnalysisReport.vue'
import InspectionTaskHeader from '@/components/InspectionTaskHeader.vue'
import type { TaskDetail } from '@/types/inspections'

defineProps<{ task: TaskDetail }>()
const router = useRouter()
</script>

<template>
  <section class="inspection-detail" aria-label="巡检记录概览">
    <InspectionTaskHeader :task="task">
      <ElButton @click="router.push({ name: 'inspection-record-detail', params: { taskId: task.id } })">巡检记录详情</ElButton>
    </InspectionTaskHeader>
    <InspectionAnalysisReport :task-id="task.id" :task-status="task.status" />
  </section>
</template>
