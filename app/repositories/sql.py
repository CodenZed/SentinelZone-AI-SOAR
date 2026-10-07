from sqlalchemy import select, text
from app.contracts import Asset, Evidence, IncidentContext
from app.db.models import IncidentEvent, StoredAsset, StoredEvent, StoredIncident
from app.errors import DependencyUnavailable, ServiceError
from app.repositories.base import EvidenceRepository, canonical


class SQLEvidenceRepository(EvidenceRepository):
    def __init__(self, sessions):
        self.sessions = sessions

    async def get_incident_context(self, incident_id, tenant_id):
        with self.sessions() as db:
            incident = db.scalar(
                select(StoredIncident).where(StoredIncident.id == incident_id, StoredIncident.tenant_id == tenant_id)
            )
            if not incident:
                raise ServiceError("incident_not_found", 404)
            data = incident.payload
            events = db.scalars(
                select(StoredEvent)
                .join(IncidentEvent, IncidentEvent.event_id == StoredEvent.id)
                .where(
                    IncidentEvent.tenant_id == tenant_id,
                    IncidentEvent.incident_id == incident_id,
                    StoredEvent.tenant_id == tenant_id,
                )
                .order_by(StoredEvent.id)
                .limit(20001)
            ).all()
            if len(events) > 20000:
                raise DependencyUnavailable("context_evidence_limit_exceeded")
            assets = []
            for asset_id in data["asset_ids"]:
                row = db.get(StoredAsset, (tenant_id, asset_id))
                if not row or row.payload["data_mode"] != data["data_mode"]:
                    raise DependencyUnavailable("asset_scope_changed")
                assets.append(Asset(tenant_id=tenant_id, **{k: v for k, v in row.payload.items() if k != "data_mode"}))
            missing = list(data["missing_telemetry"])
            if not data["telemetry"]:
                missing.append("sensor/host telemetry: UNKNOWN (not supplied)")
            if not data["identity_context"]:
                missing.append("identity context: UNKNOWN (not supplied)")
            if not assets or any(a.criticality == "unknown" for a in assets):
                missing.append("asset criticality: UNKNOWN (not supplied)")
            if not events:
                missing.append("No linked evidence supplied; malicious activity remains UNKNOWN")
            return IncidentContext(
                incident_id=incident_id,
                tenant_id=tenant_id,
                status=data["status"],
                priority=data["priority"],
                summary=data["summary"] or data["title"],
                data_mode=data["data_mode"],
                telemetry=data["telemetry"],
                identity_context=data["identity_context"],
                assets=assets,
                missing_telemetry=list(dict.fromkeys(missing)),
                evidence=[
                    Evidence(
                        event_uid=e.id,
                        incident_id=incident_id,
                        tenant_id=tenant_id,
                        source=e.source_id,
                        event_time=e.payload["event_time"],
                        summary=e.payload["summary"] or "UNKNOWN: no summary supplied",
                        priority=e.payload["priority"],
                    )
                    for e in events
                ],
            )

    async def event_exists(self, event_uid):
        # Compatibility port only; scope-aware validation below is used by investigations.
        with self.sessions() as db:
            return db.get(StoredEvent, event_uid) is not None

    async def validate_event_ids(self, ids, incident_id, tenant_id):
        with self.sessions() as db:
            for event_id in ids:
                event = db.scalar(
                    select(StoredEvent.id).where(StoredEvent.id == event_id, StoredEvent.tenant_id == tenant_id)
                )
                if not event:
                    return "fabricated_evidence_id"
                if not db.get(IncidentEvent, (tenant_id, incident_id, event_id)):
                    return "evidence_scope_mismatch"
        return None

    async def get_asset(self, asset_id, tenant_id):
        with self.sessions() as db:
            matches = []
            # Bounded inventory; incomplete inventory fails closed.
            rows = db.scalars(select(StoredAsset).where(StoredAsset.tenant_id == tenant_id).limit(20001)).all()
            if len(rows) > 20000:
                raise DependencyUnavailable("asset_inventory_limit_exceeded")
            for row in rows:
                p = row.payload
                if canonical(asset_id) in {canonical(x) for x in [row.asset_id, *p["addresses"], *p["aliases"]]}:
                    matches.append(Asset(tenant_id=tenant_id, **{k: v for k, v in p.items() if k != "data_mode"}))
            if len(matches) > 1:
                raise DependencyUnavailable("ambiguous_asset")
            return matches[0] if matches else None

    async def health(self):
        with self.sessions() as db:
            db.execute(text("SELECT 1 FROM incidents LIMIT 1"))
        return "healthy"
