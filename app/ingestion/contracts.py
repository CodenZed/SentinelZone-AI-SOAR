"""Immutable normalized input, with explicit origin and unknown values."""

from datetime import timezone
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, field_validator, model_validator
from app.contracts import Contract, Identifier, TelemetryContext, Text

Mode = Literal["REAL", "TEST", "REPLAY", "UNKNOWN"]
Severity = Literal["low", "medium", "high", "critical", "UNKNOWN"]
OriginText = Annotated[str, Field(min_length=1, max_length=500)]


class Origin(Contract):
    source_id: Identifier
    external_id: Identifier


class EventIn(Origin):
    event_time: AwareDatetime
    summary: str | None = Field(None, max_length=8000)
    priority: Severity = "UNKNOWN"
    data_mode: Mode = "UNKNOWN"
    provenance: dict[Identifier, OriginText] = Field(default_factory=dict, max_length=20)

    @field_validator("event_time")
    @classmethod
    def utc(cls, value):
        return value.astimezone(timezone.utc)


class IncidentIn(Origin):
    title: str = Field(min_length=1, max_length=300)
    summary: str | None = Field(None, max_length=8000)
    status: Literal["open", "investigating", "closed", "UNKNOWN"] = "UNKNOWN"
    priority: Severity = "UNKNOWN"
    data_mode: Mode = "UNKNOWN"
    events: list[Origin] = Field(default_factory=list, max_length=500)
    asset_ids: list[Identifier] = Field(default_factory=list, max_length=100)
    telemetry: list[TelemetryContext] = Field(default_factory=list, max_length=100)
    identity_context: list[Text] = Field(default_factory=list, max_length=100)
    missing_telemetry: list[Text] = Field(default_factory=list, max_length=100)
    provenance: dict[Identifier, OriginText] = Field(default_factory=dict, max_length=20)

    @model_validator(mode="after")
    def unique_links(self):
        if len({(e.source_id, e.external_id) for e in self.events}) != len(self.events):
            raise ValueError("duplicate event link")
        if len(set(self.asset_ids)) != len(self.asset_ids):
            raise ValueError("duplicate asset link")
        return self


class EventBatch(Contract):
    events: list[EventIn] = Field(min_length=1, max_length=100)


class IncidentBatch(Contract):
    incidents: list[IncidentIn] = Field(min_length=1, max_length=20)


class AssetIn(Contract):
    asset_id: Identifier
    criticality: Literal["low", "medium", "high", "critical", "unknown"] = "unknown"
    role: str | None = Field(None, max_length=100)
    addresses: list[Annotated[str, Field(max_length=128)]] = Field(default_factory=list, max_length=50)
    aliases: list[Identifier] = Field(default_factory=list, max_length=50)
    lab_asset: bool = False
    data_mode: Mode = "UNKNOWN"

    @model_validator(mode="after")
    def test_registration(self):
        if self.lab_asset and self.data_mode != "TEST":
            raise ValueError("test process asset must be TEST")
        return self
