<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, useId, watch } from 'vue'
import {
  ElAlert, ElButton, ElDialog, ElEmpty, ElInput, ElInputNumber, ElLoading, ElMessage, ElMessageBox,
  ElOption, ElRadioButton, ElRadioGroup, ElSelect, ElTable, ElTableColumn,
} from 'element-plus'
import { createHost, deleteHost, getHost, listGroups, listHostsPage, updateHost } from '@/api/assets'
import { listJumpHosts } from '@/api/jump_hosts'
import { listSSHKeys } from '@/api/ssh_keys'
import SSHConnectionDialog from '@/components/SSHConnectionDialog.vue'
import HostSSHStatus from '@/components/HostSSHStatus.vue'
import BatchSSHConnectionDialog from '@/components/BatchSSHConnectionDialog.vue'
import ListPagination from '@/components/ListPagination.vue'
import FieldError from '@/components/FieldError.vue'
import { focusFormFeedback, vNativeFieldAria } from '@/components/formFeedback'
import { useServerPagination } from '@/components/serverPagination'
import { showSystemError } from '@/components/feedback'
import type { AuthType, ConnectionTestTarget, Host, HostGroup, HostInput, JumpHost, SSHKey } from '@/types/api'
import '@/styles/assets.css'

interface HostForm {
  name: string
  address: string
  group_id: number | ''
  username: string
  port: number
  auth_type: AuthType
  ssh_key_id: number | null
  password: string
  vip: string
  jump_host_id: number | null
  remark: string
}

const groups = ref<HostGroup[]>([])
const jumpHosts = ref<JumpHost[]>([])
const sshKeys = ref<SSHKey[]>([])
const vLoading = ElLoading.directive
const { items: hosts, page, pageSize, total, loading: hostsLoading, loadFailed: hostsLoadFailed,
  refresh: loadHosts, resetPage, invalidate } = useServerPagination<Host>(
  (currentPage, size) => listHostsPage(search.value.trim(), selectedGroup.value, currentPage, size),
)
const hostTable = ref<{ clearSelection: () => void; toggleAllSelection: () => void } | null>(null)
const selectedGroup = ref<number | null>(null)
const search = ref('')
const groupsLoading = ref(false)
const jumpHostsLoading = ref(false)
const jumpHostsLoaded = ref(false)
const sshKeysLoading = ref(false)
const sshKeysLoaded = ref(false)
const groupsLoadFailed = ref(false)
const dialogError = ref('')
const formRoot = ref<HTMLElement | null>(null)
const formId = useId()
const saving = ref(false)
const openingHost = ref(false)
const hostDialog = ref(false)
const testDialog = ref(false)
const testTarget = ref<ConnectionTestTarget | null>(null)
const selectedHosts = ref<Host[]>([])
const allHostsSelected = computed(() => hosts.value.length > 0 && selectedHosts.value.length === hosts.value.length)
const MIN_BATCH_HOSTS = 2
function toggleAllHosts() {
  if (hostsLoading.value || hostsLoadFailed.value || !hosts.value.length) return
  hostTable.value?.toggleAllSelection()
}
function clearSelectedHosts() {
  selectedHosts.value = []
  hostTable.value?.clearSelection()
}
watch([page, pageSize], clearSelectedHosts, { flush: 'sync' })
const batchHosts = ref<Host[]>([])
const batchDialog = ref(false)
function startBatchTest() {
  if (hostsLoading.value || hostsLoadFailed.value || selectedHosts.value.length < MIN_BATCH_HOSTS || batchDialog.value) return
  batchHosts.value = [...selectedHosts.value]
  batchDialog.value = true
}
const editingHost = ref<Host | null>(null)
const hostInvalidFields = ref<Set<keyof HostForm>>(new Set())
const missingRequiredFields = ref(false)
const hostAuthChanged = ref(false)

function emptyHost(groupId: number | null): HostForm {
  return {
    name: '', address: '', group_id: groupId ?? '', username: '', port: 22,
    auth_type: 'password', ssh_key_id: null, password: '', vip: '', jump_host_id: null, remark: '',
  }
}

