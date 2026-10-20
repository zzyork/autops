<script setup lang="ts">
import { onUnmounted, ref, useId, watch } from "vue";
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElEmpty,
  ElInput,
  ElLoading,
  ElMessageBox,
  ElRadioButton,
  ElRadioGroup,
  ElSwitch,
  ElTable,
  ElTableColumn,
} from "element-plus";
import {
  createSSHKey,
  deleteSSHKey,
  getSSHKey,
  getSSHKeyReferences,
  listSSHKeysPage,
  updateSSHKey,
} from "@/api/ssh_keys";
import { showSystemError } from "@/components/feedback";
import FieldError from "@/components/FieldError.vue";
import { focusFormFeedback } from "@/components/formFeedback";
import ListPagination from "@/components/ListPagination.vue";
import { useServerPagination } from "@/components/serverPagination";
import type { SSHKey, SSHKeySummary, SSHKeyReferences, SSHKeyUpdateInput } from "@/types/api";
import "@/styles/assets.css";

const vLoading = ElLoading.directive;
const { items: keys, page, pageSize, total, loading, loadFailed, refresh: load, resetPage, invalidate } =
  useServerPagination<SSHKeySummary>((currentPage, size) => listSSHKeysPage(search.value.trim(), currentPage, size));
const search = ref("");
const opening = ref(false);
const saving = ref(false);
const dialog = ref(false);
const dialogError = ref("");
const formRoot = ref<HTMLElement | null>(null);
const formId = useId();
const editing = ref<SSHKey | null>(null);
const form = ref({ name: "", remark: "", private_key: "", public_key: "" });
const invalid = ref(false);
const privateInvalid = ref(false);
const inputMode = ref<"file" | "text">("file");
const replaceKey = ref(false);
const fileName = ref("");
const fileError = ref("");
const reading = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
const uploadPublicKey = ref(false);
const publicInputMode = ref<"file" | "text">("file");
const publicInvalid = ref(false);
const publicFileName = ref("");
const publicFileError = ref("");
const publicReading = ref(false);
const publicFileInput = ref<HTMLInputElement | null>(null);
const publicDialog = ref(false);
const publicKey = ref<string | null>(null);
const publicName = ref("");
const publicKeyId = ref<number | null>(null);
const publicLoading = ref(false);
const publicLoadFailed = ref(false);
const referencesDialog = ref(false);
const references = ref<SSHKeyReferences | null>(null);
const referencesName = ref("");
const referencesLoading = ref(false);

let searchTimer: ReturnType<typeof setTimeout> | undefined;
let readId = 0;
let publicReadId = 0;
let publicViewId = 0;
let referenceId = 0;
let editId = 0;

function refresh() {
  clearTimeout(searchTimer);
  return load();
}

watch(search, () => {
  clearTimeout(searchTimer);
  invalidate();
  resetPage();
  searchTimer = setTimeout(refresh, search.value ? 250 : 0);
}, { flush: "sync" });
watch(
  () => form.value.name,
  () => {
    if (invalid.value) dialogError.value = "";
    invalid.value = false;
  },
);

function clearPrivateKey(resetFileInput = true) {
  if (privateInvalid.value && !invalid.value && !publicInvalid.value) dialogError.value = "";
  readId++;
  reading.value = false;
  form.value.private_key = "";
  fileName.value = "";
  fileError.value = "";
  privateInvalid.value = false;
  if (resetFileInput && fileInput.value) fileInput.value.value = "";
}

function clearPublicKey(resetFileInput = true) {
  if (publicInvalid.value && !invalid.value && !privateInvalid.value) dialogError.value = "";
  publicReadId++;
  publicReading.value = false;
  form.value.public_key = "";
  publicFileName.value = "";
  publicFileError.value = "";
  publicInvalid.value = false;
  if (resetFileInput && publicFileInput.value) publicFileInput.value.value = "";
}

