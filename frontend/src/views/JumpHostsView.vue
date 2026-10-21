<script setup lang="ts">
import { onUnmounted, ref, useId, watch } from 'vue'
import {
  ElAlert, ElButton, ElDialog, ElEmpty, ElInput, ElInputNumber, ElLoading, ElMessageBox,
  ElOption, ElRadioButton, ElRadioGroup, ElSelect, ElTable, ElTableColumn,
} from 'element-plus'
import { createJumpHost, deleteJumpHost, getJumpHost, listJumpHostsPage, updateJumpHost } from '@/api/jump_hosts'
import { listSSHKeys } from '@/api/ssh_keys'
import TestStatus from '@/components/TestStatus.vue'
import { useSSHConnectionTest } from '@/components/sshConnectionTest'
import ListPagination from '@/components/ListPagination.vue'
import FieldError from '@/components/FieldError.vue'
import { focusFormFeedback, vNativeFieldAria } from '@/components/formFeedback'
import { useServerPagination } from '@/components/serverPagination'
import { showSystemError } from '@/components/feedback'
import type { AuthType, JumpHost, JumpHostInput, SSHKey } from '@/types/api'
import '@/styles/assets.css'

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
const { items: jumpHosts, page, pageSize, total, loading, loadFailed, refresh: load, resetPage, invalidate } =
  useServerPagination<JumpHost>((currentPage, size) => listJumpHostsPage(search.value.trim(), currentPage, size))
const { testing, testConnection, isTestTarget, connectionTestDisplay, clearConnectionTest } = useSSHConnectionTest()
const sshKeys = ref<SSHKey[]>([])
const sshKeysLoading = ref(false)
const sshKeysLoaded = ref(false)
const search = ref('')
const opening = ref(false)
const saving = ref(false)
const localError = ref('')
const dialogError = ref('')
const formRoot = ref<HTMLElement | null>(null)
const formId = useId()
const dialog = ref(false)
const editing = ref<JumpHost | null>(null)
const authChanged = ref(false)
const invalidFields = ref<Set<keyof JumpHostForm>>(new Set())
const missingRequiredFields = ref(false)
function fieldMessage(field: keyof JumpHostForm): string {
  if (!invalidFields.value.has(field) || !dialogError.value) return ''
  if (missingRequiredFields.value) {
    return field === 'name' ? '请填写跳板机名称。' : field === 'address' ? '请填写地址。' : '请填写用户名。'
  }
  return dialogError.value
}
const form = ref<JumpHostForm>({ name: '', address: '', username: '', port: 22, auth_type: 'password', ssh_key_id: null, password: '', remark: '' })

watch(() => ({ ...form.value }), (next, previous) => {
  for (const key of Object.keys(next) as (keyof JumpHostForm)[]) {
    if (next[key] !== previous[key]) invalidFields.value.delete(key)
  }
  if (!invalidFields.value.size) dialogError.value = ''
}, { flush: 'sync' })
watch(() => form.value.auth_type, (next, previous) => {
  if (dialog.value && next !== previous) {
    invalidFields.value.delete('password')
    invalidFields.value.delete('ssh_key_id')
    if (!invalidFields.value.size) dialogError.value = ''
    authChanged.value = true
    form.value.password = ''
    form.value.ssh_key_id = null
  }
}, { flush: 'sync' })

let searchTimer: ReturnType<typeof setTimeout> | undefined
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
function refresh() {
  clearTimeout(searchTimer)
  clearConnectionTest()
  return load()
}