const hostForm = ref<HostForm>(emptyHost(null))
watch(() => ({ ...hostForm.value }), (next, previous) => {
  for (const key of Object.keys(next) as (keyof HostForm)[]) {
    if (next[key] !== previous[key]) hostInvalidFields.value.delete(key)
  }
  if (!hostInvalidFields.value.size) dialogError.value = ''
}, { flush: 'sync' })
function fieldMessage(field: keyof HostForm): string {
  if (!hostInvalidFields.value.has(field) || !dialogError.value) return ''
  if (missingRequiredFields.value) {
    return field === 'name' ? '请填写主机名称。' : field === 'address' ? '请填写地址。' : '请填写用户名。'
  }
  return dialogError.value
}
function showHostValidation(message: string) {
  dialogError.value = message
  focusFormFeedback(formRoot.value)
}
watch(() => hostForm.value.auth_type, (next, previous) => {
  if (hostDialog.value && next !== previous) {
    hostInvalidFields.value.delete('password')
    hostInvalidFields.value.delete('ssh_key_id')
    if (!hostInvalidFields.value.size) dialogError.value = ''
    hostAuthChanged.value = true
    hostForm.value.password = ''
    hostForm.value.ssh_key_id = null
  }
}, { flush: 'sync' })
async function refreshGroups() {
  groupsLoading.value = true
  groupsLoadFailed.value = false
  try {
    groups.value = await listGroups()
  } catch {
    groupsLoadFailed.value = true
    showSystemError()
  } finally {
    groupsLoading.value = false
  }
}

let jumpHostRequest = 0
let sshKeyRequest = 0
async function refreshSSHKeys() {
  const current = ++sshKeyRequest
  sshKeysLoading.value = true
  sshKeysLoaded.value = false
  sshKeys.value = []
  try {
    const result = await listSSHKeys()
    if (current === sshKeyRequest) {
      sshKeys.value = result
      sshKeysLoaded.value = true
    }
  } catch {
    if (current === sshKeyRequest) {
      showSystemError()
    }
  } finally {
    if (current === sshKeyRequest) sshKeysLoading.value = false
  }
}
async function refreshJumpHosts() {
  const current = ++jumpHostRequest
  jumpHostsLoading.value = true
  jumpHostsLoaded.value = false
  try {
    const result = await listJumpHosts()
    if (current === jumpHostRequest) {
      jumpHosts.value = result
      jumpHostsLoaded.value = true
    }
  } catch {
    if (current === jumpHostRequest) {
      jumpHosts.value = []
      showSystemError()
    }
  } finally {
    if (current === jumpHostRequest) jumpHostsLoading.value = false
  }
}

let searchTimer: ReturnType<typeof setTimeout> | undefined
function refreshHosts() {
  clearTimeout(searchTimer)
  clearSelectedHosts()
  return loadHosts()
}

watch([search, selectedGroup], () => {
  clearTimeout(searchTimer)
  clearSelectedHosts()
  invalidate()
  resetPage()
  searchTimer = setTimeout(refreshHosts, search.value ? 250 : 0)
}, { flush: 'sync' })
onMounted(() => {
  void refreshGroups()
  void refreshJumpHosts()
})
onUnmounted(() => {
  clearTimeout(searchTimer)
  jumpHostRequest++
  sshKeyRequest++
})

function openNewHost() {
  if (groupsLoading.value) { ElMessage.info('分组加载中，请稍后重试。'); return }
  if (groupsLoadFailed.value) { showSystemError(); return }
  if (!groups.value.length) { ElMessage.warning('请先新增分组，再新增主机。'); return }
  editingHost.value = null
  hostAuthChanged.value = false
  hostForm.value = emptyHost(selectedGroup.value)
  hostInvalidFields.value.clear()
  dialogError.value = ''
  hostDialog.value = true
  void refreshJumpHosts()
  void refreshSSHKeys()
}

async function openEditHost(id: number) {
  openingHost.value = true
  try {
    const host = await getHost(id)
    editingHost.value = host
    hostAuthChanged.value = false
    hostForm.value = {
      name: host.name, address: host.address, group_id: host.group_id,
      username: host.username, port: host.port, auth_type: host.auth_type,
      ssh_key_id: host.ssh_key_id, password: '', vip: host.vip ?? '',
      jump_host_id: host.jump_host_id, remark: host.remark,
    }
    hostInvalidFields.value.clear()
    dialogError.value = ''
    hostDialog.value = true
    void refreshJumpHosts()
    void refreshSSHKeys()
  } catch {
    showSystemError()
  } finally {
    openingHost.value = false
  }
}

