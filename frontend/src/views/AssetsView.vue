<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import {
  ElAlert, ElButton, ElDialog, ElEmpty, ElInput, ElInputNumber, ElLoading, ElMessage, ElMessageBox,
  ElOption, ElRadioButton, ElRadioGroup, ElSelect, ElSwitch, ElTable, ElTableColumn,
} from 'element-plus'
import { createGroup, createHost, deleteGroup, deleteHost, getHost, listGroups, listHosts, updateGroup, updateHost } from '@/api/assets'
import { HttpError } from '@/api/http'
import type { AuthType, Host, HostGroup, HostInput } from '@/types/api'
import '@/styles/assets.css'

interface HostForm {
  name: string
  address: string
  group_id: number | ''
  username: string
  port: number
  auth_type: AuthType
  key_path: string
  password: string
  vip: string
  proxy_address: string
  proxy_username: string
  proxy_port: number
  proxy_auth_type: AuthType
  proxy_key_path: string
  proxy_password: string
  remark: string
}

const groups = ref<HostGroup[]>([])
const menuCollapsed = ref(false)
const vLoading = ElLoading.directive
const hosts = ref<Host[]>([])
const selectedGroup = ref<number | null>(null)
const search = ref('')
const groupsLoading = ref(false)
const hostsLoading = ref(false)
const groupsError = ref('')
const hostsError = ref('')
const dialogError = ref('')
const saving = ref(false)
const openingHost = ref(false)
const groupDialog = ref(false)
const hostDialog = ref(false)
const editingGroup = ref<HostGroup | null>(null)
const editingHost = ref<Host | null>(null)
const groupForm = ref({ name: '', remark: '' })
const proxyEnabled = ref(false)
const hostAuthChanged = ref(false)
const proxyAuthChanged = ref(false)

function emptyHost(groupId: number | null): HostForm {
  return {
    name: '', address: '', group_id: groupId ?? '', username: '', port: 22,
    auth_type: 'password', key_path: '', password: '', vip: '', proxy_address: '',
    proxy_username: '', proxy_port: 22, proxy_auth_type: 'password',
    proxy_key_path: '', proxy_password: '', remark: '',
  }
}

const hostForm = ref<HostForm>(emptyHost(null))
watch(() => hostForm.value.auth_type, (next, previous) => {
  if (hostDialog.value && next !== previous) {
    hostAuthChanged.value = true
    hostForm.value.password = ''
  }
}, { flush: 'sync' })
watch(() => hostForm.value.proxy_auth_type, (next, previous) => {
  if (hostDialog.value && next !== previous) {
    proxyAuthChanged.value = true
    hostForm.value.proxy_password = ''
  }
}, { flush: 'sync' })

function errorText(cause: unknown): string {
  if (cause instanceof HttpError) return cause.message
  return '无法连接服务，请稍后重试。'
}

async function refreshGroups() {
  groupsLoading.value = true
  groupsError.value = ''
  try {
    groups.value = await listGroups()
  } catch (cause) {
    groupsError.value = errorText(cause)
  } finally {
    groupsLoading.value = false
  }
}

let searchTimer: ReturnType<typeof setTimeout> | undefined
let hostRequest = 0
async function refreshHosts() {
  const current = ++hostRequest
  hostsLoading.value = true
  hostsError.value = ''
  try {
    const result = await listHosts(search.value.trim(), selectedGroup.value)
    if (current === hostRequest) hosts.value = result
  } catch (cause) {
    if (current === hostRequest) {
      hosts.value = []
      hostsError.value = errorText(cause)
    }
  } finally {
    if (current === hostRequest) hostsLoading.value = false
  }
}

watch([search, selectedGroup], () => {
  clearTimeout(searchTimer)
  hostRequest++
  hostsLoading.value = true
  searchTimer = setTimeout(refreshHosts, search.value ? 250 : 0)
})
onMounted(() => { void refreshGroups(); void refreshHosts() })
onUnmounted(() => { clearTimeout(searchTimer); hostRequest++ })

function openGroup(group: HostGroup | null = null) {
  editingGroup.value = group
  groupForm.value = { name: group?.name ?? '', remark: group?.remark ?? '' }
  dialogError.value = ''
  groupDialog.value = true
}

