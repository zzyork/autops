<script setup lang="ts">
import { computed, inject, nextTick, onMounted, onUnmounted, ref, shallowRef, useId, watch } from 'vue'
import { ElButton, ElInput, ElMessageBox } from 'element-plus'
import ChatMessageItem from '@/components/ChatMessageItem.vue'
import ChatMessageEditor from '@/components/ChatMessageEditor.vue'
import ChatProposalCard from '@/components/ChatProposalCard.vue'
import ChatTaskCard from '@/components/ChatTaskCard.vue'
import FieldError from '@/components/FieldError.vue'
import { focusFormFeedback } from '@/components/formFeedback'
import ListPagination from '@/components/ListPagination.vue'
import { useServerPagination } from '@/components/serverPagination'
import { workspaceVisibleKey } from '@/components/workspace'
import { createMessageBranch, createSession, decideProposal, deleteSession, getFeatureModels, getSession, getSessionActivity, listConnections, listSessionsPage, regenerateMessage, registerOperation, sendMessage, stopSession } from '@/api/ai'
import { SSHConnectionFailedError } from '@/api/http'
import { showRequestError } from '@/components/feedback'
import { timeLabel } from '@/components/timeDisplay'
import type { ChatMessage, ChatSession, FeatureModelsConfig, ModelConnection, SessionActivity, SessionSummary } from '@/types/ai'
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
const operation = ref<'create' | 'branch' | 'send' | 'decision' | 'delete' | null>(null)
const editingMessage = ref<ChatMessage | null>(null)
const editDraft = ref('')
const regeneratingMessageId = ref<string | null>(null)
const regenerationError = ref('')
const branchError = ref('')
const decisionError = shallowRef<{ proposalId: string; message: string } | null>(null)
const branchOrigin = ref<{ id: string; sourceId: string; sourceTitle: string } | null>(null)
// 创建分支时保留原会话未发送的草稿，返回原会话后恢复。
const preservedDrafts = new Map<string, string>()
const visible = inject(workspaceVisibleKey, ref(true))
const pageVisible = ref(!document.hidden)
const activity = ref<SessionActivity | null>(null)
const activityFailed = ref(false)
const activityLoading = ref(false)
const stopPending = ref(false)
const stopRequested = ref(false)
const conversation = ref<HTMLElement | null>(null)
const composer = ref<HTMLElement | null>(null)
const composerFocusId = ref<string | null>(null)
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
const navigationBusy = computed(() => interactionBusy.value || editingMessage.value !== null)
const running = computed(() => operation.value === 'send' || operation.value === 'decision' || stopPending.value || activity.value?.running === true)
const stopping = computed(() => stopPending.value || stopRequested.value || activity.value?.stopping === true)
const messageResultConfirmed = ref(false)
const sendDisabled = computed(() => interactionBusy.value || running.value || (selectedId.value
  ? !detailLoaded.value || activity.value === null || activityFailed.value
  : !connectionsLoaded.value || connectionsLoading.value || !newChatAvailable.value))
const historyActionsDisabled = computed(() => sendDisabled.value || !messageResultConfirmed.value)
const messageActionsDisabled = computed(() => historyActionsDisabled.value || editingMessage.value !== null)
const editingSourceMissing = computed(() => editingMessage.value !== null && detail.value !== null
  && !detail.value.messages.some((message) => message.id === editingMessage.value?.id))
const editRequestError = computed(() => editingSourceMissing.value
  ? '原消息已被其他操作移除，草稿已保留。请取消编辑后重新选择消息。'
  : regenerationError.value)
const messageRows = computed(() => {
  const messages = detail.value?.messages ?? []
  const index = messages.findIndex((message) => message.id === regeneratingMessageId.value)
  let displayed = index < 0 ? messages : messages.slice(0, index)
  // 另一页面重新生成可能移除编辑目标，仍保留草稿与取消入口。
  if (editingSourceMissing.value && editingMessage.value && !regeneratingMessageId.value) {
    displayed = [...displayed, editingMessage.value]
  }
  let retryMessage: ChatMessage | undefined
  return displayed.map((message) => {
    if (message.role === 'user') retryMessage = message
    return { message, retryMessage }
  })
})
const displayedProposals = computed(() => {
  const session = detail.value
  if (!session || operation.value === 'send') return []
  // 底部只展示最新回复的结果，避免历史计划继续占用当前确认入口。
  const messageId = messageRows.value.filter(({ message }) => message.role === 'assistant')
    .at(-1)?.retryMessage?.id
  if (!messageId) return []
  return session.proposals.filter((proposal) => session.proposal_message_ids[proposal.id] === messageId)
})
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
      if (await loadDetail(id) && isCurrent()) {
        if (messageSequence === messageResultSequence && canConfirmMessages && operation.value === null) {
          regenerationError.value = ''
        }
        void loadSessions()
      }
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
    decisionError.value = null
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
  if (navigationBusy.value || selectedId.value === id) return
  selectedId.value = id
  detail.value = null
  input.value = preservedDrafts.get(id) ?? ''
  preservedDrafts.delete(id)
  inputError.value = ''
  inputInvalid.value = false
  branchError.value = ''
  regenerationError.value = ''
  void loadDetail(id)
}
function newChat() {
  if (navigationBusy.value) return
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
  branchError.value = ''
  regenerationError.value = ''
  void loadConnections()
}

