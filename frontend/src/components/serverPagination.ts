import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { showRequestError } from '@/components/feedback'
import { DEFAULT_PAGE_SIZE } from '@/components/pagination'
import type { PageResponse } from '@/types/api'

export function useServerPagination<T>(loader: (page: number, pageSize: number) => Promise<PageResponse<T>>) {
  const items = shallowRef<T[]>([])
  const page = ref(1)
  const pageSize = ref(DEFAULT_PAGE_SIZE)
  const total = ref(0)
  const loading = ref(false)
  const loadFailed = ref(false)
  let requestId = 0
  let active = true
  let resettingSize = false
  let resettingPage = false

  function invalidate() {
    requestId++
    if (!active) return
    items.value = []
    loadFailed.value = false
    loading.value = true
  }

  async function refresh(): Promise<void> {
    if (!active) return
    invalidate()
    const current = requestId
    try {
      const result = await loader(page.value, pageSize.value)
      if (!active || current !== requestId) return
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize.value))
      if (page.value > lastPage) {
        page.value = lastPage
        return
      }
      items.value = result.items
      total.value = result.total
    } catch (error) {
      if (!active || current !== requestId) return
      loadFailed.value = true
      showRequestError(error)
    } finally {
      if (active && current === requestId) loading.value = false
    }
  }

  function resetPage() {
    // 搜索防抖与新建操作由调用方主动刷新，重置时不触发额外请求。
    resettingPage = true
    page.value = 1
    resettingPage = false
  }
  watch(page, () => { if (!resettingPage && !resettingSize) void refresh() }, { flush: 'sync' })
  watch(pageSize, () => {
    resettingSize = true
    resetPage()
    resettingSize = false
    void refresh()
  }, { flush: 'sync' })
  onMounted(() => { void refresh() })
  onUnmounted(() => { active = false; invalidate() })

  return { items, page, pageSize, total, loading, loadFailed, refresh, resetPage, invalidate }
}
