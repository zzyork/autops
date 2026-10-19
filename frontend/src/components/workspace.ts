import { inject, nextTick, onScopeDispose, ref, shallowRef, watch, type InjectionKey, type Ref } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import { showNavigationBlocked } from './feedback'

interface WorkspaceTab {
  key: string
  title: string
  location: RouteLocationNormalizedLoaded
  scrollTop: number
}

export function createWorkspace(router: Router) {
  const tabs = shallowRef<WorkspaceTab[]>([])
  const activeKey = ref('')
  const menuCollapsed = ref(false)
  const assetsExpanded = ref(true)
  const inspectionsExpanded = ref(true)
  const settingsExpanded = ref(true)
  let navigationSequence = 0
  let pendingLocation: string | null = null
  let closing = false
  let savedScroll: { key: string; top: number } | null = null

  function saveScroll() {
    if (savedScroll?.key !== activeKey.value) savedScroll = { key: activeKey.value, top: window.scrollY }
  }

  function modalOpen() {
    if (!document.body.classList.contains('el-popup-parent--hidden')) return false
    showNavigationBlocked()
    return true
  }
  const removeGuard = router.beforeEach((to) => {
    if (modalOpen()) return false
    saveScroll()
    pendingLocation = to.fullPath
  })
  const removeAfter = router.afterEach((to, _from, failure) => {
    if (pendingLocation === to.fullPath) pendingLocation = null
    if (failure) savedScroll = null
  })
  const removeError = router.onError(() => { pendingLocation = null })
  onScopeDispose(() => { removeGuard(); removeAfter(); removeError() })

  watch(router.currentRoute, async (location) => {
    if (!location.matched.length || !location.name) return
    const sequence = ++navigationSequence
    const previous = tabs.value.find((tab) => tab.key === activeKey.value)
    if (previous) previous.scrollTop = savedScroll?.key === previous.key ? savedScroll.top : window.scrollY
    savedScroll = null
    const key = location.path
    const title = String(location.meta.title)
    const taskId = location.params.taskId
    const label = location.name === 'inspection-record-detail' ? `${title} · ${String(taskId)}` : title
    const existing = tabs.value.find((tab) => tab.key === key)
    tabs.value = existing
      ? tabs.value.map((tab) => tab.key === key ? { ...tab, location, title: label } : tab)
      : [...tabs.value, { key, title: label, location, scrollTop: 0 }]
    const changed = activeKey.value !== key
    activeKey.value = key
    if (changed) {
      await nextTick()
      if (sequence === navigationSequence) window.scrollTo({ top: existing?.scrollTop ?? 0, behavior: 'instant' })
    }
  }, { immediate: true })

  function select(key: string) {
    if (closing || modalOpen()) return
    const tab = tabs.value.find((item) => item.key === key)
    if (tab && key !== activeKey.value) {
      pendingLocation = tab.location.fullPath
      void router.push(tab.location.fullPath)
    }
  }

  async function close(key: string) {
    // 未完成的导航不删除目标标签，避免导航提交后把已关闭页面重新打开。
    if (closing || pendingLocation || modalOpen() || tabs.value.length <= 1) return
    const index = tabs.value.findIndex((tab) => tab.key === key)
    if (index < 0) return
    closing = true
    try {
      if (key === activeKey.value) {
        const next = tabs.value[index + 1] ?? tabs.value[index - 1]
        if (!next) return
        await router.push(next.location.fullPath)
        if (activeKey.value === key) return
      }
      tabs.value = tabs.value.filter((tab) => tab.key !== key)
      await nextTick()
      document.querySelector<HTMLElement>('.console-tabs .is-active[role="tab"]')?.focus({ preventScroll: true })
    } finally {
      closing = false
    }
  }

  function canSwitch(target: string | number) {
    if (String(target) === activeKey.value) return true
    if (closing || modalOpen()) return false
    saveScroll()
    return true
  }

  return { tabs, activeKey, menuCollapsed, assetsExpanded, inspectionsExpanded, settingsExpanded, select, close, canSwitch }
}

export const workspaceKey: InjectionKey<ReturnType<typeof createWorkspace>> = Symbol('workspace')
export const workspaceVisibleKey: InjectionKey<Ref<boolean>> = Symbol('workspace-visible')

export function useWorkspace() {
  const workspace = inject(workspaceKey)
  if (!workspace) throw new Error('控制台布局必须在工作区内使用')
  return workspace
}