watch(inputMode, () => clearPrivateKey(), { flush: "sync" });
watch(replaceKey, () => clearPrivateKey(), { flush: "sync" });
watch(
  replaceKey,
  (enabled) => {
    if (enabled) uploadPublicKey.value = true;
  },
  { flush: "sync" },
);
watch(publicInputMode, () => clearPublicKey(), { flush: "sync" });
watch(
  uploadPublicKey,
  (enabled) => {
    if (!enabled) clearPublicKey();
  },
  { flush: "sync" },
);
watch(
  () => form.value.private_key,
  () => {
    if (privateInvalid.value && !invalid.value && !publicInvalid.value) dialogError.value = "";
    privateInvalid.value = false;
  },
  { flush: "sync" },
);
watch(
  () => form.value.public_key,
  () => {
    if (publicInvalid.value && !invalid.value && !privateInvalid.value) dialogError.value = "";
    publicInvalid.value = false;
  },
  { flush: "sync" },
);
watch(
  dialog,
  (visible) => {
    if (!visible) {
      editId++;
      clearPrivateKey();
      clearPublicKey();
    }
  },
  { flush: "sync" },
);
watch(
  publicDialog,
  (visible) => {
    if (!visible) {
      publicViewId++;
      publicKey.value = null;
      publicKeyId.value = null;
      publicName.value = "";
      publicLoadFailed.value = false;
      publicLoading.value = false;
    }
  },
  { flush: "sync" },
);
watch(referencesDialog, (visible) => {
  if (!visible) {
    referenceId++;
    references.value = null;
  }
});
onUnmounted(() => {
  clearTimeout(searchTimer);
  clearPrivateKey();
  clearPublicKey();
  publicViewId++;
  referenceId++;
  editId++;
});

function openNew() {
  editId++;
  opening.value = false;
  editing.value = null;
  form.value = { name: "", remark: "", private_key: "", public_key: "" };
  inputMode.value = "file";
  replaceKey.value = false;
  publicInputMode.value = "file";
  uploadPublicKey.value = true;
  invalid.value = false;
  dialogError.value = "";
  clearPrivateKey();
  clearPublicKey();
  dialog.value = true;
}

async function openEdit(id: number) {
  const current = ++editId;
  opening.value = true;
  try {
    const item = await getSSHKey(id);
    if (current !== editId) return;
    editing.value = item;
    form.value = {
      name: item.name,
      remark: item.remark,
      private_key: "",
      public_key: "",
    };
    inputMode.value = "file";
    replaceKey.value = false;
    publicInputMode.value = "file";
    uploadPublicKey.value = false;
    invalid.value = false;
    dialogError.value = "";
    clearPrivateKey();
    clearPublicKey();
    dialog.value = true;
  } catch {
    if (current === editId) showSystemError();
  } finally {
    if (current === editId) opening.value = false;
  }
}

async function selectFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  clearPrivateKey(false);
  if (file.size > 64 * 1024) {
    input.value = "";
    fileError.value = "私钥文件不能超过 64 KiB。";
    privateInvalid.value = true;
    return;
  }
  const current = ++readId;
  reading.value = true;
  try {
    const bytes = await file.arrayBuffer();
    if (current !== readId || !dialog.value || inputMode.value !== "file")
      return;
    const content = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    if (!content.trim()) {
      fileError.value = "私钥文件不能为空。";
      privateInvalid.value = true;
      return;
    }
    form.value.private_key = content;
    fileName.value = file.name;
  } catch {
    if (current === readId && dialog.value && inputMode.value === "file") {
      fileError.value = "文件读取失败或不是有效的 UTF-8 文本。";
      privateInvalid.value = true;
    }
  } finally {
    if (current === readId) {
      reading.value = false;
      if (!fileName.value) input.value = "";
    }
  }
}

async function selectPublicFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  clearPublicKey(false);
  if (file.size > 64 * 1024) {
    input.value = "";
    publicFileError.value = "公钥文件不能超过 64 KiB。";
    publicInvalid.value = true;
    return;
  }
  const current = ++publicReadId;
  publicReading.value = true;
  try {
    const bytes = await file.arrayBuffer();
    if (
      current !== publicReadId ||
      !dialog.value ||
      publicInputMode.value !== "file" ||
      !uploadPublicKey.value
    )
      return;
    const content = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    if (!content.trim()) {
      publicFileError.value = "公钥文件不能为空。";
      publicInvalid.value = true;
      return;
    }
    form.value.public_key = content;
    publicFileName.value = file.name;
  } catch {
    if (
      current === publicReadId &&
      dialog.value &&
      publicInputMode.value === "file" &&
      uploadPublicKey.value
    ) {
      publicFileError.value = "文件读取失败或不是有效的 UTF-8 文本。";
      publicInvalid.value = true;
    }
  } finally {
    if (current === publicReadId) {
      publicReading.value = false;
      if (!publicFileName.value) input.value = "";
    }
  }
}

