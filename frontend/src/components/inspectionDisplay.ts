import type { CheckResponse, CheckStatus, Conclusion, Metric, ResultTable, RunStatus, TaskSummary } from '@/types/inspections'

// 运行时长是秒数而非日期，年、月按固定天数拆分。
const DURATION_UNITS = [
  { label: '年', seconds: 365 * 24 * 60 * 60 },
  { label: '个月', seconds: 30 * 24 * 60 * 60 },
  { label: '天', seconds: 24 * 60 * 60 },
  { label: '小时', seconds: 60 * 60 },
  { label: '分', seconds: 60 },
  { label: '秒', seconds: 1 },
]
const INTERNAL_INTERFACE = /^(?:lo\d*|docker\d*|podman\d*|br-[\da-f]+|veth[\w.-]*|virbr[\w.-]*|cni[\w.-]*|flannel[\w.-]*|cali[\w.-]*|kube-ipvs\d*)$/i
const INTERNAL_FILESYSTEMS = new Set([
  'tmpfs', 'devtmpfs', 'proc', 'sysfs', 'cgroup', 'cgroup2', 'devpts',
  'securityfs', 'debugfs', 'tracefs', 'configfs', 'pstore', 'mqueue', 'hugetlbfs', 'autofs',
  'overlay', 'aufs', 'squashfs', 'nsfs',
])
// 保留 Docker 数据目录等独立分区，只隐藏容器内部的重复挂载。
const INTERNAL_MOUNT = /^\/var\/lib\/(?:docker\/(?:overlay2|aufs|containers)\/|containers\/storage\/overlay\/|containerd\/[^/]+\/snapshots\/|kubelet\/pods\/)/
const DISK_CAPACITY_COLUMNS = new Map([
  ['总量 KiB', '总量'], ['已用 KiB', '已用'], ['可用 KiB', '可用'],
])
const BYTES_PER_KIB = 1024
const CAPACITY_UNIT_BASE = 1000
const CAPACITY_UNITS = ['KB', 'MB', 'GB', 'TB', 'PB', 'EB']

export function durationLabel(seconds: number): string {
  let remaining = Math.floor(seconds)
  const parts = DURATION_UNITS.flatMap(({ label, seconds: unitSeconds }) => {
    const value = Math.floor(remaining / unitSeconds)
    remaining %= unitSeconds
    return value > 0 ? [`${value}${label}`] : []
  })
  return parts.length ? parts.join(' ') : '0秒'
}

function diskCapacityLabel(kib: string): string {
  let capacity = Number(kib) * BYTES_PER_KIB / CAPACITY_UNIT_BASE
  let unitIndex = 0
  while (capacity >= CAPACITY_UNIT_BASE && unitIndex < CAPACITY_UNITS.length - 1) {
    capacity /= CAPACITY_UNIT_BASE
    unitIndex++
  }
  return `${capacity.toFixed(1)} ${CAPACITY_UNITS[unitIndex]}`
}

function percentageLabel(value: string | number): string {
  const numeric = typeof value === 'number' ? value : Number(value.replace(/%$/, '').trim())
  if (!Number.isFinite(numeric) || (typeof value === 'string' && !value.trim())) return String(value)
  return `${numeric.toFixed(1)}${typeof value === 'string' && value.endsWith('%') ? '%' : ''}`
}

export function metricLabel(metric: Metric): string {
  if (metric.value === null) return '未记录'
  if (metric.name === '运行时长' && metric.unit === '秒') {
    const seconds = Number(metric.value)
    if (Number.isFinite(seconds) && seconds >= 0) return durationLabel(seconds)
  }
  const value = metric.unit === '%' ? percentageLabel(metric.value).replace(/%$/, '') : String(metric.value)
  return `${value}${metric.unit ? ` ${metric.unit}` : ''}`
}

export function findingLabel(message: string): string {
  return message.replace(/\d+(?:\.\d+)?%/g, (value) => percentageLabel(value))
}