function editMessage(message: ChatMessage): void {
  if (messageActionsDisabled.value || message.role !== 'user') return
  regenerationError.value = ''
  editDraft.value = message.content
  editingMessage.value = message
}

function closeEditor(): void {
  if (interactionBusy.value) return
  if (editingSourceMissing.value) composerFocusId.value = selectedId.value
  editingMessage.value = null
  editDraft.value = ''
}

function activateBranch(session: ChatSession, source: ChatSession): void {
  preservedDrafts.set(source.id, input.value)
  detailSequence++
  selectedId.value = session.id
  detail.value = session
  detailLoaded.value = true
  detailLoading.value = false
  input.value = ''
  inputError.value = ''
  inputInvalid.value = false
  editingMessage.value = null
  editDraft.value = ''
  branchOrigin.value = { id: session.id, sourceId: source.id, sourceTitle: source.title }
  composerFocusId.value = session.id
  selectInitialSession = false
  resetPage()
  void loadSessions()
}

async function fork(message: ChatMessage): Promise<void> {
  const source = detail.value
  if (!source || messageActionsDisabled.value) return
  const id = source.id
  branchError.value = ''
  invalidateMessageResult()
  operation.value = 'branch'
  const controller = new AbortController()
  streamController = controller
  try {
    const session = await createMessageBranch(id, message.id, { include_message: true }, controller.signal)
    if (!active || selectedId.value !== id || controller.signal.aborted) return
    activateBranch(session, source)
  } catch (error) {
    if (active && selectedId.value === id && !controller.signal.aborted) {
      branchError.value = '分支创建结果未确认，请刷新会话列表检查后再操作。'
      showRequestError(error)
    }
  } finally {
    if (streamController === controller) streamController = null
    if (active) {
      operation.value = null
      void loadActivity()
    }
  }
}

async function retry(message: ChatMessage): Promise<void> {
  if (messageActionsDisabled.value || message.role !== 'user') return
  await generateReply(message.content, message)
}

async function submitEdit(content: string): Promise<void> {
  const message = editingMessage.value
  if (message) await generateReply(content, message)
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
  if (sendDisabled.value || editingMessage.value) return
  if (!content || content.length > MAX_MESSAGE_LENGTH) {
    inputError.value = `消息须填写且不超过 ${MAX_MESSAGE_LENGTH} 字符。`
    inputInvalid.value = true
    focusFormFeedback(composer.value)
    return
  }
  await generateReply(content)
}

