"""Explicit REST mapping seam. No core imports, ORM, dynamic endpoints or raw-log passthrough."""

from pydantic import ValidationError

from app.contracts import Asset, Evidence, IncidentContext, TelemetryContext, TimelineItem
from app.ai.context.redactor import redact_text
from app.errors import DependencyUnavailable, ServiceError


class CoreContractMapper:
    def __init__(self, settings):
        self.settings = settings

    @staticmethod
    def document(value):
        if not isinstance(value, dict):
            raise DependencyUnavailable("invalid_core_contract")
        # Exactly one optional data envelope; no recursive guesswork.
        if "data" in value:
            if value.get("data_complete") is False or not isinstance(value["data"], dict):
                raise DependencyUnavailable("incomplete_core_contract")
            document = value["data"].copy()
            if "tenant_id" in value:
                if "tenant_id" in document and document["tenant_id"] != value["tenant_id"]:
                    raise DependencyUnavailable("core_scope_mismatch")
                document["tenant_id"] = value["tenant_id"]
            return document
        return value

    def scope(self, row, tenant_id):
        actual = row.get("tenant_id")
        if actual is None:
            if not (self.settings.core_single_tenant_ack and tenant_id == self.settings.core_tenant_id):
                raise DependencyUnavailable("core_tenant_missing")
        elif actual != tenant_id:
            # Indistinguishable from absent resource at the service boundary.
            raise ServiceError("incident_not_found", 404)

    @staticmethod
    def field(row, *names, default=None):
        values = [row[name] for name in names if name in row and row[name] is not None]
        if not values:
            return default
        if any(value != values[0] for value in values[1:]):
            raise DependencyUnavailable("ambiguous_core_contract")
        return values[0]

    @staticmethod
    def list_field(row, name):
        value = row.get(name)
        if value is None:
            return []
        if not isinstance(value, list):
            raise DependencyUnavailable("invalid_core_contract")
        return value.copy()

    def asset(self, row, tenant_id):
        self.scope(row, tenant_id)
        asset_id = self.field(row, "asset_id", "host_id")
        aliases = self.list_field(row, "aliases")
        if row.get("hostname"):
            aliases.append(row["hostname"])
        addresses = self.list_field(row, "addresses")
        if row.get("agent_ip"):
            addresses.append(row["agent_ip"])
        return Asset(
            asset_id=asset_id,
            tenant_id=tenant_id,
            role=row.get("role"),
            aliases=list(dict.fromkeys(aliases)),
            addresses=list(dict.fromkeys(addresses)),
            criticality=row.get("criticality") or "unknown",
            lab_asset=row.get("lab_asset") is True,
        )

    def context(self, incident, rows, assets, tenant_id):
        incident_id = self.field(incident, "incident_id", "id")
        evidence, history = {}, []
        for row in rows:
            if not isinstance(row, dict):
                raise DependencyUnavailable("invalid_timeline_contract")
            # Legacy timeline inherits verified parent scope; explicit scope may never conflict.
            if "tenant_id" in row:
                self.scope(row, tenant_id)
            if row.get("incident_id", incident_id) != incident_id:
                raise DependencyUnavailable("timeline_scope_mismatch")
            detail = row.get("detail", row)
            if not isinstance(detail, dict):
                raise DependencyUnavailable("invalid_timeline_contract")
            if "tenant_id" in detail:
                self.scope(detail, tenant_id)
            if detail.get("incident_id", incident_id) != incident_id:
                raise DependencyUnavailable("timeline_scope_mismatch")
            if row.get("kind") in {"event", "alert"}:
                event = Evidence(
                    event_uid=detail.get("event_uid"),
                    incident_id=incident_id,
                    tenant_id=tenant_id,
                    source=detail.get("original_sensor") or detail.get("source") or row.get("actor") or "unknown",
                    event_time=self.field(row, "timestamp", "ts", default=detail.get("event_time")),
                    summary=detail.get("summary") or "No summary supplied",
                    priority=detail.get("priority") or "medium",
                )
                if event.event_uid in evidence and evidence[event.event_uid] != event:
                    raise DependencyUnavailable("conflicting_timeline_evidence")
                evidence[event.event_uid] = event
            elif len(history) < 1000:
                # Deliberately do not serialize arbitrary detail/raw fields.
                history.append(
                    TimelineItem(
                        timestamp=self.field(row, "timestamp", "ts"),
                        kind=row.get("kind", "unknown"),
                        summary=redact_text(detail.get("summary") or row.get("summary") or "No summary supplied")[
                            :2000
                        ],
                    )
                )
        missing = self.list_field(incident, "missing_telemetry")
        identity = incident.get("identity_context") or []
        telemetry = []
        for raw in incident.get("telemetry") or []:
            # A versioned allowlist keeps command lines, environment and raw logs out.
            allowed = {k: v for k, v in raw.items() if k in TelemetryContext.model_fields}
            for field, keys in (
                ("processes", {"name", "pid", "cpu", "ram"}),
                ("network_connections", {"local_address", "remote_address", "state", "process_name"}),
            ):
                allowed[field] = [{k: v for k, v in item.items() if k in keys} for item in raw.get(field, [])[:30]]
            telemetry.append(TelemetryContext.model_validate(allowed))
        if not identity:
            missing.append("identity_context: UNKNOWN (not supplied by core)")
        if not telemetry:
            missing.append("sensor/host telemetry: UNKNOWN (not supplied by core)")
        if any(a.criticality == "unknown" for a in assets) or not assets:
            missing.append("asset criticality: UNKNOWN (not supplied by core)")
        return IncidentContext(
            incident_id=incident_id,
            tenant_id=tenant_id,
            status=incident["status"],
            priority=incident["priority"],
            summary=incident.get("summary") or incident.get("title") or "No summary supplied",
            assets=assets,
            evidence=list(evidence.values()),
            timeline=history,
            identity_context=identity,
            telemetry=telemetry,
            data_mode=incident.get("data_mode", "UNKNOWN"),
            correlation_reasons=self.field(incident, "correlation_reasons", "reason_codes", default=[]),
            missing_telemetry=list(dict.fromkeys(missing)),
        )


def contract_error(exc):
    """Never return upstream payloads or model validation details to clients."""
    if isinstance(exc, (ValidationError, KeyError, TypeError, ValueError, AttributeError)):
        return DependencyUnavailable("invalid_core_contract")
    return exc
