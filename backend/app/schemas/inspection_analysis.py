from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .inspections import TimestampResponse

Severity = Literal["critical", "warning", "info"]
AnalysisStatus = Literal["not_generated", "unavailable", "queued", "running", "completed", "failed", "interrupted"]


class AnalysisEvidence(BaseModel):
    id: str
    kind: Literal["host", "check", "finding", "log"]
    host_name: str
    address: str
    check_title: str
    source: str
    content: str
    severity: Severity
    incomplete: bool = False
    limited: bool = False
    group_id: str | None = None
    original_lines: list[str] = Field(default_factory=list)
    original_indices: list[int] = Field(default_factory=list)
    source_table_index: int | None = None


class DiagnosticObservation(BaseModel):
    host_name: str
    address: str
    source: str
    occurrences: int = Field(ge=1)
    first_time: str | None = None
    last_time: str | None = None


class DiagnosticGroup(BaseModel):
    id: str
    template: str
    service: str | None = None
    occurrences: int = Field(ge=1)
    host_count: int = Field(ge=1)
    observations: list[DiagnosticObservation]


class AnalysisIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=200)
    severity: Severity
    analysis: str = Field(min_length=1, max_length=8000)
    recommendation: str = Field(max_length=2000)
    evidence_ids: list[str] = Field(min_length=1)
    log_source: str | None = None
    log_message: str | None = None
    diagnostic_group: DiagnosticGroup | None = None
    diagnostic_groups: list[DiagnosticGroup] = Field(default_factory=list)


class BatchAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    summary: str = Field(min_length=1, max_length=4000)
    covered_ids: list[str] = Field(min_length=1, max_length=40)
    issues: list[AnalysisIssue] = Field(max_length=40)


class AnalysisReport(BaseModel):
    task_name: str
    task_status: str
    inspection_started_at: datetime | None
    inspection_finished_at: datetime | None
    check_ids: list[str]
    summary: str
    issues: list[AnalysisIssue]
    evidence: list[AnalysisEvidence]
    host_count: int
    finding_count: int
    log_count: int
    incomplete_count: int
    unassessed_count: int
    generated_at: datetime
    model_name: str
    model_version: int


class AnalysisProgress(BaseModel):
    phase: Literal["analyzing", "summarizing"]
    completed_batches: int = Field(ge=0)
    total_batches: int = Field(ge=1)
    current_step: str
    step_started_at: datetime


class AnalysisResponse(TimestampResponse):
    task_id: str
    status: AnalysisStatus
    model_name: str | None = None
    model_version: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    report: AnalysisReport | None = None
    can_generate: bool = False
    progress: AnalysisProgress | None = None
