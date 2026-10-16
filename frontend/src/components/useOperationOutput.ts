import { onUnmounted, ref, shallowRef, watch, type Ref } from 'vue'
import { RequestCancelledError } from '@/api/http'
import { watchOperation } from '@/api/operations'
import { showRequestError } from './feedback'
import type { OperationSnapshot } from '@/types/operations'

export function useOperationOutput(taskId: Ref<string | null>, hostId: Ref<number | null>, visible: Ref<boolean>, onDone: (id: string) => void) {
  const snapshot = shallowRef<OperationSnapshot | null>(null)
  const state = ref<'idle' | 'connecting' | 'connected' | 'disconnected' | 'done'>('idle')
  let generation = 0
  let controller: AbortController | null = null
  function stop() {
    generation++
    controller?.abort()
    controller = null
    if (state.value !== 'done') state.value = 'idle'
  }
  function connect() {
    stop()
    snapshot.value = null
    const id = taskId.value
    const host = hostId.value
    if (!visible.value || !id || host === null) return
    const current = generation
    const next = new AbortController()
    controller = next
    state.value = 'connecting'
    void watchOperation(id, host, next.signal, (value, done) => {
      if (current !== generation) return
      snapshot.value = value
      state.value = done ? 'done' : 'connected'
      if (done) onDone(id)
    }).catch((error: unknown) => {
      if (current !== generation || error instanceof RequestCancelledError) return
      state.value = 'disconnected'
      showRequestError(error)
    }).finally(() => { if (current === generation) controller = null })
  }
  watch([taskId, hostId, visible], () => {
    if (visible.value && taskId.value && hostId.value !== null) connect()
    else { stop(); snapshot.value = null }
  }, { immediate: true, flush: 'sync' })
  onUnmounted(stop)
  return { snapshot, state, connect, stop }
}
