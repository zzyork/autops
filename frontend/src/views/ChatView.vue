<script setup lang="ts">
import { computed, inject, nextTick, onMounted, onUnmounted, ref, useId, watch } from 'vue'
import { ElButton, ElInput, ElMessageBox } from 'element-plus'
import ChatMessageItem from '@/components/ChatMessageItem.vue'
import ChatProposalCard from '@/components/ChatProposalCard.vue'
import ChatTaskCard from '@/components/ChatTaskCard.vue'
import FieldError from '@/components/FieldError.vue'
import { focusFormFeedback } from '@/components/formFeedback'
import ListPagination from '@/components/ListPagination.vue'
import { useServerPagination } from '@/components/serverPagination'
import { workspaceVisibleKey } from '@/components/workspace'
import { createSession, decideProposal, deleteSession, getFeatureModels, getSession, getSessionActivity, listConnections, listSessionsPage, registerOperation, sendMessage, stopSession } from '@/api/ai'
import { showRequestError } from '@/components/feedback'
import { timeLabel } from '@/components/timeDisplay'
import type { ChatSession, FeatureModelsConfig, ModelConnection, SessionActivity, SessionSummary } from '@/types/ai'
import '@/styles/ai.css'

const connections = ref<ModelConnection[]>([])
const connectionsLoaded = ref(false)
const connectionsLoading = ref(false)
const featureModels = ref<FeatureModelsConfig | null>(null)
const { items: sessions, page, pageSize, total, loading: sessionsLoading, loadFailed: sessionsFailed, refresh: loadSessions, resetPage } = useServerPagination(listSessionsPage)
const sessionsLoaded = ref(false)
const selectedId = ref<string | null>(null)
const detail = ref<ChatSession | null>(null)
const detailLoaded = ref(false)
const detailLoading = ref(false)
const input = ref('')
const inputError = ref('')
const inputInvalid = ref(false)
const streamingText = ref('')
const sendingContent = ref('')
const operation = ref<'create' | 'send' | 'decision' | 'delete' | null>(null)
const visible = inject(workspaceVisibleKey, ref(true))
const pageVisible = ref(!document.hidden)
const activity = ref<SessionActivity | null>(null)
const activityFailed = ref(false)
const activityLoading = ref(false)
const stopPending = ref(false)
const stopRequested = ref(false)
const conversation = ref<HTMLElement | null>(null)
const composer = ref<HTMLElement | null>(null)
const inputId = useId()
const newChatConnection = computed(() => {
  if (!connectionsLoaded.value || !featureModels.value) return undefined
  return featureModels.value.chat_connection_id === null
    ? connections.value.find((item) => item.is_default)
    : connections.value.find((item) => item.id === featureModels.value?.chat_connection_id)
})
const newChatAvailable = computed(() => !!newChatConnection.value)
const selectedConnection = computed(() => connections.value.find((item) => item.id === detail.value?.connection_id))
const interactionBusy = computed(() => !!operation.value || stopPending.value)
const running = computed(() => operation.value === 'send' || operation.value === 'decision' || stopPending.value || activity.value?.running === true)
const stopping = computed(() => stopPending.value || stopRequested.value || activity.value?.stopping === true)
const messageResultConfirmed = ref(false)
const sendDisabled = computed(() => interactionBusy.value || running.value || (selectedId.value
  ? !detailLoaded.value || activity.value === null || activityFailed.value
  : !connectionsLoaded.value || connectionsLoading.value || !newChatAvailable.value))
let active = true
let connectionSequence = 0
let detailSequence = 0
let streamController: AbortController | null = null
let decisionController: AbortController | null = null
let registration: Promise<string> | null = null
let decisionSubmitted = false
let activityController: AbortController | null = null
let stopController: AbortController | null = null
let activityTimer: ReturnType<typeof setTimeout> | undefined
let activitySequence = 0
let selectInitialSession = true
const MAX_MESSAGE_LENGTH = 8000
const ACTIVITY_POLL_MS = 1000
let messageResultSequence = 0

function invalidateMessageResult(): void {
  messageResultSequence++
  messageResultConfirmed.value = false
}

