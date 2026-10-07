import hashlib
import json
from sqlalchemy.exc import IntegrityError
from app.db.models import IncidentEvent, StoredAsset, StoredEvent, StoredIncident, Tenant
from app.errors import ServiceError
from app.soar.proposals.service import audit


def stable_id(prefix, tenant, source, external):
    raw = json.dumps([tenant, source, external], separators=(",", ":")).encode()
    return prefix + "-" + hashlib.sha256(raw).hexdigest()


def ingest(db, principal, records, *, incidents=False):
    """Atomic, immutable batch; replay is safe, conflicting IDs never overwrite evidence."""
    if not db.get(Tenant, principal.tenant_id):
        raise ServiceError("tenant_not_registered", 409)
    model, prefix = (StoredIncident, "INC") if incidents else (StoredEvent, "EVT")
    results = []
    try:
        for item in records:
            payload = item.model_dump(mode="json")
            # Membership is a set; canonicalize before idempotency comparison.
            if incidents:
                payload["events"] = sorted(payload["events"], key=lambda e: (e["source_id"], e["external_id"]))
                payload["asset_ids"] = sorted(payload["asset_ids"])
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            identity = stable_id(prefix, principal.tenant_id, item.source_id, item.external_id)
            current = db.get(model, identity)
            if current:
                if current.content_hash != digest:
                    raise ServiceError("source_id_conflict", 409)
                results.append({"id": identity, "duplicate": True})
                continue
            linked = []
            if incidents:
                for origin in item.events:
                    event_id = stable_id("EVT", principal.tenant_id, origin.source_id, origin.external_id)
                    event = db.get(StoredEvent, event_id)
                    if not event or event.tenant_id != principal.tenant_id:
                        raise ServiceError("referenced_evidence_unavailable", 422)
                    if event.payload["data_mode"] != item.data_mode:
                        raise ServiceError("mixed_data_modes_forbidden", 422)
                    linked.append(event_id)
                for asset_id in item.asset_ids:
                    asset = db.get(StoredAsset, (principal.tenant_id, asset_id))
                    if not asset:
                        raise ServiceError("referenced_asset_unavailable", 422)
                    if asset.payload["data_mode"] != item.data_mode:
                        raise ServiceError("mixed_data_modes_forbidden", 422)
            db.add(
                model(
                    id=identity,
                    tenant_id=principal.tenant_id,
                    source_id=item.source_id,
                    external_id=item.external_id,
                    content_hash=digest,
                    payload=payload,
                )
            )
            db.flush()
            for event_id in linked:
                db.add(IncidentEvent(tenant_id=principal.tenant_id, incident_id=identity, event_id=event_id))
            results.append({"id": identity, "duplicate": False})
        audit(
            db,
            principal,
            "INCIDENTS_INGESTED" if incidents else "EVENTS_INGESTED",
            records=results,
            sources=sorted({r.source_id for r in records}),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent identical writer may have won. One bounded re-read, no dispatch retry.
        for item in records:
            identity = stable_id(prefix, principal.tenant_id, item.source_id, item.external_id)
            current = db.get(model, identity)
            payload = item.model_dump(mode="json")
            if incidents:
                payload["events"] = sorted(payload["events"], key=lambda e: (e["source_id"], e["external_id"]))
                payload["asset_ids"] = sorted(payload["asset_ids"])
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if not current or current.content_hash != digest:
                raise ServiceError("ingestion_conflict_retry_safe", 409) from None
        return [
            {"id": stable_id(prefix, principal.tenant_id, i.source_id, i.external_id), "duplicate": True}
            for i in records
        ]
    except Exception:
        db.rollback()
        raise
    return results
