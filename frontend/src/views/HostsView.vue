<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  ElAlert, ElButton, ElDialog, ElDropdown, ElDropdownItem, ElDropdownMenu, ElEmpty, ElInput,
  ElLoading, ElMessage, ElMessageBox,
  ElTable, ElTableColumn,
} from 'element-plus'
import { createHost, deleteHost, getHost, listGroups, listHostsPage, updateHost } from '@/api/assets'
import { listJumpHosts } from '@/api/jump_hosts'
import { listSSHKeys } from '@/api/ssh_keys'
import HostSSHStatus from '@/components/HostSSHStatus.vue'
import { useSSHConnectionTest } from '@/components/sshConnectionTest'
import BatchSSHConnectionDialog from '@/components/BatchSSHConnectionDialog.vue'
import ListPagination from '@/components/ListPagination.vue'
import HostForm, { type HostFormData } from '@/components/HostForm.vue'
import HostBasicInfoDialog from '@/components/HostBasicInfoDialog.vue'
import { focusFormFeedback } from '@/components/formFeedback'
import { hostDisplayName } from '@/components/hostDisplay'
import { useServerPagination } from '@/components/serverPagination'
import { showSystemError } from '@/components/feedback'
import type { Host, HostGroup, HostInput, JumpHost, SSHKey } from '@/types/api'
import '@/styles/assets.css'

const groups = ref<HostGroup[]>([])
const jumpHosts = ref<JumpHost[]>([])
const sshKeys = ref<SSHKey[]>([])
const vLoading = ElLoading.directive
const { items: hosts, page, pageSize, total, loading: hostsLoading, loadFailed: hostsLoadFailed,
  refresh: loadHosts, resetPage, invalidate } = useServerPagination<Host>(
  (currentPage, size) => listHostsPage(search.value.trim(), selectedGroup.value, currentPage, size),
)
const { testing, testConnection, isTestTarget, connectionTestDisplay, clearConnectionTest } = useSSHConnectionTest(loadHosts)
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
const saving = ref(false)
const openingHost = ref(false)
const hostDialog = ref(false)
const basicInfoHost = ref<Host | null>(null)
const basicInfoDialog = ref(false)
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
  if (hostsLoading.value || hostsLoadFailed.value || selectedHosts.value.length < MIN_BATCH_HOSTS || batchDialog.value || testing.value) return
  clearConnectionTest()
  batchHosts.value = [...selectedHosts.value]
  batchDialog.value = true
}
const editingHost = ref<Host | null>(null)
const hostInvalidFields = ref<Set<keyof HostFormData>>(new Set())
const missingRequiredFields = ref(false)
const hostAuthChanged = ref(false)

function emptyHost(groupId: number | null): HostFormData {
  return {
    name: '', address: '', lan_ip: '', group_id: groupId ?? '', username: '', port: 22,
    auth_type: 'password', ssh_key_id: null, password: '', vip: '', jump_host_id: null, remark: '',
  }
}

