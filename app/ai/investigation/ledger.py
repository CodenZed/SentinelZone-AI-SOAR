from app.db.models import AIStep, uid


def step(session, run, stage, sequence, *, status="completed", duration_ms=0, evidence_ids=None):
    session.add(
        AIStep(
            id=uid("STP"),
            run_id=run.run_id,
            sequence=sequence,
            stage=stage,
            evidence_ids=evidence_ids or [],
            tool_name=stage.lower(),
            output_ref=f"run:{run.run_id}/{stage.lower()}",
            duration_ms=duration_ms,
            status=status,
        )
    )
    session.commit()
