"""Explicit one-incident import from the optional read-only adapter to product storage."""

from app.errors import ServiceError
from app.ingestion.contracts import EventIn, IncidentIn, Origin
from app.ingestion.service import ingest


async def import_incident(db, principal, client, incident_id, source_id):
    if client.settings.core_single_tenant_ack:
        raise ServiceError("standalone_import_requires_explicit_upstream_tenant", 403)
    context = await client.get_incident_context(incident_id, principal.tenant_id)
    reason = await client.validate_event_ids([e.event_uid for e in context.evidence], incident_id, principal.tenant_id)
    if reason:
        raise ServiceError(reason, 422)
    events = [
        EventIn(
            source_id=source_id,
            external_id=e.event_uid,
            event_time=e.event_time,
            summary=e.summary,
            priority=e.priority,
            data_mode=context.data_mode,
            provenance={"connector": "sentinelzone", "original_sensor": e.source},
        )
        for e in context.evidence
    ]
    if events:
        ingest(db, principal, events)
    # Inventory must be independently reviewed and registered by an administrator.
    incident = IncidentIn(
        source_id=source_id,
        external_id=incident_id,
        title=context.summary[:300] or incident_id,
        summary=context.summary,
        data_mode=context.data_mode,
        status=context.status if context.status in {"open", "closed", "investigating"} else "UNKNOWN",
        priority=context.priority if context.priority in {"low", "medium", "high", "critical"} else "UNKNOWN",
        events=[Origin(source_id=source_id, external_id=e.event_uid) for e in context.evidence],
        telemetry=context.telemetry,
        identity_context=context.identity_context,
        missing_telemetry=[*context.missing_telemetry, "Imported asset inventory requires administrator registration"],
        provenance={"connector": "sentinelzone", "upstream_incident_id": incident_id},
    )
    return ingest(db, principal, [incident], incidents=True)
