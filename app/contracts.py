from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]
Text = Annotated[str, Field(min_length=1, max_length=2000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Asset(Contract):
    asset_id: Identifier
    tenant_id: Identifier
    criticality: str = "unknown"
    role: str | None = None
    addresses: list[str] = Field(default_factory=list, max_length=50)
    aliases: list[str] = Field(default_factory=list, max_length=50)
    lab_asset: bool = False


class Evidence(Contract):
    event_uid: Identifier
    incident_id: Identifier
    tenant_id: Identifier
    source: str = Field(max_length=100)
    event_time: AwareDatetime
    summary: str = Field(max_length=8000)
    priority: Literal["low", "medium", "high", "critical", "UNKNOWN"] = "UNKNOWN"
    data_classification: Literal["UNTRUSTED EVENT DATA"] = "UNTRUSTED EVENT DATA"


class TimelineItem(Contract):
    timestamp: AwareDatetime
    kind: str = Field(max_length=100)
    summary: str = Field(max_length=2000)


class ProcessSummary(Contract):
    name: str = Field(max_length=256)
    pid: int | None = Field(None, ge=0)
    cpu: float | None = None
    ram: float | None = None


class ConnectionSummary(Contract):
    local_address: str | None = Field(None, max_length=256)
    remote_address: str | None = Field(None, max_length=256)
    state: str | None = Field(None, max_length=100)
    process_name: str | None = Field(None, max_length=256)


class TelemetryContext(Contract):
    host: str = Field(max_length=256)
    platform: str | None = Field(None, max_length=100)
    agent_id: str | None = Field(None, max_length=128)
    cpu: float | None = None
    ram: float | None = None
    gpu: float | None = None
    temperature: float | None = None
    processes: list[ProcessSummary] = Field(default_factory=list, max_length=30)
    network_connections: list[ConnectionSummary] = Field(default_factory=list, max_length=30)
    persistence_observations: list[Text] = Field(default_factory=list, max_length=30)
    sensor_availability: dict[str, Literal["available", "unavailable", "unknown"]] = Field(
        default_factory=dict, max_length=30
    )
    security_risk: str | None = Field(None, max_length=100)
    resource_impact: str | None = Field(None, max_length=100)
    reasons: list[Text] = Field(default_factory=list, max_length=30)
    last_seen: AwareDatetime | None = None
    availability: Literal["available", "unavailable", "unknown"] = "unknown"


class IncidentContext(Contract):
    schema_version: Literal["1.0"] = "1.0"
    data_mode: Literal["REAL", "TEST", "REPLAY", "UNKNOWN"] = "UNKNOWN"
    telemetry: list[TelemetryContext] = Field(default_factory=list, max_length=100)
    incident_id: Identifier
    tenant_id: Identifier
    status: str = Field(max_length=100)
    priority: str = Field(max_length=100)
    summary: str = Field(max_length=8000)
    assets: list[Asset] = Field(default_factory=list, max_length=100)
    identity_context: list[Text] = Field(default_factory=list, max_length=100)
    timeline: list[TimelineItem] = Field(default_factory=list, max_length=1000)
    evidence: list[Evidence] = Field(default_factory=list, max_length=20000)
    correlation_reasons: list[Text] = Field(default_factory=list, max_length=100)
    missing_telemetry: list[Text] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def scope(self):
        if len({e.event_uid for e in self.evidence}) != len(self.evidence):
            raise ValueError("duplicate evidence")
        if any(e.tenant_id != self.tenant_id or e.incident_id != self.incident_id for e in self.evidence):
            raise ValueError("evidence scope mismatch")
        if any(a.tenant_id != self.tenant_id for a in self.assets):
            raise ValueError("asset scope mismatch")
        return self


class Fact(Contract):
    text: Text
    evidence_event_ids: list[Identifier] = Field(min_length=1, max_length=20)


class Hypothesis(Contract):
    text: Text
    limitations: Text


class AIOutput(Contract):
    observed_facts: list[Fact] = Field(max_length=50)
    hypotheses: list[Hypothesis] = Field(max_length=20)
    missing_evidence: list[Text] = Field(max_length=100)
    recommended_investigation: list[Text] = Field(max_length=30)
    containment_options: list[Text] = Field(max_length=20)


class AnalyzeIn(Contract):
    incident_id: Identifier


class ProposalIn(Contract):
    incident_id: Identifier
    action_type: Literal["BLOCK_IP", "SUSPEND_TEST_PROCESS"]
    target: str = Field(min_length=1, max_length=128)
    parameters: dict = Field(default_factory=dict)
    playbook_id: Identifier
    ttl_minutes: int = Field(default=60, ge=1, le=1440)


class ActionProposal(Contract):
    proposal_id: Identifier
    tenant_id: Identifier
    incident_id: Identifier
    action_type: Literal["BLOCK_IP", "SUSPEND_TEST_PROCESS"]
    target: str
    parameters: dict
    requested_by: str
    approved_by: str | None
    status: str
    expires_at: datetime
    rollback_available: bool
    dry_run: bool
    executor: str
    effect_scope: Literal["simulated", "live"]
    approval_status: Literal["pending", "approved", "rejected"]
    created_at: datetime
    playbook_id: str


class DecisionIn(Contract):
    reason: str = Field(default="", max_length=1000)


class Condition(Contract):
    field: Literal["action_type", "target", "parameters.lab_only"]
    equals: str | bool


class PlaybookStep(Contract):
    id: Identifier
    action: Literal[
        "validate_target",
        "human_approval",
        "windows_firewall_block",
        "suspend_test_process",
        "verify_block",
        "verify_process",
        "rollback_block",
        "rollback_process",
        "branch",
    ]
    depends_on: list[Identifier] = Field(default_factory=list, max_length=20)
    requires_approval: bool = False
    condition: Condition | None = None


class Playbook(Contract):
    id: Identifier
    name: Text
    version: str = Field(min_length=1, max_length=50)
    action_type: Literal["BLOCK_IP", "SUSPEND_TEST_PROCESS"]
    steps: list[PlaybookStep] = Field(min_length=5, max_length=30)
