import { computed, ref, watch, type Ref } from 'vue'

export const PAGE_SIZES = [10, 20, 50, 100]
export const DEFAULT_PAGE_SIZE = 10

export function useListPagination<T>(items: Ref<T[]>) {
  const page = ref(1)
  const pageSize = ref(DEFAULT_PAGE_SIZE)
  const total = computed(() => items.value.length)
  const pageItems = computed(() => items.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
  function resetPage() { page.value = 1 }
  watch(pageSize, resetPage, { flush: 'sync' })
  watch(total, (count) => {
    page.value = Math.min(page.value, Math.max(1, Math.ceil(count / pageSize.value)))
  }, { flush: 'sync' })
  return { page, pageSize, total, pageItems, resetPage }
}