function visibleInterface(row: string[]): boolean {
  const name = row[0]?.split('@')[0] ?? ''
  const address = row[1]?.split('/')[0] ?? ''
  return !INTERNAL_INTERFACE.test(name) && !/^127\./.test(address) && address !== '::1'
}

function visibleDisk(row: string[], table: ResultTable): boolean {
  const type = row[table.columns.indexOf('类型')] ?? ''
  const mount = row[table.columns.indexOf('挂载点')] ?? ''
  const device = row[table.columns.indexOf('设备')] ?? ''
  return !INTERNAL_FILESYSTEMS.has(type) && !INTERNAL_MOUNT.test(mount) && !/^\/dev\/loop\d+$/.test(device)
}

export function displayTables(check: CheckResponse): ResultTable[] {
  return check.payload.tables
    .filter((table) => !(check.check_id === 'server_info' && table.columns.includes('网卡')))
    .map((table) => {
      let rows = table.rows
      const isDiskTable = check.check_id === 'system_resources' && table.name === '磁盘'
      if (check.check_id === 'network_info' && table.columns.includes('网卡')) rows = rows.filter(visibleInterface)
      if (isDiskTable) rows = rows.filter((row) => visibleDisk(row, table))
      return {
        ...table,
        columns: table.columns.map((column) => isDiskTable ? DISK_CAPACITY_COLUMNS.get(column) ?? column : column),
        rows: rows.map((row) => row.map((value, index) => {
          const column = table.columns[index]
          if (isDiskTable && column && DISK_CAPACITY_COLUMNS.has(column)) return diskCapacityLabel(value)
          return column === '使用率' || column === '%CPU' || column === '%MEM' ? percentageLabel(value) : value
        })),
      }
    })
}

export function displayChecks(checks: CheckResponse[]): CheckResponse[] {
  return checks.map((check) => {
    const tables = displayTables(check)
    return {
      ...check,
      payload: {
        ...check.payload,
        tables,
      },
    }
  })
}

export const isActiveRun = (status: RunStatus) => status === 'queued' || status === 'running'

export function hostProgressLabel(task: TaskSummary): string {
  // 接口的完成数包含所有终态，失败数包含部分完成、失败和中断。
  return `${task.completed_hosts} / ${task.host_count} 已结束 · ${task.failed_hosts} 未完整完成`
}

export function summarizeChecks(checks: CheckResponse[]) {
  const findings = checks.flatMap((check) => check.payload.findings)
  return {
    completed: checks.filter((check) => check.status === 'completed').length,
    critical: findings.filter((finding) => finding.severity === 'critical').length,
    warning: findings.filter((finding) => finding.severity === 'warning').length,
    incomplete: checks.filter((check) => check.status !== 'completed').length,
  }
}

export function runLabel(status: RunStatus): string {
  return { queued: '排队中', running: '执行中', completed: '已完成', partial: '部分完成', failed: '执行失败', interrupted: '已中断' }[status]
}
export function checkLabel(status: CheckStatus): string {
  return { queued: '未开始', running: '执行中', completed: '已完成', failed: '执行失败', skipped: '已跳过', interrupted: '已中断' }[status]
}
export function conclusionLabel(value: Conclusion): string {
  return { normal: '正常', warning: '警告', critical: '严重', not_applicable: '不适用', unknown: '无法判定' }[value]
}
export function runType(status: RunStatus): 'info' | 'success' | 'warning' | 'danger' {
  if (status === 'completed') return 'success'
  if (status === 'partial') return 'warning'
  if (status === 'failed' || status === 'interrupted') return 'danger'
  return 'info'
}
export function conclusionType(value: Conclusion): 'info' | 'success' | 'warning' | 'danger' {
  if (value === 'normal') return 'success'
  if (value === 'warning') return 'warning'
  if (value === 'critical') return 'danger'
  return 'info'
}
