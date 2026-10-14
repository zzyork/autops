import type { AnalysisEvidence, AnalysisIssue, AnalysisSeverity, AnalysisStatus, DiagnosticGroup } from '@/types/inspections'

export function analysisStatusLabel(status: AnalysisStatus): string {
  return { not_generated: '未生成', unavailable: '不可用', queued: '排队中', running: '生成中', completed: '已完成', failed: '生成失败', interrupted: '已中断' }[status]
}

interface LogDetail {
  id: string
  message: string
  host: string
  path: string | null
  occurrences: number | null
  firstTime: string | null
  lastTime: string | null
}

export function issueLogDetails(issue: AnalysisIssue, evidence: AnalysisEvidence[]): LogDetail[] {
  const ids = new Set(issue.evidence_ids)
  const fragments = new Map<string, AnalysisEvidence[]>()
  for (const item of evidence) {
    if (item.kind !== 'log') continue
    const legacySource = item.source.replace(/（片段 \d+\/\d+）$/, '')
    const key = item.group_id ?? (legacySource !== item.source
      ? JSON.stringify([item.host_name, item.address, legacySource]) : item.id)
    const parts = fragments.get(key)
    if (parts) parts.push(item)
    else fragments.set(key, [item])
  }
  return [...fragments.values()].filter((parts) => parts.some((part) => ids.has(part.id))).map((parts) => {
    const item = parts[0]!
    const content = parts.map((part) => part.content).join('')
    const source = item.source.replace(/（片段 \d+\/\d+）$/, '').replace(/ · 结果序号 \d+$/, '')
    const detail: LogDetail = {
      id: item.id, message: content, host: `${item.host_name} (${item.address})`,
      path: source.startsWith('/') ? source : null,
      occurrences: item.original_lines?.length || null, firstTime: null, lastTime: null,
    }
    // 历史报告保存结果行或纯日志；新版证据保存精确报错及其采集统计。
    let metadata: unknown
    try { metadata = JSON.parse(content) } catch { return detail }
    if (typeof metadata !== 'object' || metadata === null) return detail
    if ('row' in metadata && Array.isArray(metadata.row) && metadata.row[0] === '匹配' && typeof metadata.row[1] === 'string') {
      detail.message = metadata.row[1]
      detail.occurrences = 1
      const stamp = detail.message.match(/^\[?(\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s{1,2}\d{1,2}\s+\d{2}:\d{2}:\d{2})\]?\s+/)
      if (stamp) detail.firstTime = detail.lastTime = stamp[1]!
      return detail
    }
    if (!('message' in metadata) || typeof metadata.message !== 'string'
      || !('result_indices' in metadata) || !Array.isArray(metadata.result_indices)
      || !metadata.result_indices.every((index: unknown) => typeof index === 'number' && Number.isInteger(index) && index > 0)
      || !('occurrences' in metadata) || typeof metadata.occurrences !== 'number' || !Number.isInteger(metadata.occurrences) || metadata.occurrences < 1
      || !('first_time' in metadata) || (metadata.first_time !== null && typeof metadata.first_time !== 'string')
      || !('last_time' in metadata) || (metadata.last_time !== null && typeof metadata.last_time !== 'string')) return detail
    detail.message = metadata.message
    detail.occurrences = metadata.occurrences
    detail.firstTime = metadata.first_time
    detail.lastTime = metadata.last_time
    return detail
  })
}

export function issueDiagnosticGroups(issue: AnalysisIssue): DiagnosticGroup[] {
  if (issue.diagnostic_groups?.length) return issue.diagnostic_groups
  return issue.diagnostic_group ? [issue.diagnostic_group] : []
}

export function analysisSeverityLabel(severity: AnalysisSeverity): string {
  return { critical: '严重', warning: '警告', info: '信息' }[severity]
}

export function analysisSeverityType(severity: AnalysisSeverity): 'danger' | 'warning' | 'info' {
  return severity === 'critical' ? 'danger' : severity
}
