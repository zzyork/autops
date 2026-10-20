<script setup lang="ts">
import { computed, watch } from 'vue'
import { ElButton } from 'element-plus'
import ListPagination from '@/components/ListPagination.vue'
import { useListPagination } from '@/components/pagination'
import type { AnalysisEvidence } from '@/types/inspections'

const props = defineProps<{ evidence: AnalysisEvidence[]; selectedIds: string[] | null }>()
const emit = defineEmits<{ clear: [] }>()
const entries = computed(() => {
  const logs = props.evidence.filter((item) => item.kind === 'log' && (!props.selectedIds || props.selectedIds.includes(item.id)))
  const originalGroups = new Set(logs.filter((item) => item.original_lines?.length).map((item) => item.group_id ?? item.id))
  return logs.flatMap((item) => {
    if (item.original_lines?.length) {
      return item.original_lines.map((line, index) => ({
        key: `${item.id}-${index}`, item, line, row: item.original_indices?.[index] ?? null,
      }))
    }
    if (originalGroups.has(item.group_id ?? item.id)) return []
    return [{ key: item.id, item, line: item.content, row: null }]
  })
})
const { page, pageSize, total, pageItems, resetPage } = useListPagination(entries)
watch(() => props.selectedIds, resetPage)
</script>

<template>
  <div class="analysis-evidence">
    <div class="analysis-evidence-toolbar">
      <span>{{ selectedIds ? '当前诊断组' : '全部日志' }} · {{ total }} 条证据</span>
      <ElButton v-if="selectedIds" size="small" @click="emit('clear')">查看全部证据</ElButton>
    </div>
    <div v-for="entry in pageItems" :key="entry.key" class="analysis-evidence-item">
      <strong>{{ entry.item.id }} · {{ entry.item.host_name }} ({{ entry.item.address }})</strong>
      <p class="ui-text-muted">{{ entry.item.source }}<template v-if="entry.item.source_table_index != null"> · 来源表 {{ entry.item.source_table_index }}</template><template v-if="entry.row != null"> · 结果行 {{ entry.row }}</template></p>
      <p>{{ entry.line }}</p>
    </div>
    <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" />
  </div>
</template>

<style scoped>
.analysis-evidence { display: grid; gap: var(--ui-space-2); min-width: 0; }
.analysis-evidence-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: var(--ui-space-2); }
.analysis-evidence-item { padding: var(--ui-space-3) var(--ui-panel-padding); border-bottom: 1px solid var(--ui-border); }
.analysis-evidence-item :is(p, strong) { overflow-wrap: anywhere; white-space: pre-wrap; }
.analysis-evidence-item p { margin: var(--ui-space-2) 0 0; }
.analysis-evidence-item > p:last-child { font-family: var(--ui-font-mono); font-size: var(--ui-font-size-code); line-height: var(--ui-line-height-code); }
</style>
