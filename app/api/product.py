import json
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from app.api.ai import run_out
from app.api.serialization import fields
from app.db.models import AIRun, Audit, Proposal, StoredAsset, StoredEvent, StoredIncident
from app.db.session import get_db
from app.errors import ServiceError
from app.ingestion.contracts import AssetIn, EventBatch, IncidentBatch
from app.ingestion.service import ingest
from app.security.auth import principal, require
from app.soar.proposals.service import audit

router = APIRouter(prefix="/v1", tags=["Product"])


def record_out(row):
    value = {
        **fields(row, ("id", "tenant_id", "source_id", "external_id", "received_at", "content_hash")),
        **row.payload,
    }
    value['received_at'] = value['received_at'].isoformat().replace('+00:00', 'Z')
    return value


def page(db, model, tenant, limit, offset):
    rows = db.scalars(
        select(model)
        .where(model.tenant_id == tenant)
        .order_by(model.received_at.desc(), model.id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return {
        "items": [record_out(r) for r in rows[:limit]],
        "next_offset": offset + limit if len(rows) > limit else None,
    }


@router.post("/ingest/events", status_code=201)
def events_ingest(body: EventBatch, db=Depends(get_db), p=Depends(require("analyst"))):
    return {"items": ingest(db, p, body.events)}


@router.post("/ingest/incidents", status_code=201)
def incidents_ingest(body: IncidentBatch, db=Depends(get_db), p=Depends(require("analyst"))):
    return {"items": ingest(db, p, body.incidents, incidents=True)}


@router.get("/events")
def events(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db=Depends(get_db), p=Depends(principal)
):
    return page(db, StoredEvent, p.tenant_id, limit, offset)


@router.get("/events/{event_id}")
def event_detail(event_id: str, db=Depends(get_db), p=Depends(principal)):
    row = db.scalar(select(StoredEvent).where(StoredEvent.id == event_id, StoredEvent.tenant_id == p.tenant_id))
    if not row:
        raise ServiceError("event_not_found", 404)
    return record_out(row)


@router.get("/incidents")
def incidents(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db=Depends(get_db), p=Depends(principal)
):
    return page(db, StoredIncident, p.tenant_id, limit, offset)


@router.get("/incidents/{incident_id}")
async def incident_detail(incident_id: str, request: Request, p=Depends(principal)):
    return (await request.app.state.repository.get_incident_context(incident_id, p.tenant_id)).model_dump(mode="json")


@router.get("/ai/runs")
def runs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db=Depends(get_db), p=Depends(principal)):
    rows = db.scalars(
        select(AIRun)
        .where(AIRun.tenant_id == p.tenant_id)
        .order_by(AIRun.started_at.desc(), AIRun.run_id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return {
        "items": [run_out(db, r) for r in rows[:limit]],
        "next_offset": offset + limit if len(rows) > limit else None,
    }


@router.get("/assets")
def assets(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db=Depends(get_db), p=Depends(principal)
):
    rows = db.scalars(
        select(StoredAsset)
        .where(StoredAsset.tenant_id == p.tenant_id)
        .order_by(StoredAsset.asset_id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return {"items": [r.payload for r in rows[:limit]], "next_offset": offset + limit if len(rows) > limit else None}


@router.put("/assets/{asset_id}")
def asset_save(asset_id: str, body: AssetIn, db=Depends(get_db), p=Depends(require("admin"))):
    if body.asset_id != asset_id:
        raise ServiceError("asset_id_mismatch", 422)
    current = db.get(StoredAsset, (p.tenant_id, asset_id))
    if current:
        # Changing provenance mode could invalidate historical incidents; require a new identity.
        if current.payload["data_mode"] != body.data_mode:
            raise ServiceError("asset_mode_immutable", 409)
        current.payload = body.model_dump(mode="json")
    else:
        db.add(StoredAsset(tenant_id=p.tenant_id, asset_id=asset_id, payload=body.model_dump(mode="json")))
    audit(db, p, "ASSET_CONFIGURED", asset_id=asset_id)
    db.commit()
    return body


@router.get("/audit")
def audits(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db=Depends(get_db), p=Depends(principal)
):
    rows = db.scalars(
        select(Audit)
        .where(Audit.tenant_id == p.tenant_id)
        .order_by(Audit.created_at.desc(), Audit.id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return {
        "items": [fields(r, ("id", "actor", "action", "proposal_id", "detail", "created_at")) for r in rows[:limit]],
        "next_offset": offset + limit if len(rows) > limit else None,
    }


@router.get("/overview")
def overview(db=Depends(get_db), p=Depends(principal)):
    counts = {
        name: db.scalar(select(func.count()).select_from(model).where(model.tenant_id == p.tenant_id))
        for name, model in [
            ("incidents", StoredIncident),
            ("events", StoredEvent),
            ("ai_runs", AIRun),
            ("actions", Proposal),
            ("assets", StoredAsset),
        ]
    }
    return {"counts": counts, "tenant_id": p.tenant_id, "live_containment_available": False}


@router.get("/integrations")
def integrations(p=Depends(principal)):
    return {
        "items": [
            {"id": "generic_rest", "status": "PASS", "scope": "Normalized authenticated ingestion"},
            {
                "id": "webhook",
                "status": "PASS",
                "scope": "Same normalized ingestion contract; no vendor signature parser",
            },
            {
                "id": "sentinelzone",
                "status": "UNVERIFIED",
                "scope": "Optional read-only import; HTTP mock contracts only",
            },
            {"id": "wazuh", "status": "NOT IMPLEMENTED", "scope": "Configuration and adapter skeleton"},
            {"id": "splunk", "status": "NOT IMPLEMENTED", "scope": "Configuration and adapter skeleton"},
        ]
    }


@router.get("/settings")
def settings_view(request: Request, p=Depends(require("admin"))):
    s = request.app.state.settings
    return {
        "managed_by": "Environment configuration; restart after changes",
        "provider": s.ai_provider,
        "model": request.app.state.provider.model,
        "executor": s.soar_executor,
        "context_source": s.core_mode,
        "max_evidence": s.max_evidence,
        "max_request_bytes": s.max_request_bytes,
        "demo_enabled": s.enable_demo,
        "live_executors": "NOT IMPLEMENTED — fail closed",
        "sso": "NOT IMPLEMENTED — identity port reserved",
    }


@router.post("/demo", status_code=201)
def load_demo(request: Request, db=Depends(get_db), p=Depends(require("analyst"))):
    if not request.app.state.settings.enable_demo:
        raise ServiceError("demo_disabled", 403)
    from app.config import ROOT

    data = json.loads((ROOT / "examples/demo.json").read_text(encoding="utf-8"))
    events = ingest(db, p, EventBatch.model_validate(data["events"]).events)
    incidents = ingest(db, p, IncidentBatch.model_validate(data["incidents"]).incidents, incidents=True)
    return {"data_mode": "TEST", "events": events, "incidents": incidents}
