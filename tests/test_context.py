from datetime import timedelta
import json

from app.ai.context.builder import build_context
from app.ai.context.selector import select_evidence
from app.config import Settings
from app.contracts import IncidentContext
import pytest


async def test_context_is_bounded_deterministic_and_diverse(setup):
    app, _, _ = setup
    context = await app.state.core.get_incident_context("SZ-000042", "lab")
    original = context.evidence[0]
    context.evidence = [
        original.model_copy(
            update={
                "event_uid": f"EVT-{i}",
                "source": "wazuh" if i % 2 else "cryptoguard",
                "event_time": original.event_time + timedelta(seconds=i),
            }
        )
        for i in range(200)
    ]
    selected = select_evidence(context.evidence, 10)
    assert len(selected) == 10
    assert {e.source for e in selected} == {"wazuh", "cryptoguard"}
    assert selected == select_evidence(list(reversed(context.evidence)), 10)
    result = build_context(context, Settings(_env_file=None, max_evidence=10, max_context_chars=5000))
    assert len(json.dumps(result["data"], ensure_ascii=False)) <= 5000
    assert result["omitted_evidence_count"] >= 190
    assert result["classification"] == "UNTRUSTED EVENT DATA"


async def test_context_contract_rejects_foreign_scope(setup):
    app, _, _ = setup
    value = (await app.state.core.get_incident_context("SZ-000042", "lab")).model_dump()
    value["evidence"][0]["tenant_id"] = "other"
    with pytest.raises(ValueError):
        IncidentContext.model_validate(value)


async def test_context_contract_rejects_duplicate_ids(setup):
    app, _, _ = setup
    value = (await app.state.core.get_incident_context("SZ-000042", "lab")).model_dump()
    value["evidence"] *= 2
    with pytest.raises(ValueError):
        IncidentContext.model_validate(value)
