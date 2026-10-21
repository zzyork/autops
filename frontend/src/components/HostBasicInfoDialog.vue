<script setup lang="ts">
import { computed, inject, onBeforeUnmount, ref, shallowRef, useId, watch } from 'vue'
import { ElAlert, ElButton, ElDialog, ElOption, ElSelect } from 'element-plus'
import { collectHostBasicInfo, saveHostBasicInfo } from '@/api/host_basic_info'
import { RequestCancelledError } from '@/api/http'
import { showRequestError } from '@/components/feedback'
import { vNativeFieldAria } from '@/components/formFeedback'
import { hostDisplayName } from '@/components/hostDisplay'
import { workspaceVisibleKey } from '@/components/workspace'
import type { Host } from '@/types/api'
import type { HostBasicInfo } from '@/types/hostBasicInfo'

const props = defineProps<{ modelValue: boolean; host: Host | null }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: [host: Host]
}>()
const visible = inject(workspaceVisibleKey, ref(true))
const fieldId = useId()
const collected = shallowRef<HostBasicInfo | null>(null)
const selectedIP = ref<string | null>(null)
const collecting = ref(false)
const collectFailed = ref(false)
const collectCancelled = ref(false)
const saving = ref(false)
const saveUnconfirmed = ref(false)
const addressOptions = computed(() => {
  const addresses = new Map<string, string[]>()
  for (const item of collected.value?.addresses ?? []) {
    const interfaces = addresses.get(item.address) ?? []
    if (!interfaces.includes(item.interface)) interfaces.push(item.interface)
    addresses.set(item.address, interfaces)
  }
  return [...addresses].map(([address, interfaces]) => ({ address, label: `${address}（${interfaces.join('、')}）` }))
})
const canSave = computed(() => !!collected.value && !!selectedIP.value
  && addressOptions.value.some((option) => option.address === selectedIP.value)
  && !collecting.value && !saving.value && visible.value)

let collectionSequence = 0
let writeSequence = 0
let controller: AbortController | null = null
let attempted = false
let mounted = true

function invalidateCollection() {
  collectionSequence++
  controller?.abort()
  controller = null
}

async function collect() {
  const host = props.host
  if (!mounted || !props.modelValue || !visible.value || !host || collecting.value || saving.value) return
  invalidateCollection()
  const current = collectionSequence
  const requestController = new AbortController()
  controller = requestController
  attempted = true
  collected.value = null
  selectedIP.value = null
  collecting.value = true
  collectFailed.value = false
  collectCancelled.value = false
  saveUnconfirmed.value = false
  const isCurrent = () => mounted && current === collectionSequence && props.modelValue
    && visible.value && props.host?.id === host.id && props.host?.version === host.version
  try {
    const result = await collectHostBasicInfo(host, { signal: requestController.signal, isCurrent })
    if (!isCurrent()) return
    collected.value = result
    const options = [...new Set(result.addresses.map((item) => item.address))]
    selectedIP.value = options.length === 1 ? options[0] ?? null : null
  } catch (error) {
    if (!isCurrent()) return
    if (error instanceof RequestCancelledError || requestController.signal.aborted) {
      collectCancelled.value = true
    } else {
      collectFailed.value = true
      showRequestError(error)
    }
  } finally {
    if (current === collectionSequence) collecting.value = false
    if (controller === requestController) controller = null
  }
}

watch(() => [props.modelValue, props.host?.id, props.host?.version] as const, () => {
  invalidateCollection()
  writeSequence++
  attempted = false
  collected.value = null
  selectedIP.value = null
  collecting.value = false
  collectFailed.value = false
  collectCancelled.value = false
  saveUnconfirmed.value = false
  saving.value = false
  if (props.modelValue && visible.value) void collect()
}, { immediate: true, flush: 'sync' })

watch(visible, (isVisible) => {
  if (!isVisible) {
    const wasCollecting = collecting.value
    invalidateCollection()
    collecting.value = false
    if (wasCollecting) collectCancelled.value = true
  } else if (props.modelValue && !attempted) {
    void collect()
  }
}, { flush: 'sync' })

