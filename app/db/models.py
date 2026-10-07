from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


def uid(prefix):
    return f"{prefix}-{uuid4().hex}"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "service_users"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    password_hash: Mapped[str | None] = mapped_column(String(256))
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)


class AIRun(Base):
    __tablename__ = "ai_runs"
    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    incident_id: Mapped[str] = mapped_column(String(128), index=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(40), default="running")
    validation_status: Mapped[str] = mapped_column(String(40), default="pending")
    error_code: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class AIStep(Base):
    __tablename__ = "ai_steps"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("ai_runs.run_id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(80))
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    tool_name: Mapped[str] = mapped_column(String(80))
    output_ref: Mapped[str] = mapped_column(String(256))
    duration_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40))
    __table_args__ = (UniqueConstraint("run_id", "sequence"),)


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    run_id: Mapped[str] = mapped_column(ForeignKey("ai_runs.run_id"), primary_key=True)
    output: Mapped[dict] = mapped_column(JSON)
    trusted: Mapped[bool] = mapped_column(Boolean)
    validation: Mapped[dict] = mapped_column(JSON)


class Proposal(Base):
    __tablename__ = "action_proposals"
    proposal_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    incident_id: Mapped[str] = mapped_column(String(128), index=True)
    action_type: Mapped[str] = mapped_column(String(60))
    target: Mapped[str] = mapped_column(String(128))
    parameters: Mapped[dict] = mapped_column(JSON)
    requested_by: Mapped[str] = mapped_column(String(128))
    approved_by: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(40), default="PROPOSED")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    playbook_id: Mapped[str] = mapped_column(String(128))
    playbook_snapshot: Mapped[dict] = mapped_column(JSON)
    rollback_available: Mapped[bool] = mapped_column(Boolean, default=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    executor: Mapped[str] = mapped_column(String(40), default="dry_run", server_default="dry_run")


class Approval(Base):
    __tablename__ = "action_approvals"
    proposal_id: Mapped[str] = mapped_column(ForeignKey("action_proposals.proposal_id"), primary_key=True)
    actor: Mapped[str] = mapped_column(String(128))
    decision: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Execution(Base):
    __tablename__ = "action_executions"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("action_proposals.proposal_id"), index=True)
    operation: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(40))
    executor: Mapped[str] = mapped_column(String(40))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("proposal_id", "operation"),)


class Audit(Base):
    __tablename__ = "action_audit"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("action_proposals.proposal_id"), index=True)
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SimulatedEffect(Base):
    __tablename__ = "simulated_effects"
    proposal_id: Mapped[str] = mapped_column(ForeignKey("action_proposals.proposal_id"), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean)
    target: Mapped[str] = mapped_column(String(128))
    action_type: Mapped[str] = mapped_column(String(60))


class Tenant(Base):
    __tablename__ = 'tenants'
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BootstrapState(Base):
    __tablename__ = 'bootstrap_state'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class BrowserSession(Base):
    __tablename__ = 'browser_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('service_users.id'), index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LoginThrottle(Base):
    __tablename__ = 'login_throttle'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StoredEvent(Base):
    __tablename__ = 'evidence_events'
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'), index=True)
    source_id: Mapped[str] = mapped_column(String(128))
    external_id: Mapped[str] = mapped_column(String(128))
    content_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint('tenant_id', 'source_id', 'external_id'), UniqueConstraint('tenant_id', 'id'))


class StoredIncident(Base):
    __tablename__ = 'incidents'
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'), index=True)
    source_id: Mapped[str] = mapped_column(String(128))
    external_id: Mapped[str] = mapped_column(String(128))
    content_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint('tenant_id', 'source_id', 'external_id'), UniqueConstraint('tenant_id', 'id'))


class IncidentEvent(Base):
    __tablename__ = 'incident_events'
    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id', 'incident_id'], ['incidents.tenant_id', 'incidents.id']),
        ForeignKeyConstraint(['tenant_id', 'event_id'], ['evidence_events.tenant_id', 'evidence_events.id']),
    )


class StoredAsset(Base):
    __tablename__ = 'assets'
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
