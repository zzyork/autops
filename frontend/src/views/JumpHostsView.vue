<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import {
  ElAlert, ElButton, ElDialog, ElEmpty, ElInput, ElInputNumber, ElLoading, ElMessageBox,
  ElOption, ElRadioButton, ElRadioGroup, ElSelect, ElTable, ElTableColumn,
} from 'element-plus'
import { createJumpHost, deleteJumpHost, getJumpHost, listJumpHosts, updateJumpHost } from '@/api/jump_hosts'
import { listSSHKeys } from '@/api/ssh_keys'
import AssetsLayout from '@/components/AssetsLayout.vue'
import { showSystemError } from '@/components/feedback'
import type { AuthType, JumpHost, JumpHostInput, SSHKey } from '@/types/api'

interface JumpHostForm {
  name: string
  address: string
  username: string
  port: number
  auth_type: AuthType
  ssh_key_id: number | null
  password: string
  remark: string
}

const vLoading = ElLoading.directive
const jumpHosts = ref<JumpHost[]>([])
const sshKeys = ref<SSHKey[]>([])
const sshKeysLoading = ref(false)
const sshKeysLoaded = ref(false)
const search = ref('')
const loading = ref(false)
const opening = ref(false)
const saving = ref(false)
const loadFailed = ref(false)
const localError = ref('')
const dialogError = ref('')
const dialog = ref(false)
const editing = ref<JumpHost | null>(null)
const authChanged = ref(false)
const invalidFields = ref<Set<keyof JumpHostForm>>(new Set())
const form = ref<JumpHostForm>({ name: '', address: '', username: '', port: 22, auth_type: 'password', ssh_key_id: null, password: '', remark: '' })

watch(() => ({ ...form.value }), (next, previous) => {
  for (const key of Object.keys(next) as (keyof JumpHostForm)[]) {
    if (next[key] !== previous[key]) invalidFields.value.delete(key)
  }
}, { flush: 'sync' })
watch(() => form.value.auth_type, (next, previous) => {
  if (dialog.value && next !== previous) {
    authChanged.value = true
    form.value.password = ''
    form.value.ssh_key_id = null
  }
}, { flush: 'sync' })

let searchTimer: ReturnType<typeof setTimeout> | undefined
let requestId = 0
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
async function refresh() {
  const current = ++requestId
  loading.value = true
  loadFailed.value = false
  try {
    const result = await listJumpHosts(search.value.trim())
    if (current === requestId) jumpHosts.value = result
  } catch {
    if (current === requestId) {
      jumpHosts.value = []
      loadFailed.value = true
      showSystemError()
    }
  } finally {
    if (current === requestId) loading.value = false
  }
}

watch(search, () => {
  clearTimeout(searchTimer)
  requestId++
  loading.value = true
  searchTimer = setTimeout(refresh, search.value ? 250 : 0)
})
onMounted(() => { void refresh() })
onUnmounted(() => {
  clearTimeout(searchTimer)
  requestId++
  sshKeyRequest++
})

function openNew() {
  editing.value = null
  authChanged.value = false
  form.value = { name: '', address: '', username: '', port: 22, auth_type: 'password', ssh_key_id: null, password: '', remark: '' }
  invalidFields.value.clear()
  dialogError.value = ''
  dialog.value = true
  void refreshSSHKeys()
}

async function openEdit(id: number) {
  opening.value = true
  try {
    const item = await getJumpHost(id)
    editing.value = item
    authChanged.value = false
    form.value = {
      name: item.name, address: item.address, username: item.username, port: item.port,
      auth_type: item.auth_type, ssh_key_id: item.ssh_key_id, password: '', remark: item.remark,
    }
    invalidFields.value.clear()
    dialogError.value = ''
    dialog.value = true
    void refreshSSHKeys()
  } catch {
    showSystemError()
  } finally {
    opening.value = false
  }
}

