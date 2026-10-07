import asyncio

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.ai.context.redactor import redact
from app.db.models import Execution, Proposal, uid, utcnow
from app.errors import DependencyUnavailable, ServiceError
from app.soar.proposals.service import audit
from app.soar.verification.service import verify_effect
from app.soar.executors.contracts import ExecutionReceipt


async def rollback(session, proposal, principal, executor, timeout=60):
    # EXECUTING may still have a live worker: reconciliation must precede rollback.
    if proposal.status not in {"SUCCESS", "FAILED", "UNKNOWN"} or not proposal.rollback_available:
        raise ServiceError("rollback_not_available")
    original = session.scalar(
        select(Execution).where(Execution.proposal_id == proposal.proposal_id, Execution.operation == "execute")
    )
    if (
        not original
        or original.executor != executor.name
        or proposal.executor != executor.name
        or proposal.dry_run != executor.dry_run
        or await executor.health() != "healthy"
    ):
        raise DependencyUnavailable("executor_unavailable_or_changed")
    claimed = session.execute(
        update(Proposal)
        .where(Proposal.proposal_id == proposal.proposal_id, Proposal.status.in_(["SUCCESS", "FAILED", "UNKNOWN"]))
        .values(status="ROLLING_BACK")
        .execution_options(synchronize_session="fetch")
    )
    if claimed.rowcount != 1:
        session.rollback()
        raise ServiceError("rollback_already_claimed")
    operation = Execution(
        id=uid("EXE"), proposal_id=proposal.proposal_id, operation="rollback", status="STARTED", executor=executor.name
    )
    session.add(operation)
    audit(session, principal, "ROLLBACK_CLAIMED", proposal.proposal_id)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ServiceError("rollback_already_claimed") from exc
    try:
        result = await asyncio.wait_for(executor.rollback(proposal), timeout)
        if not executor.dry_run:
            receipt = ExecutionReceipt.model_validate(result)
            if receipt.proposal_id != proposal.proposal_id or receipt.operation != "rollback" or receipt.dry_run:
                raise ServiceError("invalid_execution_receipt")
        verified = await asyncio.wait_for(verify_effect(executor, proposal, restored=True), timeout)
        status = "RESTORED" if verified else "ROLLBACK_FAILED"
        operation.result = redact({"rollback": result, "verified_removed": verified, "dry_run": executor.dry_run})
    except Exception:
        status = "ROLLBACK_UNKNOWN"
        operation.result = {"error": "rollback_outcome_unknown", "dry_run": executor.dry_run}
    operation.status, operation.completed_at, proposal.status = status, utcnow(), status
    audit(session, principal, status, proposal.proposal_id)
    session.commit()
    return proposal
