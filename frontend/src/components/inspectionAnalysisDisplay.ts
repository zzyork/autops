import type { AnalysisIssue, AnalysisSeverity, DiagnosticGroup } from '@/types/inspections'

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