async function loadActivity(reloadDetail = false): Promise<void> {
  clearTimeout(activityTimer)
  const id = selectedId.value
  if (!active || !visible.value || !pageVisible.value || !id || stopPending.value) return
  activityController?.abort()
  const controller = new AbortController()
  activityController = controller
  const current = ++activitySequence
  // failed 可能是执行中占位；确认必须来自本轮操作结束后发起的新查询。
  const messageSequence = messageResultSequence
  const canConfirmMessages = operation.value === null
  const isCurrent = () => active && visible.value && pageVisible.value && selectedId.value === id && current === activitySequence
  activityLoading.value = true
  try {
    const result = await getSessionActivity(id, controller.signal)
    if (!isCurrent()) return
    const wasRunning = activity.value?.running === true
    activity.value = result
    activityFailed.value = false
    messageResultConfirmed.value = messageSequence === messageResultSequence
      && canConfirmMessages && operation.value === null && !result.running
    if (result.running) {
      activityTimer = setTimeout(() => { void loadActivity() }, ACTIVITY_POLL_MS)
    } else if ((wasRunning || reloadDetail) && operation.value !== 'send') {
      if (await loadDetail(id) && isCurrent()) void loadSessions()
    }
  } catch (error) {
    if (!isCurrent() || controller.signal.aborted) return
    activityFailed.value = true
    messageResultConfirmed.value = false
    showRequestError(error)
  } finally {
    if (isCurrent()) activityLoading.value = false
    if (activityController === controller) activityController = null
  }
}

async function stop(): Promise<void> {
  if (!running.value || stopping.value) return
  const id = selectedId.value
  if (!id) return
  const controller = new AbortController()
  stopController = controller
  stopPending.value = true
  invalidateMessageResult()
  clearTimeout(activityTimer)
  activitySequence++
  activityController?.abort()
  activityLoading.value = false
  if (streamController || decisionController) stopRequested.value = true
  const pendingRegistration = registration
  if (decisionController && !decisionSubmitted) {
    stopRequested.value = true
    decisionController.abort()
  }
  let accepted = false
  try {
    if (pendingRegistration) {
      try {
        await pendingRegistration
      } catch (error) {
        if (active && selectedId.value === id) showRequestError(error)
      }
    }
    if (!active || selectedId.value !== id || controller.signal.aborted) return
    const result = await stopSession(id, controller.signal)
    if (!active || selectedId.value !== id || controller.signal.aborted) return
    activity.value = result
    activityFailed.value = false
    accepted = true
  } catch (error) {
    if (active && selectedId.value === id && !controller.signal.aborted) {
      activityFailed.value = true
      showRequestError(error)
    }
  } finally {
    if (active && selectedId.value === id) {
      stopPending.value = false
      if (accepted && id) void loadActivity(true)
    }
    if (stopController === controller) stopController = null
  }
}

watch([selectedId, visible, pageVisible], ([id, isVisible, isPageVisible], [previousId]) => {
  clearTimeout(activityTimer)
  activitySequence++
  activityController?.abort()
  activityLoading.value = false
  if (id !== previousId) {
    invalidateMessageResult()
    activity.value = null
    activityFailed.value = false
  }
  if (id && isVisible && isPageVisible) void loadActivity()
})

