from datetime import timezone

from sqlalchemy import update

from app.db.models import Approval, Proposal, utcnow
from app.errors import ServiceError


def expired(proposal):
    value = proposal.expires_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= utcnow()


def decide(session, proposal, principal, approve, reason):
    if proposal.requested_by == principal.id:
        raise ServiceError("self_approval_forbidden", 403)
    if expired(proposal):
        raise ServiceError("proposal_expired")
    status = "APPROVED" if approve else "REJECTED"
    result = session.execute(
        update(Proposal)
        .where(
            Proposal.proposal_id == proposal.proposal_id, Proposal.status == "PROPOSED", Proposal.expires_at > utcnow()
        )
        .values(status=status, approved_by=principal.id if approve else None)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        session.rollback()
        raise ServiceError("proposal_already_decided")
    session.add(Approval(proposal_id=proposal.proposal_id, actor=principal.id, decision=status, reason=reason))
