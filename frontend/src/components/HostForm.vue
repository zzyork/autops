<script lang="ts">
import type { AuthType } from '@/types/api'

export interface HostFormData {
  name: string
  address: string
  lan_ip: string
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
</script>

<script setup lang="ts">
import { computed, useId } from 'vue'
import {
  ElAlert, ElInput, ElInputNumber, ElOption, ElRadioButton, ElRadioGroup, ElSelect,
} from 'element-plus'
import FieldError from '@/components/FieldError.vue'
import { vNativeFieldAria } from '@/components/formFeedback'
import type { Host, HostGroup, JumpHost, SSHKey } from '@/types/api'

const form = defineModel<HostFormData>({ required: true })
const props = defineProps<{
  groups: HostGroup[]
  jumpHosts: JumpHost[]
  jumpHostsLoading: boolean
  jumpHostsLoaded: boolean
  sshKeys: SSHKey[]
  sshKeysLoading: boolean
  sshKeysLoaded: boolean
  editingHost: Host | null
  authChanged: boolean
  errors: Partial<Record<keyof HostFormData, string>>
}>()
const formId = useId()
const retainPassword = computed(() => props.editingHost?.auth_type === 'password'
  && props.editingHost.has_password && !props.authChanged)

function fieldInvalid(field: keyof HostFormData): boolean {
  return field in props.errors
}
</script>

<template>
  <div class="form-section-title">连接信息</div>
  <div class="field-grid host-connection-grid">
    <div class="field" :class="{ 'is-error': fieldInvalid('address') }">
      <label :for="`${formId}-address`">地址 <em>*</em></label>
      <ElInput
        :id="`${formId}-address`"
        v-model="form.address"
        maxlength="253"
        placeholder="IPv4 或 IPv6 地址"
        :aria-invalid="fieldInvalid('address') ? 'true' : undefined"
        :aria-describedby="errors.address ? `${formId}-address-error` : undefined"
      />
      <FieldError :id="`${formId}-address-error`" :message="errors.address ?? ''" />
    </div>
    <div class="field" :class="{ 'is-error': fieldInvalid('username') }">
      <label :for="`${formId}-username`">用户名 <em>*</em></label>
      <ElInput
        :id="`${formId}-username`"
        v-model="form.username"
        maxlength="100"
        autocomplete="off"
        :aria-invalid="fieldInvalid('username') ? 'true' : undefined"
        :aria-describedby="errors.username ? `${formId}-username-error` : undefined"
      />
      <FieldError :id="`${formId}-username-error`" :message="errors.username ?? ''" />
    </div>
    <div class="field" :class="{ 'is-error': fieldInvalid('port') }">
      <label :for="`${formId}-port`">端口 <em>*</em></label>
      <ElInputNumber
        :id="`${formId}-port`"
        v-model="form.port"
        v-native-field-aria
        :min="1"
        :max="65535"
        :controls="false"
        class="full-width"
        :aria-invalid="fieldInvalid('port') ? 'true' : undefined"
        :aria-describedby="errors.port ? `${formId}-port-error` : undefined"
      />
      <FieldError :id="`${formId}-port-error`" :message="errors.port ?? ''" />
    </div>
  </div>
  <div class="field">
    <span :id="`${formId}-auth-label`">认证方式</span>
    <ElRadioGroup v-model="form.auth_type" :aria-labelledby="`${formId}-auth-label`">
      <ElRadioButton value="password">密码</ElRadioButton>
      <ElRadioButton value="key">SSH 密钥</ElRadioButton>
    </ElRadioGroup>
  </div>
  <div class="field-grid">
    <div
      v-if="form.auth_type === 'password'"
      class="field"
      :class="{ 'is-error': fieldInvalid('password') }"
    >
      <label :for="`${formId}-password`">密码 <em v-if="!retainPassword">*</em></label>
      <ElInput
        :id="`${formId}-password`"
        v-model="form.password"
        type="password"
        show-password
        autocomplete="new-password"
        :placeholder="retainPassword ? '留空保留原密码' : '请输入密码'"
        :aria-invalid="fieldInvalid('password') ? 'true' : undefined"
        :aria-describedby="errors.password ? `${formId}-password-error` : undefined"
      />
      <FieldError :id="`${formId}-password-error`" :message="errors.password ?? ''" />
    </div>
    <div v-else class="field" :class="{ 'is-error': fieldInvalid('ssh_key_id') }">
      <label :for="`${formId}-key`">SSH 密钥 <em>*</em></label>
      <ElSelect
        :id="`${formId}-key`"
        v-model="form.ssh_key_id"
        v-native-field-aria
        :disabled="sshKeysLoading || !sshKeysLoaded"
        :placeholder="sshKeysLoading ? '加载中' : '请选择密钥'"
        class="full-width"
        :aria-invalid="fieldInvalid('ssh_key_id') ? 'true' : undefined"
        :aria-describedby="errors.ssh_key_id ? `${formId}-key-error` : undefined"
      >
        <ElOption
          v-for="key in sshKeys"
          :key="key.id"
          :label="key.name"
          :value="key.id"
        />
      </ElSelect>
      <FieldError :id="`${formId}-key-error`" :message="errors.ssh_key_id ?? ''" />
      <ElAlert
        v-if="editingHost?.auth_type === 'key' && editingHost.ssh_key_id === null && form.ssh_key_id === null"
        title="旧记录尚未关联密钥，请先导入并选择 SSH 密钥。"
        type="warning"
        :closable="false"
        show-icon
      />
    </div>
    <div class="field" :class="{ 'is-error': fieldInvalid('jump_host_id') }">
      <label :for="`${formId}-jump`">关联跳板机</label>
      <ElSelect
        :id="`${formId}-jump`"
        v-model="form.jump_host_id"
        v-native-field-aria
        clearable
        :value-on-clear="null"
        :disabled="jumpHostsLoading || !jumpHostsLoaded"
        placeholder="不使用跳板机"
        class="full-width"
        :aria-invalid="fieldInvalid('jump_host_id') ? 'true' : undefined"
        :aria-describedby="errors.jump_host_id ? `${formId}-jump-error` : undefined"
      >
        <ElOption
          v-for="jumpHost in jumpHosts"
          :key="jumpHost.id"
          :label="`${jumpHost.name} · ${jumpHost.address}`"
          :value="jumpHost.id"
        />
      </ElSelect>
      <FieldError :id="`${formId}-jump-error`" :message="errors.jump_host_id ?? ''" />
    </div>
  </div>