async function loadConnections(): Promise<boolean> {
  const current = ++connectionSequence
  connectionsLoaded.value = false
  connectionsLoading.value = true
  try {
    const [items, config] = await Promise.all([listConnections(), getFeatureModels()])
    if (!active || current !== connectionSequence) return false
    connections.value = items
    featureModels.value = config
    connectionsLoaded.value = true
    return true
  } catch {
    if (!active || current !== connectionSequence) return false
    featureModels.value = null
    showRequestError()
    return false
  } finally { if (active && current === connectionSequence) connectionsLoading.value = false }
}
watch(sessionsLoading, (loading) => {
  if (loading) { sessionsLoaded.value = false; return }
  if (sessionsFailed.value) return
  sessionsLoaded.value = true
  if (selectInitialSession && !selectedId.value && sessions.value.length) select(sessions.value[0]!.id)
  selectInitialSession = false
})
async function loadDetail(id: string, notify = true): Promise<boolean> {
  const current = ++detailSequence
  detailLoaded.value = false
  detailLoading.value = true
  try {
    const session = await getSession(id)
    if (!active || current !== detailSequence || selectedId.value !== id) return false
    detail.value = session
    detailLoaded.value = true
    return true
  } catch {
    if (active && current === detailSequence && selectedId.value === id && notify) showRequestError()
    return false
  } finally { if (active && current === detailSequence) detailLoading.value = false }
}
function select(id: string) {
  if (interactionBusy.value || selectedId.value === id) return
  selectedId.value = id
  detail.value = null
  input.value = ''
  inputError.value = ''
  inputInvalid.value = false
  void loadDetail(id)
}
function newChat() {
  if (interactionBusy.value) return
  selectInitialSession = false
  resetPage()
  void loadSessions()
  detailSequence++
  selectedId.value = null
  detail.value = null
  detailLoaded.value = false
  detailLoading.value = false
  input.value = ''
  inputError.value = ''
  inputInvalid.value = false
  void loadConnections()
}
function handleInputKeydown(event: Event) {
  if (!(event instanceof KeyboardEvent)) {
    return
  }
  // 输入法确认候选词时 isComposing 可能已结束，仍需检查 229。
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing || event.keyCode === 229) {
    return
  }
  event.preventDefault()
  void send()
}
async function send() {
  const content = input.value.trim()
  if (sendDisabled.value) return
  if (!content || content.length > MAX_MESSAGE_LENGTH) {
    inputError.value = `消息须填写且不超过 ${MAX_MESSAGE_LENGTH} 字符。`
    inputInvalid.value = true
    focusFormFeedback(composer.value)
    return
  }
  inputError.value = ''
  inputInvalid.value = false
  invalidateMessageResult()
  operation.value = selectedId.value ? 'send' : 'create'
  sendingContent.value = input.value
  streamingText.value = ''
  stopRequested.value = false
  let id = selectedId.value
  const controller = new AbortController()
  streamController = controller
  try {
    if (!id) {
      if (!await loadConnections() || !active || controller.signal.aborted) return
      if (!newChatAvailable.value) {
        inputError.value = featureModels.value?.chat_connection_id === null ? '尚未指定主模型。' : '指定的对话模型连接不存在，请重新配置。'
        return
      }
      const summary = await createSession()
      if (!active || controller.signal.aborted) return
      id = summary.id
      selectedId.value = id
      detail.value = { ...summary, messages: [], proposals: [] }
      detailLoaded.value = true
      selectInitialSession = false
      resetPage()
      void loadSessions()
    }
    operation.value = 'send'
    const pending = registerOperation(id, controller.signal)
    registration = pending
    const operationId = await pending
    if (!active || controller.signal.aborted || stopRequested.value) return
    input.value = ''
    const session = await sendMessage(id, content, controller.signal, (text) => {
      if (active && selectedId.value === id && !controller.signal.aborted && !stopRequested.value) streamingText.value += text
    }, operationId)
    if (!active || selectedId.value !== id || controller.signal.aborted) return
    detail.value = session
    void loadSessions()
  } catch {
    if (active && selectedId.value === id && !controller.signal.aborted && !stopRequested.value && !stopPending.value) {
      input.value = sendingContent.value
      showRequestError()
      if (id && await loadDetail(id, false)) void loadSessions()
    }
  } finally {
    const stopped = stopRequested.value || controller.signal.aborted
    if (active) {
      sendingContent.value = ''
      streamingText.value = ''
      invalidateMessageResult()
      operation.value = null
      stopRequested.value = false
    }
    if (streamController === controller) streamController = null
    registration = null
    if (active && selectedId.value === id && !activityFailed.value) void loadActivity(stopped)
  }
}
async function decide(proposalId: string, approve: boolean) {
  const id = selectedId.value
  if (!id || interactionBusy.value || stopping.value || !detailLoaded.value) return
  invalidateMessageResult()
  operation.value = 'decision'
  const controller = new AbortController()
  decisionController = controller
  decisionSubmitted = false
  try {
    const session = await decideProposal(id, proposalId, approve, {
      signal: controller.signal,
      isCurrent: () => active && selectedId.value === id && !stopRequested.value,
      onRegister: (pending) => {
        decisionSubmitted = true
        registration = pending
      },
    })
    if (!active || selectedId.value !== id || controller.signal.aborted) return
    detail.value = session
    void loadSessions()
  } catch (error) {
    if (active && selectedId.value === id && !controller.signal.aborted && !stopRequested.value && !stopPending.value) {
      showRequestError(error)
      if (await loadDetail(id, false)) void loadSessions()
    }
  }
  finally {
    const stopped = stopRequested.value || controller.signal.aborted
    if (active) {
      invalidateMessageResult()
      operation.value = null
      stopRequested.value = false
      if (!activityFailed.value) void loadActivity(stopped)
    }
    registration = null
    decisionSubmitted = false
    if (decisionController === controller) decisionController = null
  }
}
async function remove(session: SessionSummary) {
  if (interactionBusy.value) return
  operation.value = 'delete'
  try {
    await ElMessageBox.confirm(`确定删除会话“${session.title}”及其对话历史吗？已创建的巡检任务不会随会话删除。`, '删除会话', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'delete-confirm-button',
    })
  } catch { operation.value = null; return }
  if (!active) return
  try {
    await deleteSession(session.id)
    if (!active) return
    if (selectedId.value === session.id) {
      detailSequence++
      selectedId.value = null
      detail.value = null
      detailLoaded.value = false
      detailLoading.value = false
      input.value = ''
    }
    void loadSessions()
  } catch { if (active) showRequestError() }
  finally { if (active) operation.value = null }
}
watch([() => detail.value?.messages.length, streamingText, () => detail.value?.proposals.length], async () => {
  await nextTick()
  if (conversation.value) conversation.value.scrollTop = conversation.value.scrollHeight
})
function refreshActivityOnFocus(): void {
  if (!activityFailed.value) void loadActivity()
}
function updatePageVisibility(): void {
  pageVisible.value = !document.hidden
}
onMounted(() => {
  void loadConnections()
  window.addEventListener('focus', refreshActivityOnFocus)
  document.addEventListener('visibilitychange', updatePageVisibility)
})
onUnmounted(() => {
  active = false
  connectionSequence++
  detailSequence++
  streamController?.abort()
  decisionController?.abort()
  activitySequence++
  clearTimeout(activityTimer)
  activityController?.abort()
  stopController?.abort()
  window.removeEventListener('focus', refreshActivityOnFocus)
  document.removeEventListener('visibilitychange', updatePageVisibility)
})
</script>

