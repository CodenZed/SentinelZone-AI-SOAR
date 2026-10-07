from abc import ABC, abstractmethod
from pydantic import Field, SecretStr
from app.contracts import Contract, Identifier


class ConnectorConfig(Contract):
    source_id: Identifier
    enabled: bool = False
    endpoint: str = Field("", max_length=2048)
    credential: SecretStr = Field(default=SecretStr(""), exclude=True)
    ca_file: str = ""
    contract_version: str = ""


class Connector(ABC):
    status = "UNVERIFIED"

    def __init__(self, config: ConnectorConfig):
        self.config = config

    @abstractmethod
    def normalize_events(self, payload): ...