onBeforeUnmount(() => {
  mounted = false
  writeSequence++
  invalidateCollection()
})

function updateVisible(value: boolean) {
  if (!value && saving.value) return
  emit('update:modelValue', value)
}

async function save() {
  const host = props.host
  const result = collected.value
  const ip = selectedIP.value
  if (!host || !result || !ip || !canSave.value || !props.modelValue) return
  const current = writeSequence
  saving.value = true
  saveUnconfirmed.value = false
  try {
    const updated = await saveHostBasicInfo(host.id, {
      version: result.version,
      name: result.name,
      lan_ip: ip,
    })
    if (!mounted || current !== writeSequence || !props.modelValue) return
    emit('update:modelValue', false)
    emit('saved', updated)
  } catch (error) {
    if (mounted && current === writeSequence && props.modelValue) {
      saveUnconfirmed.value = true
      if (visible.value) showRequestError(error)
    }
  } finally {
    if (mounted && current === writeSequence) saving.value = false
  }
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    align-center
    :title="`获取基础信息：${host ? hostDisplayName(host) : ''}`"
    width="min(var(--ui-dialog-width), calc(100vw - 32px))"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving"
    :show-close="!saving"
    @update:model-value="updateVisible"
  >
    <div class="ui-form host-basic-info">
      <p
        v-if="collecting"
        role="status"
        class="ui-execution-status ui-execution-notice"
        data-execution-state="in-progress"
      >正在获取主机基础信息，请稍候…</p>
      <p
        v-else-if="collectFailed"
        role="status"
        class="ui-execution-status ui-execution-notice"
        data-execution-state="incomplete"
      >获取失败，未获得采集结果。</p>
      <p v-else-if="collectCancelled" role="status">本地已取消等待采集结果，远端可能仍在处理。</p>
      <template v-if="collected && host">
        <dl class="host-basic-info-details">
          <dt>当前主机名</dt><dd>{{ host.name || '未填写' }}</dd>
          <dt>采集主机名</dt><dd>{{ collected.name }}</dd>
          <dt>当前局域网 IP</dt><dd>{{ host.lan_ip || '未填写' }}</dd>
        </dl>
        <div class="field">
          <label :id="`${fieldId}-ip-label`" :for="`${fieldId}-ip`">保存为局域网 IP <em>*</em></label>
          <ElSelect
            :id="`${fieldId}-ip`"
            v-model="selectedIP"
            v-native-field-aria
            :aria-labelledby="`${fieldId}-ip-label`"
            :aria-describedby="`${fieldId}-ip-hint`"
            :disabled="!addressOptions.length || saving"
            placeholder="请选择网卡 IP"
            class="full-width"
          >
            <ElOption
              v-for="option in addressOptions"
              :key="option.address"
              :value="option.address"
              :label="option.label"
            />
          </ElSelect>
          <span :id="`${fieldId}-ip-hint`" class="ui-field-hint">
            {{ addressOptions.length ? '按网卡选择要保存的地址。' : '未采集到可选 IP 地址，无法保存。' }}
          </span>
        </div>
        <ElAlert
          title="保存将覆盖此主机当前的主机名和局域网 IP；分组、VIP 与连接信息保持不变。"
          type="warning"
          :closable="false"
          show-icon
        />
        <ElAlert
          v-if="saveUnconfirmed"
          title="保存结果未确认，主机信息可能已变化。"
          type="warning"
          :closable="false"
          show-icon
        />
      </template>
      <ElButton v-if="collectFailed || collectCancelled" :disabled="saving || !visible" @click="collect">
        重新获取
      </ElButton>
    </div>
    <template #footer>
      <ElButton :disabled="saving" @click="updateVisible(false)">取消</ElButton>
      <ElButton type="primary" :loading="saving" :disabled="!canSave" @click="save">保存</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.host-basic-info p {
  margin: 0;
}
.host-basic-info-details {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: var(--ui-space-2);
  margin: 0;
}
.host-basic-info-details dt {
  color: var(--ui-text-secondary);
}
.host-basic-info-details dd {
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
