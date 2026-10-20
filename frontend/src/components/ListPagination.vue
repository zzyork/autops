<script setup lang="ts">
import { computed } from 'vue'
import { ElConfigProvider, ElOption, ElPagination, ElSelect } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { PAGE_SIZES } from '@/components/pagination'

const props = withDefaults(defineProps<{ total: number; disabled?: boolean; compact?: boolean; totalKnown?: boolean }>(), { totalKnown: true })
const layout = computed(() => `${props.totalKnown ? 'total, ' : ''}slot, prev, ${props.compact ? '' : 'pager, '}next`)
const paginationLocale = { ...zhCn, el: { ...zhCn.el, pagination: { ...zhCn.el.pagination, total: '总计 {total} 条' } } }
const page = defineModel<number>('page', { required: true })
const pageSize = defineModel<number>('pageSize', { required: true })
const emit = defineEmits<{ change: [] }>()

function changePage(next: number) {
  if (next === page.value) return
  page.value = next
  emit('change')
}
function changeSize(next: number) {
  if (next === pageSize.value) return
  pageSize.value = next
  page.value = 1
  emit('change')
}
</script>

<template>
  <div class="list-pagination" :class="{ 'is-compact': compact }" aria-label="列表分页">
    <ElConfigProvider :locale="paginationLocale">
      <ElPagination :current-page="page" :page-size="pageSize" :total="total" :disabled="disabled" :layout="layout" @update:current-page="changePage">
        <div class="page-size-control">
          <span>每页数量</span>
          <ElSelect :model-value="pageSize" :disabled="disabled" aria-label="每页数量" @update:model-value="changeSize">
            <ElOption v-for="size in PAGE_SIZES" :key="size" :label="String(size)" :value="size" />
          </ElSelect>
        </div>
      </ElPagination>
    </ElConfigProvider>
  </div>
</template>

<style scoped>
.list-pagination { display: flex; justify-content: flex-end; padding: var(--ui-space-3) var(--ui-panel-padding); border-top: 1px solid var(--ui-border); }
.list-pagination :deep(.el-pagination) { align-items: center; --el-pagination-font-size: var(--ui-font-size-base); --el-pagination-button-height: var(--ui-inline-control-height); --el-pagination-button-width: var(--ui-inline-control-height); }
.list-pagination :deep(.el-pagination__total) { margin-right: var(--ui-space-4); color: var(--ui-text); font-size: var(--ui-font-size-base); line-height: var(--ui-control-height); white-space: nowrap; }
.page-size-control { display: flex; align-items: center; gap: var(--ui-space-2); margin-right: var(--ui-space-4); color: var(--ui-text); font-size: var(--ui-font-size-base); line-height: var(--ui-control-height); white-space: nowrap; }
.page-size-control .el-select { width: 80px; }
.page-size-control :deep(.el-select__wrapper) { min-height: var(--ui-control-height); }
.is-compact { flex: none; padding: var(--ui-space-2); }
.is-compact :deep(.el-pagination) { flex-wrap: wrap; justify-content: flex-end; gap: var(--ui-space-2); }
.is-compact :deep(.el-pagination > *) { margin: 0; }
</style>