const hostForm = ref<HostFormData>(emptyHost(null))
watch(() => ({ ...hostForm.value }), (next, previous) => {
  for (const key of Object.keys(next) as (keyof HostFormData)[]) {
    if (next[key] !== previous[key]) hostInvalidFields.value.delete(key)
  }
  if (!hostInvalidFields.value.size) dialogError.value = ''
}, { flush: 'sync' })
const fieldErrors = computed(() => {
  const errors: Partial<Record<keyof HostFormData, string>> = {}
  for (const field of hostInvalidFields.value) {
    if (missingRequiredFields.value) {
      errors[field] = field === 'address' ? '请填写地址。' : '请填写用户名。'
    } else {
      errors[field] = dialogError.value
    }
  }
  return errors
})
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
  clearConnectionTest()
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
      name: host.name, address: host.address, lan_ip: host.lan_ip ?? '', group_id: host.group_id,
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
  if (!form.address.trim() || !form.username.trim()) {
    missingRequiredFields.value = true
    if (!form.address.trim()) hostInvalidFields.value.add('address')
    if (!form.username.trim()) hostInvalidFields.value.add('username')
    return '请填写地址和用户名。'
  }
  if (form.name.trim().length > 100) {
    hostInvalidFields.value.add('name')
    return '主机名不能超过 100 个字符。'
  }
  if (form.lan_ip.trim().length > 253) {
    hostInvalidFields.value.add('lan_ip')
    return '局域网 IP 不能超过 253 个字符。'
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
  if (saving.value) return
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
    lan_ip: form.lan_ip.trim() || null,
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

function startHostConnectionTest(host: Host) {
  void testConnection({ target_type: 'host', target_id: host.id, version: host.version, name: hostDisplayName(host) })
}

function openBasicInfo(host: Host) {
  basicInfoHost.value = host
  basicInfoDialog.value = true
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
    <main class="console-main">
      <ElAlert v-if="!groupsLoading && !groupsLoadFailed && !groups.length" title="暂无分组，请前往分组管理新增分组。" type="info" :closable="false" show-icon class="ui-page-alert" />
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
        <section class="ui-panel" aria-labelledby="host-title">
          <div class="section-header"><div class="host-title-row"><h2 id="host-title">资产列表</h2><span v-if="!hostsLoading && !hostsLoadFailed" class="host-total">{{ total }} 台</span></div></div>
          <div class="ui-toolbar">
            <div class="ui-toolbar-left">
              <ElButton :disabled="hostsLoading || hostsLoadFailed || !hosts.length" :aria-label="allHostsSelected ? '取消全选当前页主机' : '全选当前页主机'" @click="toggleAllHosts">{{ allHostsSelected ? '取消全选' : '全选' }}</ElButton>
            </div>
            <div class="ui-toolbar-right">
              <ElInput v-model="search" clearable placeholder="搜索名称或地址" aria-label="搜索主机名称或地址" class="ui-search" />
              <ElButton type="primary" @click="openNewHost">新增主机</ElButton>
              <ElButton v-if="selectedHosts.length >= MIN_BATCH_HOSTS" :disabled="hostsLoading || hostsLoadFailed || batchDialog || testing" @click="startBatchTest">批量测试连接（{{ selectedHosts.length }}）</ElButton>
              <ElButton :loading="hostsLoading || groupsLoading || jumpHostsLoading" @click="refreshGroups(); refreshJumpHosts(); refreshHosts()">刷新</ElButton>
            </div>
          </div>
          <div class="ui-table-wrap">
            <ElTable ref="hostTable" v-loading="hostsLoading || openingHost" :data="hosts" row-key="id" class="ui-table" :empty-text="hostsLoadFailed ? '' : hostsLoading ? '加载中' : '暂无主机'" @selection-change="selectedHosts = $event">
              <ElTableColumn type="selection" width="44" />
              <ElTableColumn label="主机" min-width="190">
                <template #default="{ row }">
                  <div class="ui-item-title">{{ hostDisplayName(row as Host) }}</div>
                  <div v-if="row.name" class="ui-item-secondary">{{ row.address }}</div>
                </template>
              </ElTableColumn>
              <ElTableColumn label="分组" min-width="110"><template #default="{ row }">{{ groupName(row.group_id) }}</template></ElTableColumn>
              <ElTableColumn label="登录" min-width="150"><template #default="{ row }"><div>{{ row.username }} · {{ row.port }}</div><div class="ui-item-secondary">{{ row.auth_type === 'key' ? '密钥认证' : '密码认证' }}</div></template></ElTableColumn>
              <ElTableColumn label="跳板机" min-width="190"><template #default="{ row }">{{ row.jump_host_id !== null && !jumpHostsLoaded ? jumpHostsLoading ? '加载中' : '' : jumpHostName(row.jump_host_id) }}</template></ElTableColumn>
              <ElTableColumn label="更新时间" min-width="160"><template #default="{ row }">{{ dateLabel(row.updated_at) }}</template></ElTableColumn>
              <ElTableColumn label="连接状态" width="100" align="center">
                <template #default="{ row }">
                  <HostSSHStatus
                    :host="row as Host"
                    :display="connectionTestDisplay(row as Host, row.connection_status)"
                  />
                </template>
              </ElTableColumn>
              <ElTableColumn label="操作" width="344" fixed="right">
                <template #default="{ row }">
                  <div class="host-row-actions">
                    <ElButton
                      link type="primary"
                      :loading="testing && isTestTarget(row as Host)"
                      :disabled="testing"
                      @click="startHostConnectionTest(row as Host)"
                    >连接测试</ElButton>
                    <ElButton link type="primary" @click="openEditHost(row.id)">编辑</ElButton>
                    <ElDropdown trigger="click" @command="openBasicInfo(row as Host)">
                      <ElButton link type="primary">更多操作</ElButton>
                      <template #dropdown>
                        <ElDropdownMenu>
                          <ElDropdownItem command="collect-basic-info">获取基础信息</ElDropdownItem>
                        </ElDropdownMenu>
                      </template>
                    </ElDropdown>
                    <ElButton link type="danger" @click="removeHost(row.id, hostDisplayName(row as Host))">删除</ElButton>
                  </div>
                </template>
              </ElTableColumn>
            </ElTable>
          </div>
          <ElEmpty v-if="!hostsLoading && !hostsLoadFailed && !hosts.length" :description="search || selectedGroup !== null ? '暂无符合条件的主机' : '暂无主机，请新增主机'" class="ui-empty"><ElButton v-if="!search && selectedGroup === null" type="primary" plain @click="openNewHost">新增主机</ElButton></ElEmpty>
          <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :total-known="!hostsLoading && !hostsLoadFailed" :disabled="hostsLoading || hostsLoadFailed" />
        </section>
      </div>
    </main>

    <BatchSSHConnectionDialog v-model="batchDialog" :hosts="batchHosts" @status-changed="loadHosts" />
    <HostBasicInfoDialog v-model="basicInfoDialog" :host="basicInfoHost" @saved="loadHosts" />
     <ElDialog v-model="hostDialog" align-center :title="editingHost ? '编辑主机' : '新增主机'" width="min(var(--ui-dialog-width), calc(100vw - 32px))" class="host-dialog" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
       <div ref="formRoot" class="ui-form host-form">
         <ElAlert v-if="dialogError" :title="dialogError" type="error" :closable="false" show-icon data-form-error tabindex="-1" />
         <HostForm
           v-model="hostForm"
           :groups="groups"
           :jump-hosts="jumpHosts"
           :jump-hosts-loading="jumpHostsLoading"
           :jump-hosts-loaded="jumpHostsLoaded"
           :ssh-keys="sshKeys"
           :ssh-keys-loading="sshKeysLoading"
           :ssh-keys-loaded="sshKeysLoaded"
           :editing-host="editingHost"
           :auth-changed="hostAuthChanged"
           :errors="fieldErrors"
         />
      </div>
      <template #footer><ElButton :disabled="saving" @click="hostDialog = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="saveHost">保存</ElButton></template>
    </ElDialog>
</template>

<style scoped>
.host-row-actions {
  display: flex;
  align-items: center;
  gap: var(--ui-space-2);
  white-space: nowrap;
}
.host-row-actions > :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