async function saveGroup() {
  const body = { name: groupForm.value.name.trim(), remark: groupForm.value.remark.trim() }
  if (!body.name) { dialogError.value = '请输入分组名称。'; return }
  saving.value = true
  dialogError.value = ''
  try {
    if (editingGroup.value) await updateGroup(editingGroup.value.id, body)
    else await createGroup(body)
    groupDialog.value = false
    await refreshGroups()
  } catch (cause) {
    dialogError.value = errorText(cause)
  } finally {
    saving.value = false
  }
}

async function removeGroup(group: HostGroup) {
  if (group.host_count > 0) {
    groupsError.value = '请先移动或删除该分组内的主机。'
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除分组“${group.name}”吗？`,
      '删除分组', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch { return }
  groupsError.value = ''
  try {
    await deleteGroup(group.id)
    if (selectedGroup.value === group.id) selectedGroup.value = null
    await Promise.all([refreshGroups(), refreshHosts()])
  } catch (cause) {
    groupsError.value = errorText(cause)
  }
}

function openNewHost() {
  if (groupsLoading.value) { ElMessage.info('分组加载中，请稍后重试。'); return }
  if (!groups.value.length) { ElMessage.warning('请先新增分组，再新增主机。'); return }
  editingHost.value = null
  hostAuthChanged.value = false
  proxyAuthChanged.value = false
  hostForm.value = emptyHost(selectedGroup.value)
  proxyEnabled.value = false
  dialogError.value = ''
  hostDialog.value = true
}

async function openEditHost(id: number) {
  openingHost.value = true
  hostsError.value = ''
  try {
    const host = await getHost(id)
    editingHost.value = host
    hostAuthChanged.value = false
    proxyAuthChanged.value = false
    hostForm.value = {
      name: host.name, address: host.address, group_id: host.group_id,
      username: host.username, port: host.port, auth_type: host.auth_type,
      key_path: host.key_path ?? '', password: '', vip: host.vip ?? '',
      proxy_address: host.proxy_address ?? '', proxy_username: host.proxy_username ?? '',
      proxy_port: host.proxy_port ?? 22, proxy_auth_type: host.proxy_auth_type ?? 'password',
      proxy_key_path: host.proxy_key_path ?? '', proxy_password: '', remark: host.remark,
    }
    proxyEnabled.value = host.proxy_address !== null
    dialogError.value = ''
    hostDialog.value = true
  } catch (cause) {
    hostsError.value = errorText(cause)
  } finally {
    openingHost.value = false
  }
}

function toggleProxy(value: string | number | boolean) {
  const enabled = value === true
  if (editingHost.value && proxyEnabled.value !== enabled) proxyAuthChanged.value = true
  proxyEnabled.value = enabled
  if (!enabled) {
    hostForm.value.proxy_address = ''
    hostForm.value.proxy_username = ''
    hostForm.value.proxy_port = 22
    hostForm.value.proxy_auth_type = 'password'
    hostForm.value.proxy_key_path = ''
    hostForm.value.proxy_password = ''
  }
}

function validateHost(): string {
  const form = hostForm.value
  if (!form.name.trim() || !form.address.trim() || !form.username.trim()) return '请填写主机名称、地址和用户名。'
  if (!Number.isInteger(form.port) || form.port < 1 || form.port > 65535) return '主机端口须在 1 到 65535 之间。'
  if (form.auth_type === 'key' && !form.key_path.trim()) return '请输入主机密钥路径。'
  if (form.auth_type === 'password' && !form.password &&
    !(editingHost.value?.auth_type === 'password' && editingHost.value.has_password && !hostAuthChanged.value)) {
    return '请输入主机密码；切换为密码认证时不能沿用原凭据。'
  }
  if (editingHost.value && form.auth_type === 'password' && !form.password &&
    (form.address.trim() !== editingHost.value.address || form.username.trim() !== editingHost.value.username || form.port !== editingHost.value.port)) return '连接信息已变更，请重新填写主机密码。'
  if (proxyEnabled.value) {
    if (editingHost.value && form.proxy_auth_type === 'password' && !form.proxy_password &&
      (form.proxy_address.trim() !== editingHost.value.proxy_address || form.proxy_username.trim() !== editingHost.value.proxy_username || form.proxy_port !== editingHost.value.proxy_port)) return '跳板机连接信息已变更，请重新填写跳板机密码。'
    if (!form.proxy_address.trim() || !form.proxy_username.trim()) return '请填写跳板机地址和用户名。'
    if (!Number.isInteger(form.proxy_port) || form.proxy_port < 1 || form.proxy_port > 65535) return '跳板机端口须在 1 到 65535 之间。'
    if (form.proxy_auth_type === 'key' && !form.proxy_key_path.trim()) return '请输入跳板机密钥路径。'
    if (form.proxy_auth_type === 'password' && !form.proxy_password &&
      !(editingHost.value?.proxy_auth_type === 'password' && editingHost.value.has_proxy_password && !proxyAuthChanged.value)) {
      return '请输入跳板机密码；切换为密码认证时不能沿用原凭据。'
    }
  }
  return ''
}

async function saveHost() {
  const groupId = hostForm.value.group_id
  if (groupId === '' || !Number.isInteger(groupId) || groupId <= 0) {
    dialogError.value = '请选择所属分组。'
    return
  }
  const validation = validateHost()
  if (validation) { dialogError.value = validation; return }
  const form = hostForm.value
  const previous = editingHost.value
  const body: HostInput = {
    name: form.name.trim(), address: form.address.trim(), group_id: groupId,
    username: form.username.trim(), port: form.port, auth_type: form.auth_type,
    key_path: form.auth_type === 'key' ? form.key_path.trim() : null,
    vip: form.vip.trim() || null,
    proxy_address: proxyEnabled.value ? form.proxy_address.trim() : null,
    proxy_username: proxyEnabled.value ? form.proxy_username.trim() : null,
    proxy_port: proxyEnabled.value ? form.proxy_port : null,
    proxy_auth_type: proxyEnabled.value ? form.proxy_auth_type : null,
    proxy_key_path: proxyEnabled.value && form.proxy_auth_type === 'key' ? form.proxy_key_path.trim() : null,
    remark: form.remark.trim(),
  }
  if (previous) body.version = previous.version
  if (form.auth_type === 'password' && form.password) body.password = form.password
  if (!proxyEnabled.value) body.proxy_password = null
  else if (form.proxy_auth_type === 'password' && form.proxy_password) body.proxy_password = form.proxy_password

  saving.value = true
  dialogError.value = ''
  try {
    if (previous) await updateHost(previous.id, body)
    else await createHost(body)
    hostDialog.value = false
    await Promise.all([refreshHosts(), refreshGroups()])
  } catch (cause) {
    dialogError.value = errorText(cause)
  } finally {
    saving.value = false
  }
}

async function removeHost(id: number, name: string) {
  try {
    await ElMessageBox.confirm(`确定删除主机“${name}”吗？此操作不可撤销。`, '删除主机', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  hostsError.value = ''
  try {
    await deleteHost(id)
    await Promise.all([refreshHosts(), refreshGroups()])
  } catch (cause) {
    hostsError.value = errorText(cause)
  }
}

function groupName(id: number) {
  return groups.value.find((group) => group.id === id)?.name
}

function dateLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="workspace assets-page" :class="{ 'menu-collapsed': menuCollapsed }">
    <header class="topbar console-topbar">
      <RouterLink to="/assets" class="brand" aria-label="autops 资产管理"><span class="brand-mark">a.</span>autops</RouterLink>
      <span class="console-title">运维控制台</span>
      <span class="console-version">v0.1</span>
    </header>
    <aside class="console-sidebar" aria-label="主导航">
      <div class="console-sidebar-heading"><span v-if="!menuCollapsed">控制台</span><button class="menu-toggle" type="button" :aria-label="menuCollapsed ? '展开菜单' : '收起菜单'" :aria-expanded="!menuCollapsed" @click="menuCollapsed = !menuCollapsed"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg></button></div>
      <div v-if="!menuCollapsed" class="console-menu-label">资产管理</div>
      <RouterLink to="/assets" class="console-menu-item" aria-current="page" title="资产列表"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="1" /><path d="M8 21h8M12 16v5M3 12h18" /></svg><span v-if="!menuCollapsed">资产列表</span></RouterLink>
    </aside>
    <div class="console-content">
    <div class="console-breadcrumb"><span>资产管理</span><span class="breadcrumb-separator">/</span><strong>资产列表</strong></div>
    <main class="assets-main">
      <ElAlert v-if="!groupsLoading && !groupsError && !groups.length" title="暂无分组，请先新增分组。" type="info" :closable="false" show-icon class="assets-alert" />
      <div class="assets-layout">
        <aside class="group-sidebar" aria-label="主机分组">
          <div class="section-header"><h2>分组</h2><ElButton text type="primary" @click="openGroup()">新增分组</ElButton></div>
          <ElAlert v-if="groupsError" :title="groupsError" type="error" :closable="false" show-icon />
          <div v-loading="groupsLoading" class="group-list">
            <button type="button" class="group-item" :class="{ active: selectedGroup === null }" @click="selectedGroup = null"><span>全部主机</span></button>
            <div v-for="group in groups" :key="group.id" class="group-row" :class="{ active: selectedGroup === group.id }">
              <button type="button" class="group-choice" :title="group.remark || group.name" @click="selectedGroup = group.id"><span class="group-name">{{ group.name }}</span><span class="group-count">{{ group.host_count }}</span></button>
              <div class="group-actions"><ElButton text size="small" :aria-label="`编辑分组${group.name}`" @click="openGroup(group)">编辑</ElButton><span :title="group.host_count ? '请先移动或删除组内主机' : undefined"><ElButton text size="small" type="danger" :disabled="group.host_count > 0" :aria-label="`删除分组${group.name}`" @click="removeGroup(group)">删除</ElButton></span></div>
            </div>
          </div>
        </aside>
        <section class="host-section" aria-labelledby="host-title">
          <div class="section-header"><div class="host-title-row"><h2 id="host-title">资产列表</h2><span class="host-total">{{ hosts.length }} 台</span></div></div>
          <div class="host-toolbar"><ElButton type="primary" @click="openNewHost">新增主机</ElButton><div class="host-toolbar-right"><ElInput v-model="search" clearable placeholder="搜索名称或地址" aria-label="搜索主机名称或地址" class="host-search" /><ElButton :loading="hostsLoading || groupsLoading" @click="refreshGroups(); refreshHosts()">刷新</ElButton></div></div>
          <ElAlert v-if="hostsError" :title="hostsError" type="error" :closable="false" show-icon class="assets-alert" />
          <div class="host-table-wrap">
            <ElTable v-loading="hostsLoading || openingHost" :data="hosts" row-key="id" class="host-table" :empty-text="hostsError ? '加载失败' : '暂无主机'">
              <ElTableColumn label="主机" min-width="190"><template #default="{ row }"><div class="host-name">{{ row.name }}</div><div class="host-address">{{ row.address }}</div></template></ElTableColumn>
              <ElTableColumn label="分组" min-width="110"><template #default="{ row }">{{ groupName(row.group_id) }}</template></ElTableColumn>
              <ElTableColumn label="登录" min-width="150"><template #default="{ row }"><div>{{ row.username }} · {{ row.port }}</div><div class="host-secondary">{{ row.auth_type === 'key' ? '密钥认证' : '密码认证' }}</div></template></ElTableColumn>
              <ElTableColumn label="跳板机" min-width="130"><template #default="{ row }">{{ row.proxy_address || '未启用' }}</template></ElTableColumn>
              <ElTableColumn label="更新时间" min-width="160"><template #default="{ row }">{{ dateLabel(row.updated_at) }}</template></ElTableColumn>
              <ElTableColumn label="操作" width="128" fixed="right"><template #default="{ row }"><ElButton link type="primary" @click="openEditHost(row.id)">编辑</ElButton><ElButton link type="danger" @click="removeHost(row.id, row.name)">删除</ElButton></template></ElTableColumn>
            </ElTable>
          </div>
          <ElEmpty v-if="!hostsLoading && !hostsError && !hosts.length" description="暂无符合条件的主机" class="host-empty"><ElButton v-if="!search && selectedGroup === null" type="primary" plain @click="openNewHost">新增主机</ElButton></ElEmpty>
        </section>
      </div>
    </main>
    </div>

    <ElDialog v-model="groupDialog" :title="editingGroup ? '编辑分组' : '新增分组'" width="min(440px, 92vw)" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
      <div class="asset-form"><label class="field"><span>分组名称 <em>*</em></span><ElInput v-model="groupForm.name" maxlength="100" placeholder="输入分组名称" /></label><label class="field"><span>备注</span><ElInput v-model="groupForm.remark" type="textarea" :rows="3" placeholder="可选" /></label><ElAlert v-if="dialogError" :title="dialogError" type="error" :closable="false" show-icon /></div>
      <template #footer><ElButton :disabled="saving" @click="groupDialog = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="saveGroup">保存</ElButton></template>
    </ElDialog>

    <ElDialog v-model="hostDialog" :title="editingHost ? '编辑主机' : '新增主机'" width="min(720px, 94vw)" class="host-dialog" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
      <div class="asset-form host-form">
        <div class="form-section-title">基本信息</div>
        <div class="field-grid"><label class="field"><span>主机名称 <em>*</em></span><ElInput v-model="hostForm.name" placeholder="例：生产主机 01" /></label><label class="field"><span>地址 <em>*</em></span><ElInput v-model="hostForm.address" placeholder="IP 或域名" /></label><label class="field"><span>所属分组 <em>*</em></span><ElSelect v-model="hostForm.group_id" placeholder="请选择分组" class="full-width"><ElOption v-for="group in groups" :key="group.id" :label="group.name" :value="group.id" /></ElSelect></label><label class="field"><span>虚拟 IP（VIP）</span><ElInput v-model="hostForm.vip" placeholder="可选" /></label></div>
        <div class="form-section-title">登录信息</div>
        <div class="field-grid"><label class="field"><span>用户名 <em>*</em></span><ElInput v-model="hostForm.username" autocomplete="off" /></label><label class="field"><span>端口 <em>*</em></span><ElInputNumber v-model="hostForm.port" :min="1" :max="65535" :controls="false" class="full-width" /></label></div>
        <div class="field"><span>认证方式</span><ElRadioGroup v-model="hostForm.auth_type"><ElRadioButton value="password">密码</ElRadioButton><ElRadioButton value="key">密钥路径</ElRadioButton></ElRadioGroup></div>
        <label v-if="hostForm.auth_type === 'password'" class="field"><span>密码 <em v-if="!editingHost || editingHost.auth_type !== 'password' || !editingHost.has_password || hostAuthChanged">*</em></span><ElInput v-model="hostForm.password" type="password" show-password autocomplete="new-password" :placeholder="editingHost?.auth_type === 'password' && editingHost.has_password && !hostAuthChanged ? '留空保留原密码' : '请输入密码'" /></label>
        <label v-else class="field"><span>密钥路径 <em>*</em></span><ElInput v-model="hostForm.key_path" placeholder="服务端可读取的密钥路径" /></label>
        <div class="form-section-title proxy-heading"><span>跳板机</span><ElSwitch :model-value="proxyEnabled" aria-label="启用跳板机" @update:model-value="toggleProxy" /></div>
        <template v-if="proxyEnabled"><div class="field-grid"><label class="field"><span>跳板机地址 <em>*</em></span><ElInput v-model="hostForm.proxy_address" placeholder="IP 或域名" /></label><label class="field"><span>跳板机用户名 <em>*</em></span><ElInput v-model="hostForm.proxy_username" autocomplete="off" /></label><label class="field"><span>跳板机端口 <em>*</em></span><ElInputNumber v-model="hostForm.proxy_port" :min="1" :max="65535" :controls="false" class="full-width" /></label></div><div class="field"><span>跳板机认证</span><ElRadioGroup v-model="hostForm.proxy_auth_type"><ElRadioButton value="password">密码</ElRadioButton><ElRadioButton value="key">密钥路径</ElRadioButton></ElRadioGroup></div><label v-if="hostForm.proxy_auth_type === 'password'" class="field"><span>跳板机密码 <em v-if="!editingHost || editingHost.proxy_auth_type !== 'password' || !editingHost.has_proxy_password || proxyAuthChanged">*</em></span><ElInput v-model="hostForm.proxy_password" type="password" show-password autocomplete="new-password" :placeholder="editingHost?.proxy_auth_type === 'password' && editingHost.has_proxy_password && !proxyAuthChanged ? '留空保留原密码' : '请输入密码'" /></label><label v-else class="field"><span>跳板机密钥路径 <em>*</em></span><ElInput v-model="hostForm.proxy_key_path" placeholder="服务端可读取的密钥路径" /></label></template>
        <label class="field"><span>备注</span><ElInput v-model="hostForm.remark" type="textarea" :rows="3" placeholder="可选" /></label>
        <ElAlert v-if="dialogError" :title="dialogError" type="error" :closable="false" show-icon />
      </div>
      <template #footer><ElButton :disabled="saving" @click="hostDialog = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="saveHost">保存</ElButton></template>
    </ElDialog>
  </div>
</template>
