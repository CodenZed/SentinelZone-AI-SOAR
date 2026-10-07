import pytest

from app.ai.providers.mock import MockAIProvider
from tests.conftest import auth


@pytest.mark.parametrize(
    "event_id,reason",
    [
        ("EVT-FABRICATED", "fabricated_evidence_id"),
        ("EVT-OTHER", "evidence_scope_mismatch"),
        ("EVT-FOREIGN", "evidence_scope_mismatch"),
    ],
)
def test_invalid_citation_never_trusted(setup, event_id, reason):
    app, client, tokens = setup

    class Forged(MockAIProvider):
        async def analyze(self, context):
            result = await super().analyze(context)
            result["observed_facts"][0]["evidence_event_ids"] = [event_id]
            return result

    app.state.provider = Forged()
    result = client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens)).json()
    assert result["validation_status"] == "invalid"
    assert result["validation"]["reason"] == reason
    assert result["analysis"] is None and not result["trusted"]


def test_empty_citation_rejected(setup):
    app, client, tokens = setup

    class Forged(MockAIProvider):
        async def analyze(self, context):
            result = await super().analyze(context)
            result["observed_facts"][0]["evidence_event_ids"] = []
            return result

    app.state.provider = Forged()
    result = client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens)).json()
    assert result["status"] == "rejected" and not result["trusted"]
