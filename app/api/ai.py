from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.ai.investigation.runner import investigate
from app.contracts import AnalyzeIn, AIOutput
from app.api.responses import AIRunView, AIRunPage
from app.api.serialization import utc
from app.db.models import AIAnalysis, AIRun, AIStep
from app.db.session import get_db
from app.errors import ServiceError
from app.security.auth import principal, require

router = APIRouter(tags=["AI"])


def run_out(session, run):
    analysis = session.get(AIAnalysis, run.run_id)
    steps = session.scalars(select(AIStep).where(AIStep.run_id == run.run_id).order_by(AIStep.sequence)).all()
    output = analysis.output if analysis and analysis.trusted else None
    ids = {uid for fact in (output or {}).get("observed_facts", []) for uid in fact["evidence_event_ids"]}
    data = (run.context_snapshot or {}).get("data", {})
    return utc(
        {
            **{key: output[key] if output else None for key in AIOutput.model_fields},
            "created_at": run.started_at,
            "data_mode": data.get("data_mode", "UNKNOWN"),
            "citations": [
                {k: e[k] for k in ("event_uid", "incident_id", "source", "event_time")}
                for e in data.get("evidence", [])
                if e["event_uid"] in ids
            ],
            "human_review_required": True,
            "run_id": run.run_id,
            "incident_id": run.incident_id,
            "tenant_id": run.tenant_id,
            "status": run.status,
            "validation_status": run.validation_status,
            "error_code": run.error_code,
            "provider": run.provider,
            "model": run.model,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "trusted": bool(analysis and analysis.trusted),
            "analysis": analysis.output if analysis and analysis.trusted else None,
            "validation": analysis.validation if analysis else None,
            "context_snapshot": run.context_snapshot,
            "steps": [
                {
                    k: getattr(s, k)
                    for k in ("sequence", "stage", "status", "duration_ms", "tool_name", "output_ref", "evidence_ids")
                }
                for s in steps
            ],
        }
    )


@router.post("/v1/ai/analyze", status_code=201, response_model=AIRunView)
async def analyze(body: AnalyzeIn, request: Request, db=Depends(get_db), p=Depends(require("analyst"))):
    state = request.app.state
    run = await investigate(db, p, body.incident_id, state.repository, state.provider, state.settings)
    return run_out(db, run)


@router.get("/v1/ai/runs/{run_id}", response_model=AIRunView)
def get_run(run_id: str, db=Depends(get_db), p=Depends(principal)):
    run = db.scalar(select(AIRun).where(AIRun.run_id == run_id, AIRun.tenant_id == p.tenant_id))
    if run is None:
        raise ServiceError("run_not_found", 404)
    return run_out(db, run)


@router.get("/v1/incidents/{incident_id}/analyses", response_model=AIRunPage)
def analyses(
    incident_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
    p=Depends(principal),
):
    runs = db.scalars(
        select(AIRun)
        .where(AIRun.incident_id == incident_id, AIRun.tenant_id == p.tenant_id)
        .order_by(AIRun.started_at.desc(), AIRun.run_id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return {
        "items": [run_out(db, r) for r in runs[:limit]],
        "next_offset": offset + limit if len(runs) > limit else None,
    }
