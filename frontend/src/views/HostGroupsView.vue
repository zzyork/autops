<script setup lang="ts">
import { ref, useId, watch } from 'vue'
import { ElAlert, ElButton, ElDialog, ElInput, ElLoading, ElMessageBox, ElTable, ElTableColumn } from 'element-plus'
import { createGroup, deleteGroup, listGroupsPage, updateGroup } from '@/api/assets'
import ListPagination from '@/components/ListPagination.vue'
import FieldError from '@/components/FieldError.vue'
import { focusFormFeedback } from '@/components/formFeedback'
import { useServerPagination } from '@/components/serverPagination'
import { showSystemError } from '@/components/feedback'
import type { HostGroup } from '@/types/api'
import '@/styles/assets.css'

const vLoading = ElLoading.directive
const { items: groups, page, pageSize, total, loading, loadFailed, refresh: loadGroups } =
  useServerPagination<HostGroup>(listGroupsPage)
const localError = ref('')
const dialog = ref(false)
const dialogError = ref('')
const formRoot = ref<HTMLElement | null>(null)
const formId = useId()
const saving = ref(false)
const editingGroup = ref<HostGroup | null>(null)
const form = ref({ name: '', remark: '' })
const nameError = ref(false)
watch(() => form.value.name, () => { nameError.value = false; dialogError.value = '' })

function refreshGroups() {
  localError.value = ''
  return loadGroups()
}

function openGroup(group: HostGroup | null = null) {
  editingGroup.value = group
  form.value = { name: group?.name ?? '', remark: group?.remark ?? '' }
  nameError.value = false
  dialogError.value = ''
  dialog.value = true
}

async function saveGroup() {
  const body = { name: form.value.name.trim(), remark: form.value.remark.trim() }
  if (!body.name) { nameError.value = true; dialogError.value = '请输入分组名称。'; focusFormFeedback(formRoot.value); return }
  saving.value = true
  dialogError.value = ''
  try {
    if (editingGroup.value) await updateGroup(editingGroup.value.id, body)
    else await createGroup(body)
    dialog.value = false
    await refreshGroups()
  } catch {
    showSystemError()
  } finally {
    saving.value = false
  }
}

async function removeGroup(group: HostGroup) {
  if (group.host_count > 0) { localError.value = '请先移动或删除该分组内的主机。'; return }
  try {
    await ElMessageBox.confirm(`确定删除分组“${group.name}”吗？此操作不可撤销。`, '删除分组', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'delete-confirm-button',
    })
  } catch { return }
  localError.value = ''
  try {
    await deleteGroup(group.id)
    await refreshGroups()
  } catch {
    showSystemError()
  }
}
</script>

<template>
    <main class="console-main">
      <section class="ui-panel" aria-label="分组列表">
        <div class="ui-toolbar"><ElButton type="primary" @click="openGroup()">新增分组</ElButton><ElButton :loading="loading" @click="refreshGroups">刷新</ElButton></div>
        <ElAlert v-if="localError" :title="localError" type="error" :closable="false" show-icon class="ui-page-alert" />
        <div class="ui-table-wrap">
          <ElTable v-loading="loading" :data="groups" row-key="id" class="ui-table" :empty-text="loadFailed ? '' : loading ? '加载中' : '暂无分组，请新增分组'">
            <ElTableColumn prop="name" label="分组名称" min-width="180"><template #default="{ row }"><div class="ui-item-title">{{ row.name }}</div></template></ElTableColumn>
            <ElTableColumn prop="host_count" label="主机数量" width="120" />
            <ElTableColumn prop="remark" label="备注" min-width="260"><template #default="{ row }"><div class="ui-text-pre-wrap">{{ row.remark }}</div></template></ElTableColumn>
            <ElTableColumn label="操作" width="144" fixed="right"><template #default="{ row }"><ElButton link type="primary" @click="openGroup(row as HostGroup)">编辑</ElButton><span class="wrapped-action" :title="row.host_count ? '请先移动或删除组内主机' : undefined"><ElButton link type="danger" :disabled="row.host_count > 0" @click="removeGroup(row as HostGroup)">删除</ElButton></span></template></ElTableColumn>
          </ElTable>
        </div>
        <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :total-known="!loading && !loadFailed" :disabled="loading || loadFailed" />
      </section>
    </main>
    <ElDialog v-model="dialog" align-center :title="editingGroup ? '编辑分组' : '新增分组'" width="min(var(--ui-confirm-width), calc(100vw - 32px))" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
      <div ref="formRoot" class="ui-form"><ElAlert v-if="dialogError" :title="dialogError" type="error" :closable="false" show-icon data-form-error tabindex="-1" /><div class="field" :class="{ 'is-error': nameError }"><label :for="`${formId}-name`">分组名称 <em>*</em></label><ElInput :id="`${formId}-name`" v-model="form.name" maxlength="100" placeholder="输入分组名称" :aria-invalid="nameError ? 'true' : undefined" :aria-describedby="nameError ? `${formId}-name-error` : undefined" /><FieldError :id="`${formId}-name-error`" :message="nameError ? dialogError : ''" /></div><label class="field"><span>备注</span><ElInput v-model="form.remark" type="textarea" :rows="3" placeholder="可选" /></label></div>
      <template #footer><ElButton :disabled="saving" @click="dialog = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="saveGroup">保存</ElButton></template>
    </ElDialog>
</template>

<style scoped>
.wrapped-action { display: inline-block; margin-left: var(--ui-space-2); }
</style>