<template>
    <main class="console-main ai-main">
      <div class="ai-workspace">
        <aside class="ai-sessions" aria-label="会话列表">
          <div class="ai-pane-heading"><strong>会话</strong><ElButton type="primary" :disabled="interactionBusy" @click="newChat">新建对话</ElButton></div>
          <div class="ai-session-scroll">
            <p v-if="sessionsLoading && !sessionsLoaded" class="ai-placeholder">正在读取会话...</p>
            <p v-else-if="!sessionsLoaded" class="ui-load-retry">会话未加载。<ElButton @click="loadSessions()">重试</ElButton></p>
            <p v-else-if="!sessions.length" class="ai-placeholder">暂无会话</p>
            <div v-for="session in sessionsLoaded ? sessions : []" :key="session.id" class="ai-session-row" :class="{ active: selectedId === session.id }">
              <button type="button" class="ai-session-select" :disabled="interactionBusy" :title="session.title" @click="select(session.id)"><strong>{{ session.title }}</strong><small>{{ timeLabel(session.updated_at) }}</small></button>
              <ElButton link type="danger" :disabled="interactionBusy" :aria-label="`删除会话 ${session.title}`" title="删除会话" @click="remove(session)">删除</ElButton>
            </div>
          </div>
          <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :total-known="sessionsLoaded && !sessionsLoading" :disabled="sessionsLoading || !sessionsLoaded || interactionBusy" compact />
        </aside>
        <section class="ai-chat" aria-label="对话内容">
          <div class="ai-pane-heading"><strong>{{ detail?.title ?? (selectedId ? '对话' : '新对话') }}</strong><span v-if="detailLoaded && selectedConnection" class="ui-text-muted">{{ selectedConnection.name }}</span></div>
          <div ref="conversation" class="ai-conversation" role="log" aria-live="polite">
            <p v-if="selectedId && detailLoading" class="ai-placeholder">正在读取历史...</p>
            <p v-else-if="selectedId && !detailLoaded" class="ui-load-retry">历史未加载。<ElButton @click="loadDetail(selectedId!)">重试</ElButton></p>
            <template v-else-if="detailLoaded && detail">
              <ChatMessageItem v-for="message in detail.messages" :key="message.id" :message="message" :result-confirmed="messageResultConfirmed" />
              <ChatMessageItem v-if="operation === 'send'" :message="{ role: 'user', content: sendingContent.trim() }" />
              <ChatMessageItem v-if="operation === 'send' && streamingText" :message="{ role: 'assistant', content: streamingText }" />
              <template v-for="proposal in detail.proposals" :key="proposal.id"><ChatProposalCard :proposal="proposal" :busy="interactionBusy || stopping" @decide="decide" /><ChatTaskCard v-if="proposal.task_id" :task-id="proposal.task_id" @activity="refreshActivityOnFocus" /></template>
              <p v-if="!detail.messages.length && !detail.proposals.length && operation !== 'send'" class="ai-placeholder">开始对话</p>
            </template>
            <template v-else-if="!selectedId">
              <p v-if="connectionsLoading && !connectionsLoaded" class="ai-placeholder">正在读取功能模型配置与连接...</p>
              <p v-else-if="!connectionsLoaded" class="ui-load-retry">功能模型配置或连接未加载。<ElButton @click="loadConnections">重试</ElButton></p>
              <p v-else-if="!newChatAvailable" class="ai-placeholder">{{ featureModels?.chat_connection_id === null ? '尚未指定主模型。' : '指定的对话模型连接不存在，请重新配置。' }}<RouterLink to="/settings/models">前往模型配置</RouterLink></p>
              <p v-else class="ai-placeholder">开始对话</p>
            </template>
          </div>
          <div ref="composer" class="ai-composer">
            <ElInput
              :id="inputId"
              v-model="input"
              type="textarea"
              :rows="3"
              :maxlength="MAX_MESSAGE_LENGTH"
              show-word-limit
              :aria-invalid="inputInvalid"
              :aria-describedby="inputError ? `${inputId}-error` : undefined"
              :disabled="sendDisabled"
              placeholder="输入运维问题，Enter 发送"
              @input="
                inputError = '';
                inputInvalid = false
              "
              @keydown="handleInputKeydown"
            />
            <FieldError v-if="inputError" :id="`${inputId}-error`" :message="inputError" />
            <p v-if="selectedId && activityFailed" class="ui-load-retry">
              运行状态未确认。<ElButton :loading="activityLoading" :disabled="stopPending" @click="loadActivity(true)">刷新状态</ElButton>
            </p>
            <div class="ai-composer-actions">
              <span class="ui-text-muted ui-execution-status" role="status"
                :data-execution-state="operation === 'create' || operation === 'send' || operation === 'decision' ? 'in-progress' : undefined">
                <template v-if="stopping">正在中止...</template>
                <template v-else-if="operation === 'create'">正在创建会话...</template>
                <template v-else-if="operation === 'send'">正在接收回复...</template>
                <template v-else-if="operation === 'decision'">正在提交巡检计划...</template>
                <template v-else-if="activity?.running">后台任务尚未结束...</template>
              </span>
              <ElButton
                :type="running ? 'danger' : 'primary'"
                :circle="running"
                :loading="operation === 'create'"
                :class="{ 'ai-composer-stop': running }"
                :aria-label="running ? (stopping ? '正在中止' : '中止当前会话的回复和后台任务') : '发送'"
                :title="running ? (stopping ? '正在中止' : '中止当前会话的回复和后台任务') : '发送'"
                :aria-disabled="running && stopping"
                :disabled="!running && (sendDisabled || !input.trim())"
                @click="running ? stop() : send()"
              >
                <svg v-if="running" class="ai-stop-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <rect x="5" y="5" width="14" height="14" rx="1" />
                </svg>
                <template v-else>发送</template>
              </ElButton>
            </div>
          </div>
        </section>
      </div>
    </main>
</template>