function isIpAddress(value: string): boolean {
  if (!value.includes(':')) {
    const parts = value.split('.')
    return parts.length === 4 && parts.every((part) =>
      /^(0|[1-9]\d{0,2})$/.test(part) && Number(part) <= 255)
  }
  if (!/^[0-9a-f:.]+$/i.test(value)) return false
  // 浏览器 URL 解析器校验 IPv6 分组、压缩写法及内嵌 IPv4。
  try {
    return new URL(`http://[${value}]/`).hostname.startsWith('[')
  } catch {
    return false
  }
}

function validateHost(): string | false {
  const form = hostForm.value
  hostInvalidFields.value.clear()
  missingRequiredFields.value = false
  if (!form.name.trim() || !form.address.trim() || !form.username.trim()) {
    missingRequiredFields.value = true
    if (!form.name.trim()) hostInvalidFields.value.add('name')
    if (!form.address.trim()) hostInvalidFields.value.add('address')
    if (!form.username.trim()) hostInvalidFields.value.add('username')
    return '请填写主机名称、地址和用户名。'
  }
  if (!isIpAddress(form.address.trim())) {
    hostInvalidFields.value.add('address')
    return '主机地址须为有效 IPv4 或 IPv6 地址。'
  }
  if (!Number.isInteger(form.port) || form.port < 1 || form.port > 65535) {
    hostInvalidFields.value.add('port')
    return '主机端口须在 1 到 65535 之间。'
  }
  if (sshKeysLoading.value) return '密钥列表加载中。'
  if (!sshKeysLoaded.value) return false
  if (form.auth_type === 'key' && form.ssh_key_id === null) {
    hostInvalidFields.value.add('ssh_key_id')
    return editingHost.value?.auth_type === 'key' && editingHost.value.ssh_key_id === null
      ? '旧记录尚未关联密钥，请先导入并选择 SSH 密钥。' : '请选择 SSH 密钥。'
  }
  if (form.auth_type === 'key' && !sshKeys.value.some((item) => item.id === form.ssh_key_id)) {
    hostInvalidFields.value.add('ssh_key_id')
    return false
  }
  if (form.auth_type === 'password' && !form.password &&
    !(editingHost.value?.auth_type === 'password' && editingHost.value.has_password && !hostAuthChanged.value)) {
    hostInvalidFields.value.add('password')
    return '请输入主机密码；切换为密码认证时不能沿用原凭据。'
  }
  if (editingHost.value && form.auth_type === 'password' && !form.password &&
    (form.address.trim() !== editingHost.value.address || form.username.trim() !== editingHost.value.username || form.port !== editingHost.value.port)) {
    hostInvalidFields.value.add('password')
    return '连接信息已变更，请重新填写主机密码。'
  }
  if (jumpHostsLoading.value) {
    hostInvalidFields.value.add('jump_host_id')
    return '跳板机列表加载中。'
  }
  if (!jumpHostsLoaded.value) {
    hostInvalidFields.value.add('jump_host_id')
    return false
  }
  if (form.jump_host_id !== null && !jumpHosts.value.some((item) => item.id === form.jump_host_id)) {
    hostInvalidFields.value.add('jump_host_id')
    return false
  }
  return ''
}

async function saveHost() {
  const groupId = hostForm.value.group_id
  if (groupId === '' || !Number.isInteger(groupId) || groupId <= 0) {
    hostInvalidFields.value.clear()
    missingRequiredFields.value = false
    hostInvalidFields.value.add('group_id')
    showHostValidation('请选择所属分组。')
    return
  }
  const validation = validateHost()
  if (validation === false) { dialogError.value = ''; showSystemError(); return }
  if (validation) { showHostValidation(validation); return }
  const form = hostForm.value
  const previous = editingHost.value
  const body: HostInput = {
    name: form.name.trim(), address: form.address.trim(), group_id: groupId,
    username: form.username.trim(), port: form.port, auth_type: form.auth_type,
    ssh_key_id: form.auth_type === 'key' ? form.ssh_key_id : null,
    vip: form.vip.trim() || null,
    jump_host_id: form.jump_host_id,
    remark: form.remark.trim(),
  }
  if (form.auth_type === 'password' && form.password) body.password = form.password

  saving.value = true
  dialogError.value = ''
  try {
    if (previous) await updateHost(previous.id, { ...body, version: previous.version })
    else await createHost(body)
    hostDialog.value = false
    await Promise.all([refreshHosts(), refreshGroups()])
  } catch {
    showSystemError()
  } finally {
    saving.value = false
  }
}

