from datetime import timedelta

from app.db.models import utcnow
from app.errors import ServiceError
from app.soar.executors.contracts import VerificationReport


async def verify_effect(executor, proposal, *, restored=False):
    value = await executor.verify(proposal, restored=restored)
    # Backward-compatible simulator interface; real adapters may never return just an exit code/bool.
    if executor.dry_run and type(value) is bool:
        return value
    report = VerificationReport.model_validate(value)
    if (
        report.proposal_id != proposal.proposal_id
        or report.target != proposal.target
        or report.action_type != proposal.action_type
        or report.restored is not restored
        or report.dry_run != executor.dry_run
        or not utcnow() - timedelta(minutes=5) <= report.queried_at <= utcnow() + timedelta(seconds=5)
    ):
        raise ServiceError("invalid_verification_scope")
    return report.verified
