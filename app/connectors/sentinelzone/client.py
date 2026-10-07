"""Optional read-only SentinelZone adapter and explicit regression fixtures."""
import json
from urllib.parse import quote
from app.contracts import Asset, IncidentContext
from app.connectors.sentinelzone.mapping import CoreContractMapper, contract_error
from app.connectors.http import http_client, json_request
from app.errors import DependencyUnavailable, ServiceError
from app.repositories.base import EvidenceRepository, canonical

CoreBackendClient = EvidenceRepository

class MockCoreBackendClient(CoreBackendClient):
    def __init__(self, fixture_dir):
        self.contexts = {}
        for path in sorted((fixture_dir / "incidents").glob("*.json")):
            context = IncidentContext.model_validate(json.loads(path.read_text(encoding="utf-8")))
            self.contexts[(context.tenant_id, context.incident_id)] = context
        self.assets = [
            Asset.model_validate(a) for a in json.loads((fixture_dir / "assets.json").read_text(encoding="utf-8"))
        ]

    async def get_incident_context(self, incident_id, tenant_id):
        value = self.contexts.get((tenant_id, incident_id))
        if value is None:
            raise ServiceError("incident_not_found", 404)
        return value.model_copy(deep=True)

    async def event_exists(self, event_uid):
        return any(e.event_uid == event_uid for c in self.contexts.values() for e in c.evidence)

    async def get_asset(self, asset_id, tenant_id):
        matches = [
            a
            for a in self.assets
            if a.tenant_id == tenant_id
            and canonical(asset_id) in {canonical(x) for x in [a.asset_id, *a.addresses, *a.aliases]}
        ]
        if len(matches) > 1:
            raise DependencyUnavailable("ambiguous_asset")
        return matches[0].model_copy(deep=True) if matches else None


class RealCoreBackendClient(CoreBackendClient):
    """Authenticated, read-only REST; upstream shapes live exclusively in the mapper."""

    def __init__(self, settings, transport=None, mapper=None):
        self.settings = settings
        if not settings.core_api_token:
            raise DependencyUnavailable("core_unconfigured")
        self.mapper = mapper or CoreContractMapper(settings)
        self.client = http_client(
            settings.core_api_url, settings.core_api_token, settings, settings.core_api_ca_file, transport
        )

    def check_tenant(self, tenant_id):
        if tenant_id != self.settings.core_tenant_id:
            raise ServiceError("incident_not_found", 404)

    @staticmethod
    def identifier(value):
        import re

        if not isinstance(value, str) or value in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
            raise ServiceError("invalid_resource_identifier", 422)
        return quote(value, safe="")

    async def get(self, path, **kwargs):
        value = await json_request(self.client, "GET", path, limit=self.settings.max_response_bytes, **kwargs)
        return self.mapper.document(value) if value is not None else None

    async def pages(self, path, label):
        cursor, seen, rows = None, set(), []
        for _ in range(self.settings.core_max_pages):
            value = await self.get(path, params={"limit": 500, **({"cursor": cursor} if cursor else {})})
            if not isinstance(value, dict) or not isinstance(value.get("items"), list):
                raise DependencyUnavailable(f"invalid_{label}_contract")
            if "tenant_id" in value:
                self.mapper.scope(value, self.settings.core_tenant_id)
            if value.get("data_complete") is False:
                raise DependencyUnavailable(f"{label}_pagination_incomplete")
            rows.extend(value["items"])
            if len(rows) > self.settings.core_max_items:
                raise DependencyUnavailable(f"{label}_pagination_incomplete")
            cursor = value.get("next_cursor")
            if cursor is None or cursor == "":
                return rows
            if not isinstance(cursor, str) or len(cursor) > 2048 or cursor in seen:
                break
            seen.add(cursor)
        raise DependencyUnavailable(f"{label}_pagination_incomplete")

    async def get_incident_context(self, incident_id, tenant_id):
        self.check_tenant(tenant_id)
        try:
            path = f"v1/incidents/{self.identifier(incident_id)}"
            incident = await self.get(path)
            if incident is None:
                raise ServiceError("incident_not_found", 404)
            self.mapper.scope(incident, tenant_id)
            if self.mapper.field(incident, "id", "incident_id") != incident_id:
                raise DependencyUnavailable("core_scope_mismatch")
            if incident.get("data_complete") is False:
                raise DependencyUnavailable("core_context_incomplete")
            rows = await self.pages(path + "/timeline", "timeline")
            asset_id = self.mapper.field(incident, "asset_id", "host_id")
            asset = await self.get_asset(asset_id, tenant_id) if asset_id else None
            return self.mapper.context(incident, rows, [asset] if asset else [], tenant_id)
        except Exception as exc:
            raise contract_error(exc) from None

    async def event_exists(self, event_uid):
        value = await self.get(f"v1/alerts/{self.identifier(event_uid)}")
        if value is None:
            return False
        self.mapper.scope(value, self.settings.core_tenant_id)
        return value.get("event_uid") == event_uid

    async def event_belongs(self, event_uid, incident_id, tenant_id):
        self.check_tenant(tenant_id)
        event = await self.get(f"v1/alerts/{self.identifier(event_uid)}")
        if event is None or event.get("event_uid") != event_uid:
            return False
        self.mapper.scope(event, tenant_id)
        if "incident_id" in event and event["incident_id"] != incident_id:
            return False
        if "incident_ids" in event and incident_id not in event["incident_ids"]:
            return False
        return await super().event_belongs(event_uid, incident_id, tenant_id)

    async def validate_event_ids(self, ids, incident_id, tenant_id):
        self.check_tenant(tenant_id)
        if not ids:
            return None
        # Re-fetch membership once, then verify each selected alert independently.
        current = await self.get_incident_context(incident_id, tenant_id)
        linked = {e.event_uid for e in current.evidence}
        for event_uid in ids:
            event = await self.get(f"v1/alerts/{self.identifier(event_uid)}")
            if not event or event.get("event_uid") != event_uid:
                return "fabricated_evidence_id"
            self.mapper.scope(event, tenant_id)
            if (
                event_uid not in linked
                or ("incident_id" in event and event["incident_id"] != incident_id)
                or (
                    "incident_ids" in event
                    and (not isinstance(event["incident_ids"], list) or incident_id not in event["incident_ids"])
                )
            ):
                return "evidence_scope_mismatch"
        return None

    async def get_asset(self, asset_id, tenant_id):
        self.check_tenant(tenant_id)
        try:
            matches = {}
            for row in await self.pages("v1/assets", "asset"):
                asset = self.mapper.asset(row, tenant_id)
                values = [asset.asset_id, *asset.addresses, *asset.aliases]
                if canonical(asset_id) in {canonical(v) for v in values}:
                    if asset.asset_id in matches and matches[asset.asset_id] != asset:
                        raise DependencyUnavailable("ambiguous_asset")
                    matches[asset.asset_id] = asset
            if len(matches) > 1:
                raise DependencyUnavailable("ambiguous_asset")
            return next(iter(matches.values()), None)
        except Exception as exc:
            raise contract_error(exc) from None

    async def health(self):
        data = await self.get("health")
        return "healthy" if data and data.get("status") in {"ok", "healthy"} else "degraded"

    async def close(self):
        await self.client.aclose()
