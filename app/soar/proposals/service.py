import asyncio
from datetime import timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.ai.context.redactor import redact
from app.contracts import ActionProposal
from app.db.models import Approval, Audit, Execution, Proposal, User, uid, utcnow
from app.errors import DependencyUnavailable, ServiceError
from app.soar.approvals.service import decide, expired
from app.soar.playbooks.engine import catalog, execution_plan, validate_playbook
from app.soar.proposals.policy import TargetPolicy
from app.soar.verification.service import verify_effect
from app.soar.executors.contracts import ExecutionReceipt


def audit(session, principal, action, proposal_id=None, **detail):
    session.add(
        Audit(
            id=uid("AUD"),
            tenant_id=principal.tenant_id,
            proposal_id=proposal_id,
            actor=principal.id,
            action=action,
            detail=redact(detail),
        )
    )


def find(session, proposal_id, principal):
    result = session.scalar(
        select(Proposal).where(Proposal.proposal_id == proposal_id, Proposal.tenant_id == principal.tenant_id)
    )
    if result is None:
        raise ServiceError("proposal_not_found", 404)
    return result


def serialize(proposal):
    data = {
        k: getattr(proposal, k) for k in ActionProposal.model_fields if k not in {"effect_scope", "approval_status"}
    }
    for field in ("created_at", "expires_at"):
        if data[field].tzinfo is None:
            data[field] = data[field].replace(tzinfo=timezone.utc)
    data["effect_scope"] = "simulated" if proposal.dry_run else "live"
    data["approval_status"] = (
        "approved" if proposal.approved_by else ("rejected" if proposal.status == "REJECTED" else "pending")
    )
    # Available means the endpoint can currently be invoked, not merely a playbook capability.
    data["rollback_available"] = bool(
        proposal.rollback_available and proposal.status in {"SUCCESS", "FAILED", "UNKNOWN"}
    )
    return ActionProposal.model_validate(data).model_dump(mode="json")


async def create(session, body, principal, core, settings, executor):
    context = await core.get_incident_context(body.incident_id, principal.tenant_id)
    if not executor.dry_run and context.data_mode != "REAL":
        raise ServiceError("real_executor_requires_real_incident", 403)
    target = await TargetPolicy(settings).validate(
        body.target, body.action_type, body.parameters, principal.tenant_id, core
    )
    book = catalog(settings.playbook_dir).get(body.playbook_id)
    if not book or book.action_type != body.action_type:
        raise ServiceError("playbook_action_mismatch", 422)
    proposal = Proposal(
        proposal_id=uid("ACT"),
        tenant_id=principal.tenant_id,
        incident_id=body.incident_id,
        action_type=body.action_type,
        target=target,
        parameters=body.parameters,
        requested_by=principal.id,
        expires_at=utcnow() + timedelta(minutes=body.ttl_minutes),
        playbook_id=book.id,
        playbook_snapshot=book.model_dump(mode="json"),
        dry_run=executor.dry_run,
        executor=executor.name,
    )
    session.add(proposal)
    session.flush()
    audit(session, principal, "PROPOSED", proposal.proposal_id)
    session.commit()
    return proposal


async def decision(session, proposal, principal, approve, reason, core, settings):
    if approve:
        await TargetPolicy(settings).validate(
            proposal.target, proposal.action_type, proposal.parameters, principal.tenant_id, core
        )
    decide(session, proposal, principal, approve, redact(reason))
    audit(session, principal, "APPROVED" if approve else "REJECTED", proposal.proposal_id, reason=reason)
    session.commit()
    session.refresh(proposal)
    return proposal


async def execute(session, proposal, principal, core, settings, executor):
    if session.scalar(
        select(Execution.id).where(Execution.proposal_id == proposal.proposal_id, Execution.operation == "execute")
    ):
        raise ServiceError("ALREADY_EXECUTED" if proposal.status == "SUCCESS" else "execution_already_claimed")
    if proposal.status != "APPROVED":
        raise ServiceError("approval_required")
    if expired(proposal):
        raise ServiceError("proposal_expired")
    approval = session.get(Approval, proposal.proposal_id)
    approver = session.get(User, proposal.approved_by) if proposal.approved_by else None
    if (
        not approval
        or approval.decision != "APPROVED"
        or approval.actor != proposal.approved_by
        or approval.actor == proposal.requested_by
        or not approver
        or not approver.active
        or approver.role != "operator"
        or approver.tenant_id != principal.tenant_id
    ):
        raise ServiceError("valid_independent_approval_required", 403)
    if (
        proposal.executor != executor.name
        or proposal.dry_run != executor.dry_run
        or await executor.health() != "healthy"
    ):
        raise DependencyUnavailable("executor_unavailable_or_changed")
    context = await core.get_incident_context(proposal.incident_id, principal.tenant_id)
    if not executor.dry_run and context.data_mode != "REAL":
        raise ServiceError("real_executor_requires_real_incident", 403)
    target = await TargetPolicy(settings).validate(
        proposal.target, proposal.action_type, proposal.parameters, principal.tenant_id, core
    )
    if target != proposal.target:
        raise ServiceError("target_changed_reproposal_required")
    book = validate_playbook(proposal.playbook_snapshot)
    plan = execution_plan(book, proposal)
    # Durable claim commits before any side effect. A crash is never retried blindly.
    claimed = session.execute(
        update(Proposal)
        .where(
            Proposal.proposal_id == proposal.proposal_id, Proposal.status == "APPROVED", Proposal.expires_at > utcnow()
        )
        .values(status="EXECUTING")
        .execution_options(synchronize_session="fetch")
    )
    if claimed.rowcount != 1:
        session.rollback()
        raise ServiceError("execution_already_claimed_or_expired")
    execution = Execution(
        id=uid("EXE"), proposal_id=proposal.proposal_id, operation="execute", status="STARTED", executor=executor.name
    )
    session.add(execution)
    audit(session, principal, "EXECUTION_CLAIMED", proposal.proposal_id, plan=plan)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ServiceError("execution_already_claimed") from exc
    try:
        result = await asyncio.wait_for(executor.execute(proposal), settings.executor_timeout_seconds)
        if not executor.dry_run:
            receipt = ExecutionReceipt.model_validate(result)
            if receipt.proposal_id != proposal.proposal_id or receipt.operation != "execute" or receipt.dry_run:
                raise ServiceError("invalid_execution_receipt")
        verified = await asyncio.wait_for(verify_effect(executor, proposal), settings.executor_timeout_seconds)
        status = "SUCCESS" if verified else "FAILED"
        execution.result = redact({"execution": result, "verified": verified, "dry_run": executor.dry_run})
    except Exception:
        # The side effect may already exist. Keep the durable claim and require reconciliation.
        status = "UNKNOWN"
        execution.result = {"error": "executor_outcome_unknown", "dry_run": executor.dry_run}
    execution.status, execution.completed_at, proposal.status = status, utcnow(), status
    audit(session, principal, status, proposal.proposal_id, dry_run=executor.dry_run)
    session.commit()
    return proposal
