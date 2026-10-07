"""Stable, exported dashboard response schemas. Never contain upstream credentials."""

from datetime import datetime
from typing import Literal

from pydantic import Field
from app.contracts import ActionProposal, AIOutput, Contract, Fact, Hypothesis, Playbook


class ErrorIssue(Contract):
    loc: list[str | int]
    type: str


class ErrorDetail(Contract):
    code: str
    issues: list[ErrorIssue] = Field(default_factory=list)


class ErrorResponse(Contract):
    detail: ErrorDetail


class Citation(Contract):
    event_uid: str
    incident_id: str
    source: str
    event_time: datetime


class StepView(Contract):
    sequence: int
    stage: str
    status: str
    duration_ms: int
    tool_name: str
    output_ref: str
    evidence_ids: list[str]


class AIRunView(Contract):
    run_id: str
    incident_id: str
    tenant_id: str
    status: Literal["running", "completed", "invalid", "rejected", "failed"]
    trusted: bool
    validation_status: Literal["pending", "valid", "invalid", "unavailable"]
    provider: str
    model: str
    error_code: str | None
    created_at: datetime
    started_at: datetime
    completed_at: datetime | None
    data_mode: Literal["REAL", "TEST", "REPLAY", "UNKNOWN"]
    observed_facts: list[Fact] | None
    hypotheses: list[Hypothesis] | None
    missing_evidence: list[str] | None
    recommended_investigation: list[str] | None
    containment_options: list[str] | None
    citations: list[Citation]
    human_review_required: Literal[True] = True
    # v0.29.0 compatibility; exactly the same five sections as the flat fields.
    analysis: AIOutput | None
    validation: dict | None
    context_snapshot: dict
    steps: list[StepView]


class AIRunPage(Contract):
    items: list[AIRunView]
    next_offset: int | None


class ExecutionView(Contract):
    id: str
    operation: Literal["execute", "rollback"]
    status: str
    executor: str
    result: dict
    started_at: datetime
    completed_at: datetime | None


class AuditView(Contract):
    actor: str
    action: str
    detail: dict
    created_at: datetime


class ApprovalView(Contract):
    actor: str
    decision: str
    reason: str
    created_at: datetime


class ActionView(ActionProposal):
    approval: ApprovalView | None
    execution_result: dict | None
    verification_result: bool | None
    rollback_result: dict | None
    restoration_verified: bool | None
    executions: list[ExecutionView]
    audit: list[AuditView]
    audit_truncated: bool


class ActionPage(Contract):
    items: list[ActionView]
    next_offset: int | None


class HealthView(Contract):
    status: Literal["healthy", "degraded"]
    database: Literal["healthy", "unavailable"]
    core_backend: str
    core_mode: Literal["standalone", "mock", "real"]
    ai_provider: str
    soar_executor: str
    executor_status: str
    dry_run: bool
    version: str


class PlaybookPage(Contract):
    items: list[Playbook]


class PolicyView(Contract):
    protected_assets: list[str]
    protected_roles: list[str]
    protected_networks: list[str]
    lab_asset_ids: list[str]
    managed_by: str
