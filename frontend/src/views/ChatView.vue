<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElInput, ElMessageBox, ElTag } from 'element-plus'
import ChatProposalCard from '@/components/ChatProposalCard.vue'
import ChatTaskCard from '@/components/ChatTaskCard.vue'
import ListPagination from '@/components/ListPagination.vue'
import { useServerPagination } from '@/components/serverPagination'
import { createSession, decideProposal, deleteSession, getFeatureModels, getSession, listConnections, listSessionsPage, sendMessage } from '@/api/ai'
import { showRequestError } from '@/components/feedback'
import { timeLabel } from '@/components/inspectionDisplay'
import type { ChatSession, FeatureModelsConfig, ModelConnection, SessionSummary } from '@/types/ai'
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
const streamingText = ref('')
const sendingContent = ref('')
const operation = ref<'create' | 'send' | 'decision' | 'delete' | null>(null)
const conversation = ref<HTMLElement | null>(null)
const newChatConnection = computed(() => {
  if (!connectionsLoaded.value || !featureModels.value) return undefined
  return featureModels.value.chat_connection_id === null
    ? connections.value.find((item) => item.is_default)
    : connections.value.find((item) => item.id === featureModels.value?.chat_connection_id)
})
const newChatAvailable = computed(() => !!newChatConnection.value)
const selectedConnection = computed(() => connections.value.find((item) => item.id === detail.value?.connection_id))
let active = true
let connectionSequence = 0
let detailSequence = 0
let streamController: AbortController | null = null
let selectInitialSession = true
const MAX_MESSAGE_LENGTH = 8000

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
  if (operation.value || selectedId.value === id) return
  selectedId.value = id
  detail.value = null
  input.value = ''
  inputError.value = ''
  void loadDetail(id)
}
function newChat() {
  if (operation.value) return
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
  void loadConnections()
}
async function send() {
  const content = input.value.trim()
  if (operation.value || (selectedId.value ? !detailLoaded.value : !connectionsLoaded.value || connectionsLoading.value || !newChatAvailable.value)) return
  if (!content || content.length > MAX_MESSAGE_LENGTH) {
    inputError.value = `消息须填写且不超过 ${MAX_MESSAGE_LENGTH} 字符。`
    return
  }
  inputError.value = ''
  operation.value = selectedId.value ? 'send' : 'create'
  sendingContent.value = content
  streamingText.value = ''
  let id = selectedId.value
  let controller: AbortController | null = null
  try {
    if (!id) {
      if (!await loadConnections() || !active) return
      if (!newChatAvailable.value) {
        inputError.value = featureModels.value?.chat_connection_id === null ? '尚未指定主模型。' : '指定的对话模型连接不存在，请重新配置。'
        return
      }
      const summary = await createSession()
      if (!active) return
      id = summary.id
      selectedId.value = id
      detail.value = { ...summary, messages: [], proposals: [] }
      detailLoaded.value = true
      selectInitialSession = false
      resetPage()
      void loadSessions()
    }
    operation.value = 'send'
    const stream = new AbortController()
    controller = stream
    streamController = stream
    const session = await sendMessage(id, content, stream.signal, (text) => { if (active && selectedId.value === id && !stream.signal.aborted) streamingText.value += text })
    if (!active || selectedId.value !== id || stream.signal.aborted) return
    detail.value = session
    input.value = ''
    void loadSessions()
  } catch {
    if (active && selectedId.value === id && !controller?.signal.aborted) {
      showRequestError()
      if (id && await loadDetail(id, false)) void loadSessions()
    }
  } finally {
    if (active) { sendingContent.value = ''; streamingText.value = ''; operation.value = null }
    if (controller && streamController === controller) streamController = null
  }
}
async function decide(proposalId: string, approve: boolean) {
  const id = selectedId.value
  if (!id || operation.value || !detailLoaded.value) return
  operation.value = 'decision'
  try {
    const session = await decideProposal(id, proposalId, approve, { isCurrent: () => active && selectedId.value === id })
    if (!active || selectedId.value !== id) return
    detail.value = session
    void loadSessions()
  } catch (error) {
    if (active && selectedId.value === id) {
      showRequestError(error)
      if (await loadDetail(id, false)) void loadSessions()
    }
  }
  finally { if (active) operation.value = null }
}
async function remove(session: SessionSummary) {
  if (operation.value) return
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
onMounted(() => { void loadConnections() })
onUnmounted(() => {
  active = false
  connectionSequence++
  detailSequence++
  streamController?.abort()
})
</script>

<template>
    <main class="assets-main ai-main">
      <div class="assets-heading"><h1>AI 对话</h1></div>
      <div class="ai-workspace">
        <aside class="ai-sessions" aria-label="会话列表">
          <div class="ai-pane-heading"><strong>会话</strong><ElButton type="primary" :disabled="!!operation" @click="newChat">新建对话</ElButton></div>
          <div class="ai-session-scroll">
            <p v-if="sessionsLoading && !sessionsLoaded" class="ai-placeholder">正在读取会话...</p>
            <p v-else-if="!sessionsLoaded" class="inspection-retry">会话未加载。<ElButton @click="loadSessions()">重试</ElButton></p>
            <p v-else-if="!sessions.length" class="ai-placeholder">暂无会话</p>
            <div v-for="session in sessionsLoaded ? sessions : []" :key="session.id" class="ai-session-row" :class="{ active: selectedId === session.id }">
              <button type="button" class="ai-session-select" :disabled="!!operation" :title="session.title" @click="select(session.id)"><strong>{{ session.title }}</strong><small>{{ timeLabel(session.updated_at) }}</small></button>
              <ElButton link type="danger" :disabled="!!operation" :aria-label="`删除会话 ${session.title}`" title="删除会话" @click="remove(session)">删除</ElButton>
            </div>
          </div>
          <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :total-known="sessionsLoaded && !sessionsLoading" :disabled="sessionsLoading || !sessionsLoaded || !!operation" compact />
        </aside>
        <section class="ai-chat" aria-label="对话内容">
          <div class="ai-pane-heading"><strong>{{ detail?.title ?? (selectedId ? '对话' : '新对话') }}</strong><span v-if="detailLoaded && selectedConnection" class="inspection-muted">{{ selectedConnection.name }}</span></div>
          <div ref="conversation" class="ai-conversation" role="log" aria-live="polite">
            <p v-if="selectedId && detailLoading" class="ai-placeholder">正在读取历史...</p>
            <p v-else-if="selectedId && !detailLoaded" class="inspection-retry">历史未加载。<ElButton @click="loadDetail(selectedId!)">重试</ElButton></p>
            <template v-else-if="detailLoaded && detail">
              <div v-for="message in detail.messages" :key="message.id" class="ai-message" :class="`ai-message-${message.role}`"><span class="ai-message-role">{{ message.role === 'user' ? '你' : '助手' }} <ElTag v-if="message.status !== 'completed'" :type="message.status === 'failed' ? 'danger' : 'warning'" size="small">{{ message.status === 'failed' ? '发送失败' : '已中断' }}</ElTag></span><p>{{ message.content }}</p></div>
              <div v-if="operation === 'send'" class="ai-message ai-message-user"><span class="ai-message-role">你</span><p>{{ sendingContent }}</p></div>
              <div v-if="operation === 'send' && streamingText" class="ai-message ai-message-assistant"><span class="ai-message-role">助手</span><p>{{ streamingText }}</p></div>
              <template v-for="proposal in detail.proposals" :key="proposal.id"><ChatProposalCard :proposal="proposal" :busy="!!operation" @decide="decide" /><ChatTaskCard v-if="proposal.task_id" :task-id="proposal.task_id" /></template>
              <p v-if="!detail.messages.length && !detail.proposals.length && operation !== 'send'" class="ai-placeholder">开始对话</p>
            </template>
            <template v-else-if="!selectedId">
              <p v-if="connectionsLoading && !connectionsLoaded" class="ai-placeholder">正在读取功能模型配置与连接...</p>
              <p v-else-if="!connectionsLoaded" class="inspection-retry">功能模型配置或连接未加载。<ElButton @click="loadConnections">重试</ElButton></p>
              <p v-else-if="!newChatAvailable" class="ai-placeholder">{{ featureModels?.chat_connection_id === null ? '尚未指定主模型。' : '指定的对话模型连接不存在，请重新配置。' }}<RouterLink to="/settings/models">前往模型配置</RouterLink></p>
              <p v-else class="ai-placeholder">开始对话</p>
            </template>
          </div>
           <div class="ai-composer"><label for="chat-input">消息</label><ElInput id="chat-input" v-model="input" type="textarea" :rows="3" :maxlength="MAX_MESSAGE_LENGTH" show-word-limit :aria-invalid="!!inputError" :disabled="!!operation || (selectedId ? !detailLoaded : !connectionsLoaded || connectionsLoading || !newChatAvailable)" placeholder="输入运维问题" @input="inputError = ''" @keydown.ctrl.enter.prevent="send" /><p v-if="inputError" class="ssh-field-error" role="alert">{{ inputError }}</p><div class="ai-composer-actions"><span class="inspection-muted">{{ operation === 'create' ? '正在创建会话...' : operation === 'send' ? '正在接收回复...' : '' }}</span><ElButton type="primary" :loading="operation === 'create' || operation === 'send'" :disabled="!!operation || (selectedId ? !detailLoaded : !connectionsLoaded || connectionsLoading || !newChatAvailable) || !input.trim()" @click="send">发送</ElButton></div></div>
        </section>
      </div>
    </main>
</template>