async function save() {
  if (saving.value || reading.value || publicReading.value) return;
  invalid.value = false;
  privateInvalid.value = false;
  publicInvalid.value = false;
  dialogError.value = "";
  const name = form.value.name.trim();
  if (!name) {
    invalid.value = true;
    dialogError.value = "请输入密钥名称。";
    focusFormFeedback(formRoot.value);
    return;
  }
  const previous = editing.value;
  const replacing = !previous || replaceKey.value;
  const privateKey = form.value.private_key;
  const publicKeyContent = form.value.public_key;
  if (replacing) {
    if (!privateKey.trim() || (inputMode.value === "file" && !fileName.value)) {
      privateInvalid.value = true;
      dialogError.value = fileError.value || "请选择私钥文件或粘贴私钥内容。";
      focusFormFeedback(formRoot.value);
      return;
    }
    if (new TextEncoder().encode(privateKey).byteLength > 64 * 1024) {
      privateInvalid.value = true;
      dialogError.value = "私钥内容不能超过 64 KiB。";
      focusFormFeedback(formRoot.value);
      return;
    }
  }
  if (replacing || uploadPublicKey.value) {
    if (
      !publicKeyContent.trim() ||
      (publicInputMode.value === "file" && !publicFileName.value)
    ) {
      publicInvalid.value = true;
      dialogError.value =
        publicFileError.value || "请选择公钥文件或粘贴公钥内容。";
      focusFormFeedback(formRoot.value);
      return;
    }
    if (new TextEncoder().encode(publicKeyContent).byteLength > 64 * 1024) {
      publicInvalid.value = true;
      dialogError.value = "公钥内容不能超过 64 KiB。";
      focusFormFeedback(formRoot.value);
      return;
    }
  }
  saving.value = true;
  dialogError.value = "";
  try {
    if (previous && replaceKey.value) {
      try {
        await ElMessageBox.confirm(
          `替换“${previous.name}”的私钥将影响 ${previous.host_count} 台主机和 ${previous.jump_host_count} 台跳板机的认证。确定继续吗？`,
          "替换私钥",
          {
            confirmButtonText: "确认替换",
            cancelButtonText: "取消",
            type: "warning",
          },
        );
      } catch {
        return;
      }
    }
    if (previous) {
      const body: SSHKeyUpdateInput = {
        name,
        remark: form.value.remark.trim(),
        version: previous.version,
      };
      if (replaceKey.value) body.private_key = privateKey;
      if (uploadPublicKey.value) body.public_key = publicKeyContent;
      await updateSSHKey(previous.id, body);
    } else {
      await createSSHKey({
        name,
        remark: form.value.remark.trim(),
        private_key: privateKey,
        public_key: publicKeyContent,
      });
    }
    dialog.value = false;
    await refresh();
  } catch {
    showSystemError();
  } finally {
    saving.value = false;
  }
}

async function showPublicKey(item: SSHKeySummary) {
  const current = ++publicViewId;
  publicName.value = item.name;
  publicKeyId.value = item.id;
  publicKey.value = null;
  publicLoadFailed.value = false;
  publicLoading.value = true;
  publicDialog.value = true;
  try {
    const detail = await getSSHKey(item.id);
    if (current === publicViewId) publicKey.value = detail.public_key;
  } catch {
    if (current === publicViewId) {
      publicLoadFailed.value = true;
      showSystemError();
    }
  } finally {
    if (current === publicViewId) publicLoading.value = false;
  }
}

function editMissingPublicKey() {
  const id = publicKeyId.value;
  if (id === null) return;
  publicDialog.value = false;
  void openEdit(id);
}

async function showReferences(item: SSHKeySummary) {
  const current = ++referenceId;
  referencesName.value = item.name;
  references.value = null;
  referencesLoading.value = true;
  referencesDialog.value = true;
  try {
    const result = await getSSHKeyReferences(item.id);
    if (current === referenceId) references.value = result;
  } catch {
    if (current === referenceId) showSystemError();
  } finally {
    if (current === referenceId) referencesLoading.value = false;
  }
}

