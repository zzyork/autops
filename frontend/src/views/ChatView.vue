<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElButton, ElInput, ElMessageBox, ElOption, ElSelect, ElTag } from 'element-plus'
import AssetsLayout from '@/components/AssetsLayout.vue'
import ChatProposalCard from '@/components/ChatProposalCard.vue'
import ChatTaskCard from '@/components/ChatTaskCard.vue'
import { createSession, decideProposal, deleteSession, getSession, listConnections, listSessions, sendMessage } from '@/api/ai'
import { showRequestError } from '@/components/feedback'
import { timeLabel } from '@/components/inspectionDisplay'
import type { ChatSession, ModelConnection, SessionSummary } from '@/types/ai'
import '@/styles/ai.css'

const connections = ref<ModelConnection[]>([])
const connectionsLoaded = ref(false)
const connectionsLoading = ref(false)
const sessions = ref<SessionSummary[]>([])
const sessionsLoaded = ref(false)
const sessionsLoading = ref(false)
const selectedId = ref<string | null>(null)
const detail = ref<ChatSession | null>(null)
const detailLoaded = ref(false)
const detailLoading = ref(false)
const connectionId = ref<number | null>(null)
const input = ref('')
const inputError = ref('')
const streamingText = ref('')
const sendingContent = ref('')
const operation = ref<'create' | 'send' | 'decision' | 'delete' | null>(null)
const conversation = ref<HTMLElement | null>(null)
const selectedConnection = computed(() => connections.value.find((item) => item.id === (detail.value?.connection_id ?? connectionId.value)))
let active = true
let listSequence = 0
let connectionSequence = 0
let detailSequence = 0
let streamController: AbortController | null = null
let selectInitialSession = true
const MAX_MESSAGE_LENGTH = 8000

async function loadConnections() {
  const current = ++connectionSequence
  connectionsLoading.value = true
  try {
    const items = await listConnections()
    if (!active || current !== connectionSequence) return
    connections.value = items
    connectionsLoaded.value = true
    if (!connectionId.value || !items.some((item) => item.id === connectionId.value)) connectionId.value = items.find((item) => item.is_default)?.id ?? items[0]?.id ?? null
  } catch {
    if (!active || current !== connectionSequence) return
    connectionsLoaded.value = false
    showRequestError()
  } finally { if (active && current === connectionSequence) connectionsLoading.value = false }
}
async function loadSessions(notify = true) {
  const current = ++listSequence
  sessionsLoading.value = true
  try {
    const items = await listSessions()
    if (!active || current !== listSequence) return
    sessions.value = items
    sessionsLoaded.value = true
    if (selectInitialSession && !selectedId.value && items.length) select(items[0]!.id)
    selectInitialSession = false
  } catch {
    if (!active || current !== listSequence) return
    sessionsLoaded.value = false
    if (notify) showRequestError()
  } finally { if (active && current === listSequence) sessionsLoading.value = false }
}
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
  detailSequence++
  selectedId.value = null
  detail.value = null
  detailLoaded.value = false
  detailLoading.value = false
  input.value = ''
  inputError.value = ''
}
async function create() {
  if (operation.value || !connectionsLoaded.value || connectionId.value === null) return
  operation.value = 'create'
  try {
    const summary = await createSession(connectionId.value)
    if (!active) return
    selectedId.value = summary.id
    detail.value = null
    void loadSessions()
    await loadDetail(summary.id)
  } catch { if (active) showRequestError() }
  finally { if (active) operation.value = null }
}
async function send() {
  const id = selectedId.value
  const content = input.value.trim()
  if (operation.value || !id || !detailLoaded.value) return
  if (!content || content.length > MAX_MESSAGE_LENGTH) {
    inputError.value = `消息须填写且不超过 ${MAX_MESSAGE_LENGTH} 字符。`
    return
  }
  inputError.value = ''
  operation.value = 'send'
  sendingContent.value = content
  streamingText.value = ''
  const controller = new AbortController()
  streamController = controller
  try {
    const session = await sendMessage(id, content, controller.signal, (text) => { if (active && selectedId.value === id && !controller.signal.aborted) streamingText.value += text })
    if (!active || selectedId.value !== id || controller.signal.aborted) return
    detail.value = session
    input.value = ''
    void loadSessions()
  } catch {
    if (active && selectedId.value === id && !controller.signal.aborted) {
      showRequestError()
      if (await loadDetail(id, false)) void loadSessions(false)
    }
  } finally {
    if (active) { sendingContent.value = ''; streamingText.value = ''; operation.value = null }
    if (streamController === controller) streamController = null
  }
}
async function decide(proposalId: string, approve: boolean) {
  const id = selectedId.value
  if (!id || operation.value || !detailLoaded.value) return
  operation.value = 'decision'
  try {
    const session = await decideProposal(id, proposalId, approve)
    if (!active || selectedId.value !== id) return
    detail.value = session
    void loadSessions()
  } catch {
    if (active && selectedId.value === id) {
      showRequestError()
      if (await loadDetail(id, false)) void loadSessions(false)
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
    sessions.value = sessions.value.filter((item) => item.id !== session.id)
    if (selectedId.value === session.id) {
      detailSequence++
      selectedId.value = null
      detail.value = null
      detailLoaded.value = false
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
onMounted(() => { void loadConnections(); void loadSessions() })
onUnmounted(() => {
  active = false
  listSequence++
  connectionSequence++
  detailSequence++
  streamController?.abort()
})
</script>

<template>
  <AssetsLayout title="AI 对话" section="AI 对话">
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
              <p v-if="connectionsLoading && !connectionsLoaded" class="ai-placeholder">正在读取模型连接...</p>
              <p v-else-if="!connectionsLoaded" class="inspection-retry">模型连接未加载。<ElButton @click="loadConnections">重试</ElButton></p>
              <p v-else-if="!connections.length" class="ai-placeholder">尚未配置模型连接。<RouterLink to="/ai/connections">前往模型配置</RouterLink></p>
              <div v-else class="ai-new-session"><label for="chat-model">选择模型连接</label><ElSelect id="chat-model" v-model="connectionId" aria-label="选择模型连接"><ElOption v-for="connection in connections" :key="connection.id" :label="`${connection.name}${connection.is_default ? '（默认）' : ''}`" :value="connection.id" /></ElSelect><ElButton type="primary" :loading="operation === 'create'" :disabled="!!operation || connectionId === null" @click="create">创建会话</ElButton></div>
            </template>
          </div>
          <div class="ai-composer"><label for="chat-input">消息</label><ElInput id="chat-input" v-model="input" type="textarea" :rows="3" :maxlength="MAX_MESSAGE_LENGTH" show-word-limit :aria-invalid="!!inputError" :disabled="!detailLoaded || !!operation" placeholder="输入运维问题" @input="inputError = ''" @keydown.ctrl.enter.prevent="send" /><p v-if="inputError" class="ssh-field-error" role="alert">{{ inputError }}</p><div class="ai-composer-actions"><span class="inspection-muted">{{ operation === 'send' ? '正在接收回复...' : '' }}</span><ElButton type="primary" :loading="operation === 'send'" :disabled="!detailLoaded || !!operation || !input.trim()" @click="send">发送</ElButton></div></div>
        </section>
      </div>
    </main>
  </AssetsLayout>
</template>