async function generateReply(content: string, sourceMessage?: ChatMessage): Promise<void> {
  if (sendDisabled.value || sourceMessage && historyActionsDisabled.value) return
  const source = sourceMessage ? detail.value : null
  if (sourceMessage && !source?.messages.some((message) => message.id === sourceMessage.id)) return
  inputError.value = ''
  inputInvalid.value = false
  branchError.value = ''
  regenerationError.value = ''
  regeneratingMessageId.value = sourceMessage?.id ?? null
  invalidateMessageResult()
  operation.value = 'send'
  if (!selectedId.value) operation.value = 'create'
  sendingContent.value = content
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
      detail.value = { ...summary, messages: [], proposals: [], proposal_message_ids: {} }
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
    if (!sourceMessage) input.value = ''
    const onToken = (text: string): void => {
      if (active && selectedId.value === id && !controller.signal.aborted && !stopRequested.value) streamingText.value += text
    }
    let session: ChatSession
    if (sourceMessage && source) {
      session = await regenerateMessage(id, sourceMessage.id, {
        content, expected_updated_at: source.updated_at, operation_id: operationId,
      }, controller.signal, onToken)
    } else {
      session = await sendMessage(id, content, controller.signal, onToken, operationId)
    }
    if (!active || selectedId.value !== id || controller.signal.aborted) return
    detail.value = session
    if (sourceMessage) {
      editingMessage.value = null
      editDraft.value = ''
      composerFocusId.value = id
    }
    void loadSessions()
  } catch (error) {
    if (active && selectedId.value === id && !controller.signal.aborted && !stopRequested.value && !stopPending.value) {
      showRequestError(error)
      if (sourceMessage) {
        regenerationError.value = '本次重新生成结果未确认，请刷新对话核对后再操作。'
      } else {
        input.value = sendingContent.value
      }
      if (id && await loadDetail(id, false)) void loadSessions()
    }
  } finally {
    const stopped = stopRequested.value || controller.signal.aborted
    if (active) {
      sendingContent.value = ''
      streamingText.value = ''
      regeneratingMessageId.value = null
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
  if (!id || navigationBusy.value || stopping.value || !detailLoaded.value) return
  decisionError.value = null
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
      if (error instanceof SSHConnectionFailedError) {
        const proposal = detail.value?.proposals.find((item) => item.id === proposalId)
        const host = error.target.target_type === 'host'
          ? proposal?.hosts.find((item) => item.id === error.target.target_id) : undefined
        const hostLabel = host ? `${host.name}（${host.address}）：` : ''
        decisionError.value = {
          proposalId,
          message: `${hostLabel}${error.message} 本次巡检尚未提交，请检查连接后再次确认计划。`,
        }
      }
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
  if (navigationBusy.value) return
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
    preservedDrafts.delete(session.id)
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
watch([() => messageRows.value.length, streamingText, () => displayedProposals.value.length], async () => {
  await nextTick()
  if (conversation.value) conversation.value.scrollTop = conversation.value.scrollHeight
})
watch([historyActionsDisabled, selectedId, visible, composerFocusId], ([disabled, id, isVisible, focusId]) => {
  if (!focusId) return
  if (id !== focusId) {
    composerFocusId.value = null
    return
  }
  if (disabled || !isVisible || editingMessage.value) return
  const textarea = composer.value?.querySelector('textarea')
  if (!textarea || textarea.disabled) return
  textarea.focus()
  composerFocusId.value = null
}, { flush: 'post' })
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
          <div class="ai-pane-heading"><strong>会话</strong><ElButton type="primary" :disabled="navigationBusy" @click="newChat">新建对话</ElButton></div>
          <div class="ai-session-scroll">
            <p v-if="sessionsLoading && !sessionsLoaded" class="ai-placeholder">正在读取会话...</p>
            <p v-else-if="!sessionsLoaded" class="ui-load-retry">会话未加载。<ElButton @click="loadSessions()">重试</ElButton></p>
            <p v-else-if="!sessions.length" class="ai-placeholder">暂无会话</p>
            <div v-for="session in sessionsLoaded ? sessions : []" :key="session.id" class="ai-session-row" :class="{ active: selectedId === session.id }">
              <button type="button" class="ai-session-select" :disabled="navigationBusy" :title="session.title" @click="select(session.id)"><strong>{{ session.title }}</strong><small>{{ timeLabel(session.updated_at) }}</small></button>
              <ElButton link type="danger" :disabled="navigationBusy" :aria-label="`删除会话 ${session.title}`" title="删除会话" @click="remove(session)">删除</ElButton>
            </div>
          </div>
          <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :total-known="sessionsLoaded && !sessionsLoading" :disabled="sessionsLoading || !sessionsLoaded || navigationBusy" compact />
        </aside>
        <section class="ai-chat" aria-label="对话内容">
          <div class="ai-pane-heading"><strong>{{ detail?.title ?? (selectedId ? '对话' : '新对话') }}</strong><span v-if="detailLoaded && selectedConnection" class="ui-text-muted">{{ selectedConnection.name }}</span></div>
          <div v-if="branchOrigin && branchOrigin.id === selectedId" class="ai-branch-notice">
            <span class="ui-text-muted" role="status">已从“{{ branchOrigin.sourceTitle }}”创建分支。原对话的巡检计划与任务保留在原会话中。</span>
            <ElButton link type="primary" :disabled="navigationBusy" @click="select(branchOrigin.sourceId)">返回原对话</ElButton>
          </div>
          <div ref="conversation" class="ai-conversation" role="log" aria-live="polite">
            <p v-if="selectedId && detailLoading" class="ai-placeholder">正在读取历史…</p>
            <p v-else-if="selectedId && !detailLoaded" class="ui-load-retry">{{ editingMessage ? '历史刷新失败，当前编辑内容已保留。' : '历史未加载。' }}<ElButton @click="loadDetail(selectedId!)">重试</ElButton></p>
            <!-- 历史刷新期间保留原位编辑入口，失败时仍可取消编辑。 -->
            <template v-if="detail && (detailLoaded || editingMessage)">
              <ChatMessageItem
                v-for="row in messageRows"
                :key="row.message.id"
                :message="row.message"
                :result-confirmed="messageResultConfirmed"
                :actions-disabled="messageActionsDisabled"
                :retryable="!!row.retryMessage"
                :editing="editingMessage?.id === row.message.id"
                @edit="editMessage(row.message)"
                @retry="row.retryMessage && retry(row.retryMessage)"
                @branch="fork(row.message)"
              >
                <template #editor>
                  <ChatMessageEditor
                    v-model="editDraft"
                    :busy="interactionBusy"
                    :disabled="historyActionsDisabled || editingSourceMissing"
                    :request-error="editRequestError"
                    :refreshing="activityLoading || detailLoading"
                    @submit="submitEdit"
                    @close="closeEditor"
                    @refresh="loadActivity(true)"
                  />
                </template>
              </ChatMessageItem>
              <ChatMessageItem v-if="operation === 'send'" :message="{ role: 'user', content: sendingContent.trim() }" />
              <ChatMessageItem v-if="operation === 'send' && streamingText" :message="{ role: 'assistant', content: streamingText }" />
              <template v-for="proposal in displayedProposals" :key="proposal.id">
                <ChatProposalCard :proposal="proposal" :busy="navigationBusy || stopping" @decide="decide" />
                <p v-if="decisionError?.proposalId === proposal.id" class="ui-execution-status ui-execution-notice" data-execution-state="incomplete" role="status">
                  {{ decisionError.message }}
                </p>
                <ChatTaskCard v-if="proposal.task_id" :task-id="proposal.task_id" @activity="refreshActivityOnFocus" />
              </template>
              <p v-if="!detail.messages.length && !displayedProposals.length && operation !== 'send'" class="ai-placeholder">开始对话</p>
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
              :disabled="sendDisabled || !!editingMessage"
              name="chat_message"
              autocomplete="off"
              aria-label="运维消息"
              placeholder="输入运维问题，Enter 发送"
              @input="
                inputError = '';
                inputInvalid = false
              "
              @keydown="handleInputKeydown"
            />
            <FieldError v-if="inputError" :id="`${inputId}-error`" :message="inputError" />
            <p v-if="branchError && !editingMessage" class="ui-load-retry ai-message-action-error" role="alert">
              {{ branchError }}<ElButton :disabled="navigationBusy || sessionsLoading" @click="loadSessions()">刷新会话列表</ElButton>
            </p>
            <p v-if="regenerationError && !editingMessage" class="ui-load-retry ai-message-action-error" role="alert">
              {{ regenerationError }}<ElButton :disabled="interactionBusy || activityLoading || detailLoading" @click="loadActivity(true)">刷新对话</ElButton>
            </p>
            <p v-if="selectedId && activityFailed" class="ui-load-retry">
              运行状态未确认。<ElButton :loading="activityLoading" :disabled="stopPending" @click="loadActivity(true)">刷新状态</ElButton>
            </p>
            <div class="ai-composer-actions">
              <span class="ui-text-muted ui-execution-status" role="status"
                :data-execution-state="operation === 'create' || operation === 'branch' || operation === 'send' || operation === 'decision' ? 'in-progress' : undefined">
                <template v-if="stopping">正在中止...</template>
                <template v-else-if="operation === 'create'">正在创建会话...</template>
                <template v-else-if="operation === 'branch'">正在创建分支…</template>
                <template v-else-if="operation === 'send' && regeneratingMessageId">正在重新生成回复…</template>
                <template v-else-if="operation === 'send'">正在接收回复...</template>
                <template v-else-if="operation === 'decision'">正在提交巡检计划...</template>
                <template v-else-if="activity?.running">后台任务尚未结束...</template>
              </span>
              <ElButton
                :type="running ? 'danger' : 'primary'"
                :circle="running"
                :loading="operation === 'create' || operation === 'branch'"
                :class="{ 'ai-composer-stop': running }"
                :aria-label="running ? (stopping ? '正在中止' : '中止当前会话的回复和后台任务') : '发送'"
                :title="running ? (stopping ? '正在中止' : '中止当前会话的回复和后台任务') : '发送'"
                :aria-disabled="running && stopping"
                :disabled="!running && (sendDisabled || !!editingMessage || !input.trim())"
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
