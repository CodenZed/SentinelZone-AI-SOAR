from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.contracts import DecisionIn, ProposalIn
from app.api.responses import ActionView, ActionPage
from app.api.serialization import fields
from app.db.models import Approval, Audit, Execution, Proposal
from app.db.session import get_db
from app.errors import ServiceError
from app.security.auth import principal, require
from app.soar.proposals import service
from app.soar.rollback.service import rollback as rollback_action

router = APIRouter(prefix="/v1/actions", tags=["SOAR"])


def denied(db, p, error, proposal_id=None):
    db.rollback()
    service.audit(db, p, "REQUEST_DENIED", proposal_id, reason=error.code)
    db.commit()


@router.post("", status_code=201, response_model=ActionView)
async def create(body: ProposalIn, request: Request, db=Depends(get_db), p=Depends(require("analyst"))):
    state = request.app.state
    try:
        proposal = await service.create(db, body, p, state.repository, state.settings, state.executor)
        return action_out(db, proposal)
    except ServiceError as exc:
        denied(db, p, exc)
        raise


@router.get("", response_model=ActionPage)
def listing(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db=Depends(get_db), p=Depends(principal)
):
    items = db.scalars(
        select(Proposal)
        .where(Proposal.tenant_id == p.tenant_id)
        .order_by(Proposal.created_at.desc(), Proposal.proposal_id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return {
        "items": [action_out(db, r) for r in items[:limit]],
        "next_offset": offset + limit if len(items) > limit else None,
    }


def action_out(db, proposal):
    value = service.serialize(proposal)
    proposal_id = proposal.proposal_id
    value["executions"] = [
        fields(r, ("id", "operation", "status", "executor", "result", "started_at", "completed_at"))
        for r in db.scalars(
            select(Execution).where(Execution.proposal_id == proposal_id).order_by(Execution.started_at)
        )
    ]
    audits = db.scalars(
        select(Audit)
        .where(Audit.proposal_id == proposal_id, Audit.tenant_id == proposal.tenant_id)
        .order_by(Audit.created_at.desc(), Audit.id.desc())
        .limit(201)
    ).all()
    value["audit"] = [fields(r, ("actor", "action", "detail", "created_at")) for r in reversed(audits[:200])]
    value["audit_truncated"] = len(audits) > 200
    approval = db.get(Approval, proposal_id)
    value["approval"] = fields(approval, ("actor", "decision", "reason", "created_at")) if approval else None
    operations = {r["operation"]: r for r in value["executions"]}
    execution = operations.get("execute", {}).get("result", {})
    rollback = operations.get("rollback", {}).get("result", {})
    value.update(
        execution_result=execution or None,
        verification_result=execution.get("verified"),
        rollback_result=rollback or None,
        restoration_verified=rollback.get("verified_removed"),
    )
    return value


@router.get("/{proposal_id}", response_model=ActionView)
def get_action(proposal_id: str, db=Depends(get_db), p=Depends(principal)):
    return action_out(db, service.find(db, proposal_id, p))


async def apply_decision(proposal_id, body, request, db, p, approve):
    proposal = service.find(db, proposal_id, p)
    try:
        return action_out(
            db,
            await service.decision(
                db, proposal, p, approve, body.reason, request.app.state.repository, request.app.state.settings
            ),
        )
    except ServiceError as exc:
        denied(db, p, exc, proposal_id)
        raise


@router.post("/{proposal_id}/approve", response_model=ActionView)
async def approve(
    proposal_id: str, body: DecisionIn, request: Request, db=Depends(get_db), p=Depends(require("operator"))
):
    return await apply_decision(proposal_id, body, request, db, p, True)


@router.post("/{proposal_id}/reject", response_model=ActionView)
async def reject(
    proposal_id: str, body: DecisionIn, request: Request, db=Depends(get_db), p=Depends(require("operator"))
):
    return await apply_decision(proposal_id, body, request, db, p, False)


@router.post("/{proposal_id}/execute", response_model=ActionView)
async def execute(proposal_id: str, request: Request, db=Depends(get_db), p=Depends(require("operator"))):
    proposal = service.find(db, proposal_id, p)
    state = request.app.state
    try:
        return action_out(db, await service.execute(db, proposal, p, state.repository, state.settings, state.executor))
    except ServiceError as exc:
        denied(db, p, exc, proposal_id)
        raise


@router.post("/{proposal_id}/rollback", response_model=ActionView)
async def rollback(proposal_id: str, request: Request, db=Depends(get_db), p=Depends(require("operator"))):
    proposal = service.find(db, proposal_id, p)
    try:
        return action_out(
            db,
            await rollback_action(
                db, proposal, p, request.app.state.executor, request.app.state.settings.executor_timeout_seconds
            ),
        )
    except ServiceError as exc:
        denied(db, p, exc, proposal_id)
        raise
