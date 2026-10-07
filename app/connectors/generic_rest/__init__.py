from app.connectors.base import Connector
from app.ingestion.contracts import EventBatch
from app.errors import ServiceError


class GenericRESTConnector(Connector):
    status = "PASS"

    def normalize_events(self, payload):
        if not self.config.enabled:
            raise ServiceError("connector_disabled", 403)
        batch = EventBatch.model_validate(payload)
        if any(e.source_id != self.config.source_id for e in batch.events):
            raise ServiceError("connector_source_mismatch", 422)
        return batch
