"""UNVERIFIED skeleton. No vendor response fields or endpoints are invented."""

from app.connectors.base import Connector
from app.errors import DependencyUnavailable


class WazuhConnector(Connector):
    def normalize_events(self, payload):
        raise DependencyUnavailable("wazuh_contract_not_implemented")