async function remove(item: SSHKeySummary) {
  if (item.host_count || item.jump_host_count) return;
  try {
    await ElMessageBox.confirm(
      `确定删除 SSH 密钥“${item.name}”吗？此操作不可撤销。`,
      "删除 SSH 密钥",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
        confirmButtonClass: "delete-confirm-button",
      },
    );
  } catch {
    return;
  }
  try {
    await deleteSSHKey(item.id);
    await refresh();
  } catch {
    showSystemError();
  }
}

function dateLabel(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
</script>

<template>
    <main class="console-main">
      <section class="ui-panel" aria-label="SSH 密钥列表">
        <div class="ui-toolbar">
          <ElButton type="primary" @click="openNew">新增密钥</ElButton>
          <div class="ui-toolbar-right">
            <ElInput
              v-model="search"
              clearable
              placeholder="搜索密钥名称"
              aria-label="搜索密钥名称"
              class="ui-search"
            /><ElButton :loading="loading" @click="refresh">刷新</ElButton>
          </div>
        </div>
        <div class="ui-table-wrap">
          <ElTable
            v-loading="loading || opening"
            :data="keys"
            row-key="id"
            class="ui-table"
            :empty-text="loadFailed ? '' : loading ? '加载中' : '暂无 SSH 密钥'"
          >
            <ElTableColumn label="密钥名称" min-width="170"
              ><template #default="{ row }"
                ><div class="ui-item-title">{{ row.name }}</div></template
              ></ElTableColumn
            >
            <ElTableColumn prop="key_type" label="类型" min-width="100" />
            <ElTableColumn label="指纹" min-width="270"
              ><template #default="{ row }"
                ><span class="ssh-fingerprint">{{
                  row.fingerprint
                }}</span></template
              ></ElTableColumn
            >
            <ElTableColumn label="关联" width="170"
              ><template #default="{ row }"
                ><ElButton
                  link
                  type="primary"
                   @click="showReferences(row as SSHKeySummary)"
                  >{{ row.host_count }} 主机 /
                  {{ row.jump_host_count }} 跳板机</ElButton
                ></template
              ></ElTableColumn
            >
            <ElTableColumn label="备注" min-width="160"
              ><template #default="{ row }"
                ><div class="ui-text-pre-wrap">{{ row.remark }}</div></template
              ></ElTableColumn
            >
            <ElTableColumn label="更新时间" min-width="160"
              ><template #default="{ row }">{{
                dateLabel(row.updated_at)
              }}</template></ElTableColumn
            >
            <ElTableColumn label="操作" width="252" fixed="right"
              ><template #default="{ row }"
                ><ElButton
                  link
                  type="primary"
                  :disabled="opening"
                   @click="showPublicKey(row as SSHKeySummary)"
                  >查看公钥</ElButton
                ><ElButton
                  link
                  type="primary"
                  :disabled="opening"
                  @click="openEdit(row.id)"
                  >编辑</ElButton
                ><span class="wrapped-action"
                  :title="
                    row.host_count || row.jump_host_count
                      ? '请先解除主机和跳板机的关联'
                      : undefined
                  "
                  ><ElButton
                    link
                    type="danger"
                    :disabled="
                      opening || row.host_count > 0 || row.jump_host_count > 0
                    "
                     @click="remove(row as SSHKeySummary)"
                    >删除</ElButton
                  ></span
                ></template
              ></ElTableColumn
            >
          </ElTable>
        </div>
        <ElEmpty
          v-if="!loading && !loadFailed && !keys.length"
          :description="
            search ? '暂无符合条件的密钥' : '暂无 SSH 密钥，请新增密钥'
          "
          class="ui-empty"
          ><ElButton v-if="!search" type="primary" plain @click="openNew"
            >新增密钥</ElButton
          ></ElEmpty
        >
        <ListPagination v-model:page="page" v-model:page-size="pageSize" :total="total" :total-known="!loading && !loadFailed" :disabled="loading || loadFailed" />
      </section>
    </main>

    <ElDialog
      v-model="dialog"
      align-center
      :title="editing ? '编辑 SSH 密钥' : '新增 SSH 密钥'"
      width="min(var(--ui-dialog-width), calc(100vw - 32px))"
      :close-on-click-modal="false"
      :close-on-press-escape="!saving"
      :show-close="!saving"
    >
      <div ref="formRoot" class="ui-form">
        <ElAlert v-if="dialogError" :title="dialogError" type="error" :closable="false" show-icon data-form-error tabindex="-1" />
        <div class="field" :class="{ 'is-error': invalid }"
          ><label :for="`${formId}-name`">密钥名称 <em>*</em></label
          ><ElInput
            :id="`${formId}-name`"
            v-model="form.name"
            maxlength="100"
            :disabled="saving || reading || publicReading"
            :aria-invalid="invalid ? 'true' : undefined"
            :aria-describedby="invalid ? `${formId}-name-error` : undefined"
        /><FieldError :id="`${formId}-name-error`" :message="invalid ? dialogError : ''" /></div>
        <label class="field"
          ><span>备注</span
          ><ElInput
            v-model="form.remark"
            type="textarea"
            :rows="2"
            maxlength="2000"
            :disabled="saving || reading || publicReading"
            placeholder="可选"
        /></label>
        <template v-if="editing"
          ><div class="ssh-key-detail">
            <div>类型：{{ editing.key_type }}</div>
            <div class="ssh-fingerprint">指纹：{{ editing.fingerprint }}</div>
            <div>
              关联：{{ editing.host_count }} 台主机 /
              {{ editing.jump_host_count }} 台跳板机
            </div>
            <div>
              公钥：{{ editing.public_key === null ? "尚未上传" : "已上传" }}
            </div>
          </div>
          <label class="ssh-replace"
            ><span>替换私钥</span
            ><ElSwitch
              v-model="replaceKey"
              :disabled="saving || reading || publicReading"
              aria-label="替换私钥" /></label
          ><label class="ssh-replace"
            ><span>上传/替换公钥</span
            ><ElSwitch
              v-model="uploadPublicKey"
              :disabled="saving || reading || publicReading || replaceKey"
              aria-label="上传/替换公钥" /></label
        ></template>
        <template v-if="!editing || replaceKey">
          <ElAlert
            v-if="editing"
            :title="`替换后将影响 ${editing.host_count} 台主机和 ${editing.jump_host_count} 台跳板机的认证。`"
            type="warning"
            :closable="false"
            show-icon
          />
          <div class="field">
            <span>私钥来源 <em>*</em></span
            ><ElRadioGroup
              v-model="inputMode"
              :disabled="saving || reading || publicReading"
              aria-label="私钥来源"
              ><ElRadioButton value="file">上传文件</ElRadioButton
              ><ElRadioButton value="text"
                >粘贴内容</ElRadioButton
              ></ElRadioGroup
            >
          </div>
          <div
            v-if="inputMode === 'file'"
            class="field"
            :class="{ 'is-error': privateInvalid }"
          >
            <label :for="`${formId}-private-file`">私钥文件 <em>*</em></label
            ><input
              :id="`${formId}-private-file`"
              ref="fileInput"
              type="file"
              class="ssh-file-input"
              :disabled="saving || reading || publicReading"
              :aria-invalid="privateInvalid ? 'true' : undefined"
              :aria-describedby="privateInvalid ? `${formId}-private-error` : undefined"
              @change="selectFile"
            /><span v-if="reading" class="ui-field-hint">读取中...</span
            ><FieldError :id="`${formId}-private-error`" :message="privateInvalid ? fileError || dialogError : ''" />
          </div>
          <div v-else class="field" :class="{ 'is-error': privateInvalid }"
            ><label :for="`${formId}-private-text`">私钥内容 <em>*</em></label
            ><ElInput
              :id="`${formId}-private-text`"
              v-model="form.private_key"
              type="textarea"
              :rows="7"
              :disabled="saving || reading || publicReading"
              autocomplete="off"
              :aria-invalid="privateInvalid ? 'true' : undefined"
              :aria-describedby="privateInvalid ? `${formId}-private-error` : undefined"
              placeholder="粘贴 OpenSSH 或 PEM 私钥"
          /><FieldError :id="`${formId}-private-error`" :message="privateInvalid ? dialogError : ''" /></div>
          <div class="ui-field-hint">
            仅支持无口令的 OpenSSH / PEM 私钥，最大 64 KiB。
          </div>
        </template>
        <template v-if="uploadPublicKey">
          <div class="field">
            <span>公钥来源 <em>*</em></span
            ><ElRadioGroup
              v-model="publicInputMode"
              :disabled="saving || reading || publicReading"
              aria-label="公钥来源"
              ><ElRadioButton value="file">上传文件</ElRadioButton
              ><ElRadioButton value="text"
                >粘贴内容</ElRadioButton
              ></ElRadioGroup
            >
          </div>
          <div
            v-if="publicInputMode === 'file'"
            class="field"
            :class="{ 'is-error': publicInvalid }"
          >
            <label :for="`${formId}-public-file`">公钥文件 <em>*</em></label
            ><input
              :id="`${formId}-public-file`"
              ref="publicFileInput"
              type="file"
              class="ssh-file-input"
              :disabled="saving || reading || publicReading"
              :aria-invalid="publicInvalid ? 'true' : undefined"
              :aria-describedby="publicInvalid ? `${formId}-public-error` : undefined"
              @change="selectPublicFile"
            /><span v-if="publicReading" class="ui-field-hint">读取中...</span
            ><FieldError :id="`${formId}-public-error`" :message="publicInvalid ? publicFileError || dialogError : ''" />
          </div>
          <div v-else class="field" :class="{ 'is-error': publicInvalid }"
            ><label :for="`${formId}-public-text`">公钥内容 <em>*</em></label
            ><ElInput
              :id="`${formId}-public-text`"
              v-model="form.public_key"
              type="textarea"
              :rows="5"
              :disabled="saving || reading || publicReading"
              :aria-invalid="publicInvalid ? 'true' : undefined"
              :aria-describedby="publicInvalid ? `${formId}-public-error` : undefined"
              placeholder="粘贴 OpenSSH .pub 或 PEM 公钥"
          /><FieldError :id="`${formId}-public-error`" :message="publicInvalid ? dialogError : ''" /></div>
          <div class="ui-field-hint">
            支持 OpenSSH .pub 文本或 PEM 公钥，最大 64
            KiB。保存时校验公私钥匹配。
          </div>
        </template>
      </div>
      <template #footer
        ><ElButton
          :disabled="saving || reading || publicReading"
          @click="dialog = false"
          >取消</ElButton
        ><ElButton
          type="primary"
          :loading="saving"
          :disabled="reading || publicReading"
          @click="save"
          >保存</ElButton
        ></template
      >
    </ElDialog>

    <ElDialog
      v-model="publicDialog"
      align-center
      :title="`公钥：${publicName}`"
      width="min(var(--ui-dialog-width), calc(100vw - 32px))"
    >
      <div v-loading="publicLoading" class="ssh-public-view">
        <template v-if="!publicLoading && !publicLoadFailed">
          <ElInput
            v-if="publicKey !== null"
            :model-value="publicKey"
            type="textarea"
            :rows="10"
            readonly
            aria-label="公钥内容"
          />
          <div v-else class="ui-field-hint">
            尚未上传公钥，请编辑密钥补传。
          </div>
        </template>
      </div>
      <template #footer
        ><ElButton
          v-if="!publicLoading && !publicLoadFailed && publicKey === null"
          type="primary"
          @click="editMissingPublicKey"
          >编辑补传</ElButton
        ><ElButton @click="publicDialog = false">关闭</ElButton></template
      >
    </ElDialog>

    <ElDialog
      v-model="referencesDialog"
      align-center
      :title="`密钥引用：${referencesName}`"
      width="min(var(--ui-confirm-width), calc(100vw - 32px))"
    >
      <div v-loading="referencesLoading" class="ssh-references">
        <template v-if="references"
          ><h2>主机</h2>
          <div v-if="!references.hosts.length" class="ui-field-hint">
            无关联主机
          </div>
          <RouterLink
            v-for="host in references.hosts"
            :key="host.id"
            to="/assets/hosts"
            class="ssh-reference-link"
            @click="referencesDialog = false"
            >{{ host.name }}</RouterLink
          >
          <h2>跳板机</h2>
          <div v-if="!references.jump_hosts.length" class="ui-field-hint">
            无关联跳板机
          </div>
          <RouterLink
            v-for="jumpHost in references.jump_hosts"
            :key="jumpHost.id"
            to="/assets/jump-hosts"
            class="ssh-reference-link"
            @click="referencesDialog = false"
            >{{ jumpHost.name }}</RouterLink
          ></template
        >
      </div>
      <template #footer
        ><ElButton @click="referencesDialog = false">关闭</ElButton></template
      >
    </ElDialog>
</template>

<style scoped>
.wrapped-action { display: inline-block; margin-left: var(--ui-space-2); }
.ssh-public-view {
  min-height: 90px;
}
</style>