async function removeHost(id: number, name: string) {
  try {
    await ElMessageBox.confirm(`确定删除主机“${name}”吗？此操作不可撤销。`, '删除主机', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'delete-confirm-button',
    })
  } catch { return }
  try {
    await deleteHost(id)
    await Promise.all([refreshHosts(), refreshGroups()])
  } catch {
    showSystemError()
  }
}

function groupName(id: number) {
  return groups.value.find((group) => group.id === id)?.name
}

function openConnectionTest(host: Host) {
  testTarget.value = { target_type: 'host', target_id: host.id, version: host.version, name: host.name }
  testDialog.value = true
}

function jumpHostName(id: number | null) {
  if (id === null) return '未关联'
  const jumpHost = jumpHosts.value.find((item) => item.id === id)
  return jumpHost ? `${jumpHost.name} · ${jumpHost.address}` : undefined
}

function dateLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
    <main class="assets-main">
      <ElAlert v-if="!groupsLoading && !groupsLoadFailed && !groups.length" title="暂无分组，请前往分组管理新增分组。" type="info" :closable="false" show-icon class="assets-alert" />
      <div class="assets-layout">
        <aside class="group-sidebar" aria-label="主机分组">
          <div class="section-header"><h2>分组筛选</h2><RouterLink to="/assets/groups">管理分组</RouterLink></div>
          <div v-loading="groupsLoading" class="group-list">
            <button type="button" class="group-item" :class="{ active: selectedGroup === null }" @click="selectedGroup = null"><span>全部主机</span></button>
            <div v-for="group in groups" :key="group.id" class="group-row" :class="{ active: selectedGroup === group.id }">
              <button type="button" class="group-choice" :title="group.remark ? `${group.name}：${group.remark}` : group.name" :aria-pressed="selectedGroup === group.id" @click="selectedGroup = group.id"><span class="group-name">{{ group.name }}</span><span class="group-count">{{ group.host_count }}</span></button>
            </div>
          </div>
        </aside>
        <section class="host-section" aria-labelledby="host-title">
          <div class="section-header"><div class="host-title-row"><h2 id="host-title">资产列表</h2><span v-if="!hostsLoading && !hostsLoadFailed" class="host-total">{{ total }} 台</span></div></div>
          <div class="host-toolbar">
            <div class="host-toolbar-left">
              <ElButton :disabled="hostsLoading || hostsLoadFailed || !hosts.length" :aria-label="allHostsSelected ? '取消全选当前页主机' : '全选当前页主机'" @click="toggleAllHosts">{{ allHostsSelected ? '取消全选' : '全选' }}</ElButton>
            </div>
            <div class="host-toolbar-right">
              <ElInput v-model="search" clearable placeholder="搜索名称或地址" aria-label="搜索主机名称或地址" class="host-search" />
              <ElButton type="primary" @click="openNewHost">新增主机</ElButton>
              <ElButton v-if="selectedHosts.length >= MIN_BATCH_HOSTS" :disabled="hostsLoading || hostsLoadFailed || batchDialog" @click="startBatchTest">批量测试连接（{{ selectedHosts.length }}）</ElButton>
              <ElButton :loading="hostsLoading || groupsLoading || jumpHostsLoading" @click="refreshGroups(); refreshJumpHosts(); refreshHosts()">刷新</ElButton>
            </div>
          </div>
          <div class="host-table-wrap">
            <ElTable ref="hostTable" v-loading="hostsLoading || openingHost" :data="hosts" row-key="id" class="host-table" :empty-text="hostsLoadFailed ? '' : hostsLoading ? '加载中' : '暂无主机'" @selection-change="selectedHosts = $event">
              <ElTableColumn type="selection" width="44" />
              <ElTableColumn label="主机" min-width="190"><template #default="{ row }"><div class="host-name">{{ row.name }}</div><div class="host-address">{{ row.address }}</div></template></ElTableColumn>
              <ElTableColumn label="分组" min-width="110"><template #default="{ row }">{{ groupName(row.group_id) }}</template></ElTableColumn>
              <ElTableColumn label="登录" min-width="150"><template #default="{ row }"><div>{{ row.username }} · {{ row.port }}</div><div class="host-secondary">{{ row.auth_type === 'key' ? '密钥认证' : '密码认证' }}</div></template></ElTableColumn>
              <ElTableColumn label="跳板机" min-width="190"><template #default="{ row }">{{ row.jump_host_id !== null && !jumpHostsLoaded ? jumpHostsLoading ? '加载中' : '' : jumpHostName(row.jump_host_id) }}</template></ElTableColumn>
              <ElTableColumn label="更新时间" min-width="160"><template #default="{ row }">{{ dateLabel(row.updated_at) }}</template></ElTableColumn>
              <ElTableColumn label="连接状态" width="100" align="center"><template #default="{ row }"><HostSSHStatus :host="row as Host" /></template></ElTableColumn>
              <ElTableColumn label="操作" width="344" fixed="right">
                <template #default="{ row }">
                  <ElButton link type="primary" @click="openConnectionTest(row as Host)">连接测试</ElButton>
                  <ElButton link type="primary" @click="openEditHost(row.id)">编辑</ElButton>
                  <ElButton link disabled>更多操作</ElButton>
                  <ElButton link type="danger" @click="removeHost(row.id, row.name)">删除</ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
          </div>
          <ElEmpty v-if="!hostsLoading && !hostsLoadFailed && !hosts.length" :description="search || selectedGroup !== null ? '暂无符合条件的主机' : '暂无主机，请新增主机'" class="host-empty"><ElButton v-if="!search && selectedGroup === null" type="primary" plain @click="openNewHost">新增主机</ElButton></ElEmpty>
          <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :total-known="!hostsLoading && !hostsLoadFailed" :disabled="hostsLoading || hostsLoadFailed" />
        </section>
      </div>
    </main>

    <BatchSSHConnectionDialog v-model="batchDialog" :hosts="batchHosts" @status-changed="loadHosts" />
    <SSHConnectionDialog v-model="testDialog" :target="testTarget" @status-changed="loadHosts" />
     <ElDialog v-model="hostDialog" align-center :title="editingHost ? '编辑主机' : '新增主机'" width="min(var(--ui-dialog-width), calc(100vw - 32px))" class="host-dialog" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
       <div ref="formRoot" class="asset-form host-form">
         <ElAlert v-if="dialogError" :title="dialogError" type="error" :closable="false" show-icon data-form-error tabindex="-1" />
         <div class="form-section-title">基本信息</div>
         <div class="field-grid">
           <div class="field" :class="{ 'is-error': hostInvalidFields.has('name') }"><label :for="`${formId}-name`">主机名称 <em>*</em></label><ElInput :id="`${formId}-name`" v-model="hostForm.name" placeholder="例：生产主机 01" :aria-invalid="hostInvalidFields.has('name') ? 'true' : undefined" :aria-describedby="fieldMessage('name') ? `${formId}-name-error` : undefined" /><FieldError :id="`${formId}-name-error`" :message="fieldMessage('name')" /></div>
           <div class="field" :class="{ 'is-error': hostInvalidFields.has('address') }"><label :for="`${formId}-address`">地址 <em>*</em></label><ElInput :id="`${formId}-address`" v-model="hostForm.address" placeholder="IPv4 或 IPv6 地址" :aria-invalid="hostInvalidFields.has('address') ? 'true' : undefined" :aria-describedby="fieldMessage('address') ? `${formId}-address-error` : undefined" /><FieldError :id="`${formId}-address-error`" :message="fieldMessage('address')" /></div>
            <div class="field" :class="{ 'is-error': hostInvalidFields.has('group_id') }"><label :for="`${formId}-group`">所属分组 <em>*</em></label><ElSelect :id="`${formId}-group`" v-model="hostForm.group_id" v-native-field-aria placeholder="请选择分组" class="full-width" :aria-invalid="hostInvalidFields.has('group_id') ? 'true' : undefined" :aria-describedby="fieldMessage('group_id') ? `${formId}-group-error` : undefined"><ElOption v-for="group in groups" :key="group.id" :label="group.name" :value="group.id" /></ElSelect><FieldError :id="`${formId}-group-error`" :message="fieldMessage('group_id')" /></div>
           <label class="field"><span>虚拟 IP（VIP）</span><ElInput v-model="hostForm.vip" placeholder="可选" /></label>
         </div>
         <div class="form-section-title">登录信息</div>
         <div class="field-grid">
           <div class="field" :class="{ 'is-error': hostInvalidFields.has('username') }"><label :for="`${formId}-username`">用户名 <em>*</em></label><ElInput :id="`${formId}-username`" v-model="hostForm.username" autocomplete="off" :aria-invalid="hostInvalidFields.has('username') ? 'true' : undefined" :aria-describedby="fieldMessage('username') ? `${formId}-username-error` : undefined" /><FieldError :id="`${formId}-username-error`" :message="fieldMessage('username')" /></div>
            <div class="field" :class="{ 'is-error': hostInvalidFields.has('port') }"><label :for="`${formId}-port`">端口 <em>*</em></label><ElInputNumber :id="`${formId}-port`" v-model="hostForm.port" v-native-field-aria :min="1" :max="65535" :controls="false" class="full-width" :aria-invalid="hostInvalidFields.has('port') ? 'true' : undefined" :aria-describedby="fieldMessage('port') ? `${formId}-port-error` : undefined" /><FieldError :id="`${formId}-port-error`" :message="fieldMessage('port')" /></div>
         </div>
        <div class="field"><span>认证方式</span><ElRadioGroup v-model="hostForm.auth_type" aria-label="主机认证方式"><ElRadioButton value="password">密码</ElRadioButton><ElRadioButton value="key">SSH 密钥</ElRadioButton></ElRadioGroup></div>
         <div v-if="hostForm.auth_type === 'password'" class="field" :class="{ 'is-error': hostInvalidFields.has('password') }"><label :for="`${formId}-password`">密码 <em v-if="!editingHost || editingHost.auth_type !== 'password' || !editingHost.has_password || hostAuthChanged">*</em></label><ElInput :id="`${formId}-password`" v-model="hostForm.password" type="password" show-password autocomplete="new-password" :placeholder="editingHost?.auth_type === 'password' && editingHost.has_password && !hostAuthChanged ? '留空保留原密码' : '请输入密码'" :aria-invalid="hostInvalidFields.has('password') ? 'true' : undefined" :aria-describedby="fieldMessage('password') ? `${formId}-password-error` : undefined" /><FieldError :id="`${formId}-password-error`" :message="fieldMessage('password')" /></div>
          <template v-else><div class="field" :class="{ 'is-error': hostInvalidFields.has('ssh_key_id') }"><label :for="`${formId}-key`">SSH 密钥 <em>*</em></label><ElSelect :id="`${formId}-key`" v-model="hostForm.ssh_key_id" v-native-field-aria :disabled="sshKeysLoading || !sshKeysLoaded" :placeholder="sshKeysLoading ? '加载中' : '请选择密钥'" class="full-width" :aria-invalid="hostInvalidFields.has('ssh_key_id') ? 'true' : undefined" :aria-describedby="fieldMessage('ssh_key_id') ? `${formId}-key-error` : undefined"><ElOption v-for="key in sshKeys" :key="key.id" :label="`${key.name} · ${key.key_type} · ${key.fingerprint}`" :value="key.id" /></ElSelect><FieldError :id="`${formId}-key-error`" :message="fieldMessage('ssh_key_id')" /></div><ElAlert v-if="editingHost?.auth_type === 'key' && editingHost.ssh_key_id === null && hostForm.ssh_key_id === null" title="旧记录尚未关联密钥，请先导入并选择 SSH 密钥。" type="warning" :closable="false" show-icon /><RouterLink to="/assets/ssh-keys">管理 SSH 密钥</RouterLink></template>
         <div class="form-section-title">跳板机</div>
          <div class="field" :class="{ 'is-error': hostInvalidFields.has('jump_host_id') }"><label :for="`${formId}-jump`">关联跳板机</label><ElSelect :id="`${formId}-jump`" v-model="hostForm.jump_host_id" v-native-field-aria clearable :value-on-clear="null" :disabled="jumpHostsLoading || !jumpHostsLoaded" placeholder="不使用跳板机" class="full-width" :aria-invalid="hostInvalidFields.has('jump_host_id') ? 'true' : undefined" :aria-describedby="fieldMessage('jump_host_id') ? `${formId}-jump-error` : undefined"><ElOption v-for="jumpHost in jumpHosts" :key="jumpHost.id" :label="`${jumpHost.name} · ${jumpHost.address}`" :value="jumpHost.id" /></ElSelect><FieldError :id="`${formId}-jump-error`" :message="fieldMessage('jump_host_id')" /></div>
         <label class="field"><span>备注</span><ElInput v-model="hostForm.remark" type="textarea" :rows="3" placeholder="可选" /></label>
      </div>
      <template #footer><ElButton :disabled="saving" @click="hostDialog = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="saveHost">保存</ElButton></template>
    </ElDialog>
</template>