function validate(): string | false {
  const value = form.value
  invalidFields.value.clear()
  if (!value.name.trim() || !value.address.trim() || !value.username.trim()) {
    if (!value.name.trim()) invalidFields.value.add('name')
    if (!value.address.trim()) invalidFields.value.add('address')
    if (!value.username.trim()) invalidFields.value.add('username')
    return '请填写跳板机名称、地址和用户名。'
  }
  if (!Number.isInteger(value.port) || value.port < 1 || value.port > 65535) {
    invalidFields.value.add('port')
    return '端口须在 1 到 65535 之间。'
  }
  if (sshKeysLoading.value) return '密钥列表加载中。'
  if (!sshKeysLoaded.value) return false
  if (value.auth_type === 'key' && value.ssh_key_id === null) {
    invalidFields.value.add('ssh_key_id')
    return editing.value?.auth_type === 'key' && editing.value.ssh_key_id === null
      ? '旧记录尚未关联密钥，请先导入并选择 SSH 密钥。' : '请选择 SSH 密钥。'
  }
  if (value.auth_type === 'key' && !sshKeys.value.some((item) => item.id === value.ssh_key_id)) {
    invalidFields.value.add('ssh_key_id')
    return false
  }
  if (value.auth_type === 'password' && !value.password &&
    !(editing.value?.auth_type === 'password' && editing.value.has_password && !authChanged.value)) {
    invalidFields.value.add('password')
    return '请输入跳板机密码；切换为密码认证时不能沿用原凭据。'
  }
  if (editing.value && value.auth_type === 'password' && !value.password &&
    (value.address.trim() !== editing.value.address || value.username.trim() !== editing.value.username || value.port !== editing.value.port)) {
    invalidFields.value.add('password')
    return '连接信息已变更，请重新填写跳板机密码。'
  }
  return ''
}

async function save() {
  const validation = validate()
  if (validation === false) { dialogError.value = ''; showSystemError(); return }
  if (validation) { dialogError.value = validation; return }
  const value = form.value
  const previous = editing.value
  const body: JumpHostInput = {
    name: value.name.trim(), address: value.address.trim(), username: value.username.trim(),
    port: value.port, auth_type: value.auth_type,
    ssh_key_id: value.auth_type === 'key' ? value.ssh_key_id : null,
    remark: value.remark.trim(),
  }
  if (value.auth_type === 'password' && value.password) body.password = value.password
  saving.value = true
  dialogError.value = ''
  try {
    if (previous) await updateJumpHost(previous.id, { ...body, version: previous.version })
    else await createJumpHost(body)
    dialog.value = false
    void refresh()
  } catch {
    showSystemError()
  } finally {
    saving.value = false
  }
}

async function remove(item: JumpHost) {
  if (item.host_count > 0) { localError.value = '请先解除该跳板机与主机的关联。'; return }
  try {
    await ElMessageBox.confirm(`确定删除跳板机“${item.name}”吗？此操作不可撤销。`, '删除跳板机', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'delete-confirm-button',
    })
  } catch { return }
  localError.value = ''
  try {
    await deleteJumpHost(item.id)
    await refresh()
  } catch {
    showSystemError()
  }
}

