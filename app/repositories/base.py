"""Context access port. Investigation and policy do not depend on a vendor API."""

from abc import ABC, abstractmethod


def canonical(value):
    import ipaddress

    value = value.strip().lower().rstrip(".")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return value


class EvidenceRepository(ABC):
    @abstractmethod
    async def get_incident_context(self, incident_id, tenant_id): ...

    @abstractmethod
    async def event_exists(self, event_uid): ...

    @abstractmethod
    async def get_asset(self, asset_id, tenant_id): ...

    async def event_belongs(self, event_uid, incident_id, tenant_id):
        context = await self.get_incident_context(incident_id, tenant_id)
        return any(e.event_uid == event_uid and e.tenant_id == tenant_id for e in context.evidence)

    async def validate_event_ids(self, ids, incident_id, tenant_id):
        for event_uid in ids:
            if not await self.event_exists(event_uid):
                return "fabricated_evidence_id"
            if not await self.event_belongs(event_uid, incident_id, tenant_id):
                return "evidence_scope_mismatch"
        return None

    async def health(self):
        return "healthy"

    async def close(self):
        pass
