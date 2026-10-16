<script setup lang="ts">
import { computed } from 'vue'
import { sshTestDisplay } from '@/components/sshTestDisplay'
import TestStatus from '@/components/TestStatus.vue'
import type { Host } from '@/types/api'

const props = defineProps<{ host: Host }>()
const appearance = computed(() => sshTestDisplay(props.host.connection_status))
</script>

<template>
  <TestStatus :status="appearance.status" :description="appearance.description" />
</template>