watch(search, () => {
  clearTimeout(searchTimer)
  invalidate()
  resetPage()
  searchTimer = setTimeout(refresh, search.value ? 250 : 0)
}, { flush: 'sync' })
onUnmounted(() => {
  clearTimeout(searchTimer)
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
  missingRequiredFields.value = false
  if (!value.name.trim() || !value.address.trim() || !value.username.trim()) {
    missingRequiredFields.value = true
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
  if (validation) { dialogError.value = validation; focusFormFeedback(formRoot.value); return }
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

function startJumpHostConnectionTest(item: JumpHost) {
  void testConnection({ target_type: 'jump_host', target_id: item.id, version: item.version, name: item.name })
}
</script>

<template>
    <main class="console-main">
      <section class="ui-panel" aria-label="跳板机列表">
        <div class="ui-toolbar"><ElButton type="primary" @click="openNew">新增跳板机</ElButton><div class="ui-toolbar-right"><ElInput v-model="search" clearable placeholder="搜索名称或地址" aria-label="搜索跳板机名称或地址" class="ui-search" /><ElButton :loading="loading" @click="refresh">刷新</ElButton></div></div>
        <ElAlert v-if="localError" :title="localError" type="error" :closable="false" show-icon class="ui-page-alert" />
        <div class="ui-table-wrap">
          <ElTable v-loading="loading || opening" :data="jumpHosts" row-key="id" class="ui-table" :empty-text="loadFailed ? '' : loading ? '加载中' : '暂无跳板机'">
            <ElTableColumn label="跳板机" min-width="200"><template #default="{ row }"><div class="ui-item-title">{{ row.name }}</div><div class="ui-item-secondary">{{ row.address }}</div></template></ElTableColumn>
            <ElTableColumn label="登录" min-width="150"><template #default="{ row }"><div>{{ row.username }} · {{ row.port }}</div><div class="ui-item-secondary">{{ row.auth_type === 'key' ? '密钥认证' : '密码认证' }}</div></template></ElTableColumn>
            <ElTableColumn prop="host_count" label="关联主机" width="100" />
            <ElTableColumn label="备注" min-width="180"><template #default="{ row }"><div class="ui-text-pre-wrap">{{ row.remark }}</div></template></ElTableColumn>
            <ElTableColumn label="更新时间" min-width="160"><template #default="{ row }">{{ dateLabel(row.updated_at) }}</template></ElTableColumn>
            <ElTableColumn label="本次测试" width="100" align="center">
              <template #default="{ row }">
                <TestStatus
                  :status="connectionTestDisplay(row as JumpHost).status"
                  :description="connectionTestDisplay(row as JumpHost).description"
                />
              </template>
            </ElTableColumn>
            <ElTableColumn label="操作" width="248" fixed="right">
              <template #default="{ row }">
                <ElButton
                  link type="primary"
                  :loading="testing && isTestTarget(row as JumpHost)"
                  :disabled="testing"
                  @click="startJumpHostConnectionTest(row as JumpHost)"
                >连接测试</ElButton>
                <ElButton link type="primary" @click="openEdit(row.id)">编辑</ElButton>
                <span class="wrapped-action" :title="row.host_count ? '请先解除关联主机' : undefined">
                  <ElButton link type="danger" :disabled="row.host_count > 0" @click="remove(row as JumpHost)">删除</ElButton>
                </span>
              </template>
            </ElTableColumn>
          </ElTable>
        </div>
        <ElEmpty v-if="!loading && !loadFailed && !jumpHosts.length" :description="search ? '暂无符合条件的跳板机' : '暂无跳板机，请新增跳板机'" class="ui-empty"><ElButton v-if="!search" type="primary" plain @click="openNew">新增跳板机</ElButton></ElEmpty>
        <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :total-known="!loading && !loadFailed" :disabled="loading || loadFailed" />
      </section>
    </main>

    <ElDialog v-model="dialog" align-center :title="editing ? '编辑跳板机' : '新增跳板机'" width="min(var(--ui-dialog-width), calc(100vw - 32px))" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
      <div ref="formRoot" class="ui-form">
        <ElAlert v-if="dialogError" :title="dialogError" type="error" :closable="false" show-icon data-form-error tabindex="-1" />
        <div class="form-section-title">基本信息</div>
        <div class="field-grid">
          <div class="field" :class="{ 'is-error': invalidFields.has('name') }"><label :for="`${formId}-name`">跳板机名称 <em>*</em></label><ElInput :id="`${formId}-name`" v-model="form.name" maxlength="100" :aria-invalid="invalidFields.has('name') ? 'true' : undefined" :aria-describedby="fieldMessage('name') ? `${formId}-name-error` : undefined" /><FieldError :id="`${formId}-name-error`" :message="fieldMessage('name')" /></div>
          <div class="field" :class="{ 'is-error': invalidFields.has('address') }"><label :for="`${formId}-address`">地址 <em>*</em></label><ElInput :id="`${formId}-address`" v-model="form.address" maxlength="253" placeholder="IP 或域名" :aria-invalid="invalidFields.has('address') ? 'true' : undefined" :aria-describedby="fieldMessage('address') ? `${formId}-address-error` : undefined" /><FieldError :id="`${formId}-address-error`" :message="fieldMessage('address')" /></div>
        </div>
        <div class="form-section-title">登录信息</div>
        <div class="field-grid">
          <div class="field" :class="{ 'is-error': invalidFields.has('username') }"><label :for="`${formId}-username`">用户名 <em>*</em></label><ElInput :id="`${formId}-username`" v-model="form.username" maxlength="100" autocomplete="off" :aria-invalid="invalidFields.has('username') ? 'true' : undefined" :aria-describedby="fieldMessage('username') ? `${formId}-username-error` : undefined" /><FieldError :id="`${formId}-username-error`" :message="fieldMessage('username')" /></div>
          <div class="field" :class="{ 'is-error': invalidFields.has('port') }"><label :for="`${formId}-port`">端口 <em>*</em></label><ElInputNumber :id="`${formId}-port`" v-model="form.port" v-native-field-aria :min="1" :max="65535" :controls="false" class="full-width" :aria-invalid="invalidFields.has('port') ? 'true' : undefined" :aria-describedby="fieldMessage('port') ? `${formId}-port-error` : undefined" /><FieldError :id="`${formId}-port-error`" :message="fieldMessage('port')" /></div>
        </div>
        <div class="field"><span>认证方式</span><ElRadioGroup v-model="form.auth_type" aria-label="跳板机认证方式"><ElRadioButton value="password">密码</ElRadioButton><ElRadioButton value="key">SSH 密钥</ElRadioButton></ElRadioGroup></div>
        <div v-if="form.auth_type === 'password'" class="field" :class="{ 'is-error': invalidFields.has('password') }"><label :for="`${formId}-password`">密码 <em v-if="!editing || editing.auth_type !== 'password' || !editing.has_password || authChanged || (form.address.trim() !== editing.address || form.username.trim() !== editing.username || form.port !== editing.port)">*</em></label><ElInput :id="`${formId}-password`" v-model="form.password" type="password" show-password autocomplete="new-password" :placeholder="editing?.auth_type === 'password' && editing.has_password && !authChanged ? '连接信息不变时留空保留原密码' : '请输入密码'" :aria-invalid="invalidFields.has('password') ? 'true' : undefined" :aria-describedby="fieldMessage('password') ? `${formId}-password-error` : undefined" /><FieldError :id="`${formId}-password-error`" :message="fieldMessage('password')" /></div>
        <template v-else><div class="field" :class="{ 'is-error': invalidFields.has('ssh_key_id') }"><label :for="`${formId}-key`">SSH 密钥 <em>*</em></label><ElSelect :id="`${formId}-key`" v-model="form.ssh_key_id" v-native-field-aria :disabled="sshKeysLoading || !sshKeysLoaded" :placeholder="sshKeysLoading ? '加载中' : '请选择密钥'" class="full-width" :aria-invalid="invalidFields.has('ssh_key_id') ? 'true' : undefined" :aria-describedby="fieldMessage('ssh_key_id') ? `${formId}-key-error` : undefined"><ElOption v-for="key in sshKeys" :key="key.id" :label="`${key.name} · ${key.key_type} · ${key.fingerprint}`" :value="key.id" /></ElSelect><FieldError :id="`${formId}-key-error`" :message="fieldMessage('ssh_key_id')" /></div><ElAlert v-if="editing?.auth_type === 'key' && editing.ssh_key_id === null && form.ssh_key_id === null" title="旧记录尚未关联密钥，请先导入并选择 SSH 密钥。" type="warning" :closable="false" show-icon /><RouterLink to="/assets/ssh-keys">管理 SSH 密钥</RouterLink></template>
        <label class="field"><span>备注</span><ElInput v-model="form.remark" type="textarea" :rows="3" maxlength="2000" placeholder="可选" /></label>
      </div>
      <template #footer><ElButton :disabled="saving" @click="dialog = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="save">保存</ElButton></template>
    </ElDialog>
</template>

<style scoped>
.wrapped-action { display: inline-block; margin-left: var(--ui-space-2); }
</style>