  <div class="form-section-title">基本信息</div>
  <div class="field-grid">
    <div class="field" :class="{ 'is-error': fieldInvalid('name') }">
      <label :for="`${formId}-name`">主机名</label>
      <ElInput
        :id="`${formId}-name`"
        v-model="form.name"
        maxlength="100"
        placeholder="可选"
        :aria-invalid="fieldInvalid('name') ? 'true' : undefined"
        :aria-describedby="errors.name ? `${formId}-name-error` : undefined"
      />
      <FieldError :id="`${formId}-name-error`" :message="errors.name ?? ''" />
    </div>
    <div class="field" :class="{ 'is-error': fieldInvalid('lan_ip') }">
      <label :for="`${formId}-lan-ip`">局域网 IP</label>
      <ElInput
        :id="`${formId}-lan-ip`"
        v-model="form.lan_ip"
        maxlength="253"
        placeholder="可选"
        :aria-invalid="fieldInvalid('lan_ip') ? 'true' : undefined"
        :aria-describedby="errors.lan_ip ? `${formId}-lan-ip-error` : undefined"
      />
      <FieldError :id="`${formId}-lan-ip-error`" :message="errors.lan_ip ?? ''" />
    </div>
    <div class="field" :class="{ 'is-error': fieldInvalid('group_id') }">
      <label :for="`${formId}-group`">分组 <em>*</em></label>
      <ElSelect
        :id="`${formId}-group`"
        v-model="form.group_id"
        v-native-field-aria
        placeholder="请选择分组"
        class="full-width"
        :aria-invalid="fieldInvalid('group_id') ? 'true' : undefined"
        :aria-describedby="errors.group_id ? `${formId}-group-error` : undefined"
      >
        <ElOption v-for="group in groups" :key="group.id" :label="group.name" :value="group.id" />
      </ElSelect>
      <FieldError :id="`${formId}-group-error`" :message="errors.group_id ?? ''" />
    </div>
    <div class="field">
      <label :for="`${formId}-vip`">虚拟 IP（VIP）</label>
      <ElInput :id="`${formId}-vip`" v-model="form.vip" maxlength="253" placeholder="可选" />
    </div>
  </div>

  <div :id="`${formId}-remark-label`" class="form-section-title">备注</div>
  <ElInput
    v-model="form.remark"
    type="textarea"
    :rows="3"
    maxlength="2000"
    placeholder="可选"
    :aria-labelledby="`${formId}-remark-label`"
  />
</template>
