<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElDialog, ElInput, ElLoading, ElMessageBox, ElTable, ElTableColumn } from 'element-plus'
import { createGroup, deleteGroup, listGroups, updateGroup } from '@/api/assets'
import AssetsLayout from '@/components/AssetsLayout.vue'
import type { HostGroup } from '@/types/api'

const vLoading = ElLoading.directive
const groups = ref<HostGroup[]>([])
const loading = ref(false)
const error = ref('')
const dialog = ref(false)
const dialogError = ref('')
const saving = ref(false)
const editingGroup = ref<HostGroup | null>(null)
const form = ref({ name: '', remark: '' })
const nameError = ref(false)
watch(() => form.value.name, () => { nameError.value = false })

async function refreshGroups() {
  loading.value = true
  error.value = ''
  try {
    groups.value = await listGroups()
  } catch {
    error.value = '系统异常'
  } finally {
    loading.value = false
  }
}
onMounted(() => { void refreshGroups() })

function openGroup(group: HostGroup | null = null) {
  editingGroup.value = group
  form.value = { name: group?.name ?? '', remark: group?.remark ?? '' }
  nameError.value = false
  dialogError.value = ''
  dialog.value = true
}

async function saveGroup() {
  const body = { name: form.value.name.trim(), remark: form.value.remark.trim() }
  if (!body.name) { nameError.value = true; dialogError.value = '请输入分组名称。'; return }
  saving.value = true
  dialogError.value = ''
  try {
    if (editingGroup.value) await updateGroup(editingGroup.value.id, body)
    else await createGroup(body)
    dialog.value = false
    await refreshGroups()
  } catch {
    dialogError.value = '系统异常'
  } finally {
    saving.value = false
  }
}

async function removeGroup(group: HostGroup) {
  if (group.host_count > 0) { error.value = '请先移动或删除该分组内的主机。'; return }
  try {
    await ElMessageBox.confirm(`确定删除分组“${group.name}”吗？此操作不可撤销。`, '删除分组', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'delete-confirm-button',
    })
  } catch { return }
  error.value = ''
  try {
    await deleteGroup(group.id)
    await refreshGroups()
  } catch {
    error.value = '系统异常'
  }
}
</script>

<template>
  <AssetsLayout title="分组管理">
    <main class="assets-main">
      <div class="assets-heading"><h1>分组管理</h1></div>
      <section class="host-section" aria-label="分组列表">
        <div class="host-toolbar"><ElButton type="primary" @click="openGroup()">新增分组</ElButton><ElButton :loading="loading" @click="refreshGroups">刷新</ElButton></div>
        <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon class="assets-alert" />
        <div class="host-table-wrap">
          <ElTable v-loading="loading" :data="groups" row-key="id" class="host-table" :empty-text="error === '系统异常' ? '系统异常' : loading ? '加载中' : '暂无分组，请新增分组'">
            <ElTableColumn prop="name" label="分组名称" min-width="180"><template #default="{ row }"><div class="host-name">{{ row.name }}</div></template></ElTableColumn>
            <ElTableColumn prop="host_count" label="主机数量" width="120" />
            <ElTableColumn prop="remark" label="备注" min-width="260"><template #default="{ row }"><div class="group-remark">{{ row.remark }}</div></template></ElTableColumn>
            <ElTableColumn label="操作" width="128" fixed="right"><template #default="{ row }"><ElButton link type="primary" @click="openGroup(row as HostGroup)">编辑</ElButton><span :title="row.host_count ? '请先移动或删除组内主机' : undefined"><ElButton link type="danger" :disabled="row.host_count > 0" @click="removeGroup(row as HostGroup)">删除</ElButton></span></template></ElTableColumn>
          </ElTable>
        </div>
      </section>
    </main>
    <ElDialog v-model="dialog" align-center :title="editingGroup ? '编辑分组' : '新增分组'" width="min(440px, 92vw)" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
      <div class="asset-form"><label class="field" :class="{ 'is-error': nameError }"><span>分组名称 <em>*</em></span><ElInput v-model="form.name" maxlength="100" placeholder="输入分组名称" :aria-invalid="nameError ? 'true' : undefined" /></label><label class="field"><span>备注</span><ElInput v-model="form.remark" type="textarea" :rows="3" placeholder="可选" /></label><ElAlert v-if="dialogError" :title="dialogError" type="error" :closable="false" show-icon /></div>
      <template #footer><ElButton :disabled="saving" @click="dialog = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="saveGroup">保存</ElButton></template>
    </ElDialog>
  </AssetsLayout>
</template>
