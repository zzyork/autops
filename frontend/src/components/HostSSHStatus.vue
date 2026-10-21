<script setup lang="ts">
import { computed } from 'vue'
import { sshTestDisplay } from '@/components/sshTestDisplay'
import TestStatus from '@/components/TestStatus.vue'
import type { Host } from '@/types/api'

const props = defineProps<{ host: Host; display?: ReturnType<typeof sshTestDisplay> }>()
const appearance = computed(() => props.display ?? sshTestDisplay(props.host.connection_status))
</script>

<template>
  <TestStatus :status="appearance.status" :description="appearance.description" />
</template>
