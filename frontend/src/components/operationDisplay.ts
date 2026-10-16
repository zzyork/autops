import type { OperationHostStatus, OperationStepStatus, OperationTaskStatus, OperationModuleId, OperationAction } from '@/types/operations'

export const operationInspectLabels: Record<OperationModuleId, string> = {
  hostname: '查看当前主机名', packages: '查看软件仓库', firewall: '查看防火墙状态',
  kernel: '查看内核参数与资源限制', system: '查看系统配置', disk: '查看磁盘',
}

export const operationImpacts: Record<OperationModuleId, Record<string, string>> = {
  hostname: { query: '', set: '将更改主机名，可能影响依赖原名称的服务。' },
  packages: {
    list_repos: '', upgrade_all: '将升级该主机可用的软件包更新，可能影响运行中的服务。',
    add_repo: '将新增软件仓库配置，影响后续软件包来源。',
    update_repo: '将修改目标仓库的下载地址，影响后续软件包来源。',
    delete_repo: '将删除目标仓库配置，该仓库将无法继续用于安装和更新软件包。',
  },
  firewall: {
    start: '将启动防火墙，现有网络连接可能受到影响。', stop: '将停止防火墙，主机网络访问规则将不再生效。',
    enable: '将启用防火墙开机自启，重启后的网络访问可能变化。', disable: '将关闭防火墙开机自启，重启后规则不再自动生效。',
    add_service: '将开放所选服务的网络访问。', remove_service: '将移除所选服务的访问规则，相关连接可能中断。',
    add_port: '将开放所选端口的网络访问。', remove_port: '将移除所选端口的访问规则，相关连接可能中断。',
    reload: '将重载防火墙并丢弃仅运行态规则，现有连接可能受到影响。',
  },
  kernel: {
    set_sysctl: '将修改运行中的内核参数及持久配置，可能影响系统服务。',
    set_limit: '将修改资源限制配置，后续启动的进程可能受到影响。',
  },
  system: {
    chrony: '将修改时间同步配置并重启服务，系统时间同步可能受到影响。',
    vimrc: '将修改 root 的 Vim 默认配置。',
    selinux: '将修改 SELinux 运行态和重启后模式；禁用模式需重启才能完全生效。',
  },
  disk: {
    list: '', provision: '将对所选整盘分区、创建逻辑卷、格式化并挂载；磁盘上原有数据无法恢复。',
  },
}
export function validateOperationActions(module: OperationModuleId, actions: OperationAction[]) {
  if (actions.some((item) => !(item.id in operationImpacts[module]) || item.destructive && !operationImpacts[module][item.id]
    || !item.destructive && operationImpacts[module][item.id])) throw new Error('操作目录与影响提示不一致')
}
export function preflightEvidence(value: string | null) {
  return value?.split('\n').filter((line) => !/^[a-f0-9]{64}(?:\s|$)/i.test(line.trim())).join('\n').trim() ?? ''
}

export const taskLabels: Record<OperationTaskStatus, string> = {
  planned: '待确认', queued: '排队中', running: '执行中', succeeded: '成功', failed: '失败',
  partial: '部分成功', unknown: '结果未知', interrupted: '已中断', expired: '已过期',
}
export const hostLabels: Record<OperationHostStatus, string> = {
  planned: '待确认', queued: '排队中', running: '执行中', succeeded: '成功',
  failed: '失败', unknown: '结果未知', interrupted: '已中断',
}
export const stepLabels: Record<OperationStepStatus, string> = {
  pending: '待执行', running: '执行中', succeeded: '成功', failed: '失败', unknown: '结果未知',
}
export function statusType(status: OperationTaskStatus | OperationHostStatus | OperationStepStatus) {
  if (status === 'succeeded') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'partial' || status === 'unknown' || status === 'interrupted' || status === 'expired') return 'warning'
  return 'info'
}
export const isRunningOperation = (status: OperationTaskStatus) => status === 'queued' || status === 'running'
export function operationTime(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '—'
}