function dateLabel(value: string) {
  return new Date(value).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <AssetsLayout title="跳板机管理">
    <main class="assets-main">
      <div class="assets-heading"><h1>跳板机管理</h1></div>
      <section class="host-section" aria-label="跳板机列表">
        <div class="host-toolbar"><ElButton type="primary" @click="openNew">新增跳板机</ElButton><div class="host-toolbar-right"><ElInput v-model="search" clearable placeholder="搜索名称或地址" aria-label="搜索跳板机名称或地址" class="host-search" /><ElButton :loading="loading" @click="refresh">刷新</ElButton></div></div>
        <ElAlert v-if="localError" :title="localError" type="error" :closable="false" show-icon class="assets-alert" />
        <div class="host-table-wrap">
          <ElTable v-loading="loading || opening" :data="jumpHosts" row-key="id" class="host-table" :empty-text="loadFailed ? '' : loading ? '加载中' : '暂无跳板机'">
            <ElTableColumn label="跳板机" min-width="200"><template #default="{ row }"><div class="host-name">{{ row.name }}</div><div class="host-address">{{ row.address }}</div></template></ElTableColumn>
            <ElTableColumn label="登录" min-width="150"><template #default="{ row }"><div>{{ row.username }} · {{ row.port }}</div><div class="host-secondary">{{ row.auth_type === 'key' ? '密钥认证' : '密码认证' }}</div></template></ElTableColumn>
            <ElTableColumn prop="host_count" label="关联主机" width="100" />
            <ElTableColumn label="备注" min-width="180"><template #default="{ row }"><div class="group-remark">{{ row.remark }}</div></template></ElTableColumn>
            <ElTableColumn label="更新时间" min-width="160"><template #default="{ row }">{{ dateLabel(row.updated_at) }}</template></ElTableColumn>
            <ElTableColumn label="操作" width="128" fixed="right"><template #default="{ row }"><ElButton link type="primary" @click="openEdit(row.id)">编辑</ElButton><span :title="row.host_count ? '请先解除关联主机' : undefined"><ElButton link type="danger" :disabled="row.host_count > 0" @click="remove(row as JumpHost)">删除</ElButton></span></template></ElTableColumn>
          </ElTable>
        </div>
        <ElEmpty v-if="!loading && !loadFailed && !jumpHosts.length" :description="search ? '暂无符合条件的跳板机' : '暂无跳板机，请新增跳板机'" class="host-empty"><ElButton v-if="!search" type="primary" plain @click="openNew">新增跳板机</ElButton></ElEmpty>
      </section>
    </main>

    <ElDialog v-model="dialog" align-center :title="editing ? '编辑跳板机' : '新增跳板机'" width="min(720px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
      <div class="asset-form">
        <div class="form-section-title">基本信息</div>
        <div class="field-grid">
          <label class="field" :class="{ 'is-error': invalidFields.has('name') }"><span>跳板机名称 <em>*</em></span><ElInput v-model="form.name" maxlength="100" :aria-invalid="invalidFields.has('name') ? 'true' : undefined" /></label>
          <label class="field" :class="{ 'is-error': invalidFields.has('address') }"><span>地址 <em>*</em></span><ElInput v-model="form.address" maxlength="253" placeholder="IP 或域名" :aria-invalid="invalidFields.has('address') ? 'true' : undefined" /></label>
        </div>
        <div class="form-section-title">登录信息</div>
        <div class="field-grid">
          <label class="field" :class="{ 'is-error': invalidFields.has('username') }"><span>用户名 <em>*</em></span><ElInput v-model="form.username" maxlength="100" autocomplete="off" :aria-invalid="invalidFields.has('username') ? 'true' : undefined" /></label>
          <label class="field" :class="{ 'is-error': invalidFields.has('port') }"><span>端口 <em>*</em></span><ElInputNumber v-model="form.port" :min="1" :max="65535" :controls="false" class="full-width" :aria-invalid="invalidFields.has('port') ? 'true' : undefined" /></label>
        </div>
        <div class="field"><span>认证方式</span><ElRadioGroup v-model="form.auth_type" aria-label="跳板机认证方式"><ElRadioButton value="password">密码</ElRadioButton><ElRadioButton value="key">SSH 密钥</ElRadioButton></ElRadioGroup></div>
        <label v-if="form.auth_type === 'password'" class="field" :class="{ 'is-error': invalidFields.has('password') }"><span>密码 <em v-if="!editing || editing.auth_type !== 'password' || !editing.has_password || authChanged || (form.address.trim() !== editing.address || form.username.trim() !== editing.username || form.port !== editing.port)">*</em></span><ElInput v-model="form.password" type="password" show-password autocomplete="new-password" :placeholder="editing?.auth_type === 'password' && editing.has_password && !authChanged ? '连接信息不变时留空保留原密码' : '请输入密码'" :aria-invalid="invalidFields.has('password') ? 'true' : undefined" /></label>
        <template v-else><label class="field" :class="{ 'is-error': invalidFields.has('ssh_key_id') }"><span>SSH 密钥 <em>*</em></span><ElSelect v-model="form.ssh_key_id" :disabled="sshKeysLoading || !sshKeysLoaded" :placeholder="sshKeysLoading ? '加载中' : '请选择密钥'" class="full-width" :aria-invalid="invalidFields.has('ssh_key_id') ? 'true' : undefined"><ElOption v-for="key in sshKeys" :key="key.id" :label="`${key.name} · ${key.key_type} · ${key.fingerprint}`" :value="key.id" /></ElSelect></label><ElAlert v-if="editing?.auth_type === 'key' && editing.ssh_key_id === null && form.ssh_key_id === null" title="旧记录尚未关联密钥，请先导入并选择 SSH 密钥。" type="warning" :closable="false" show-icon /><RouterLink to="/assets/ssh-keys">管理 SSH 密钥</RouterLink></template>
        <label class="field"><span>备注</span><ElInput v-model="form.remark" type="textarea" :rows="3" maxlength="2000" placeholder="可选" /></label>
        <ElAlert v-if="dialogError" :title="dialogError" type="error" :closable="false" show-icon />
      </div>
      <template #footer><ElButton :disabled="saving" @click="dialog = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="save">保存</ElButton></template>
    </ElDialog>
  </AssetsLayout>
</template>
