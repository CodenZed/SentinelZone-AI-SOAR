from app.db.models import SimulatedEffect
from app.soar.executors.base import ActionExecutor


class DryRunExecutor(ActionExecutor):
    name, dry_run = "dry_run", True

    def __init__(self, sessions):
        self.sessions = sessions

    async def execute(self, proposal):
        with self.sessions() as session:
            effect = session.get(SimulatedEffect, proposal.proposal_id)
            if effect is None:
                session.add(
                    SimulatedEffect(
                        proposal_id=proposal.proposal_id,
                        target=proposal.target,
                        action_type=proposal.action_type,
                        active=True,
                    )
                )
                session.commit()
        return {"dry_run": True, "message": "WOULD EXECUTE", "effect_id": proposal.proposal_id}

    async def verify(self, proposal, *, restored=False):
        # Separate state query; execute's return value is never treated as verification.
        with self.sessions() as session:
            effect = session.get(SimulatedEffect, proposal.proposal_id)
            return bool(
                effect
                and effect.target == proposal.target
                and effect.action_type == proposal.action_type
                and effect.active is not restored
            )

    async def rollback(self, proposal):
        with self.sessions() as session:
            effect = session.get(SimulatedEffect, proposal.proposal_id)
            if effect:
                effect.active = False
                session.commit()
        return {"dry_run": True, "message": "WOULD ROLLBACK", "effect_id": proposal.proposal_id}
