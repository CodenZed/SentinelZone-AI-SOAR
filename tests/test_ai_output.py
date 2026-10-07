import json

import pytest

from app.ai.providers.mock import MockAIProvider
from app.ai.validation.output import parse_output
from app.errors import DependencyUnavailable
from tests.conftest import auth


@pytest.mark.parametrize("payload", ["not json", "```json\n{}\n```", {}, {"observed_facts": []}, '{"a":1,"a":2}'])
def test_malformed_output_rejected(payload):
    with pytest.raises(ValueError):
        parse_output(payload)


def test_normal_incident_valid_with_ordered_ledger(setup):
    _, client, tokens = setup
    response = client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens))
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "completed" and result["validation_status"] == "valid"
    assert result["trusted"]
    assert [s["stage"] for s in result["steps"]] == [
        "CONTEXT_BUILT",
        "REDACTED",
        "PROVIDER_CALLED",
        "OUTPUT_RECEIVED",
        "EVIDENCE_VALIDATED",
        "STORED",
    ]
    assert "UNKNOWN" in json.dumps(result["analysis"]["missing_evidence"])
    assert client.get(f"/v1/ai/runs/{result['run_id']}", headers=auth(tokens)).json()["analysis"] == result["analysis"]
    assert len(client.get("/v1/incidents/SZ-000042/analyses", headers=auth(tokens)).json()["items"]) == 1


def test_provider_unavailable_safe_and_ledger_persisted(setup):
    app, client, tokens = setup

    class Broken(MockAIProvider):
        async def analyze(self, context):
            raise DependencyUnavailable("DO_NOT_EXPOSE_PRIVATE_DETAIL")

    app.state.provider = Broken()
    result = client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens)).json()
    assert result["status"] == "failed" and result["error_code"] == "dependency_unavailable"
    assert not result["trusted"] and result["analysis"] is None
    assert "PRIVATE_DETAIL" not in json.dumps(result)
    assert result["steps"][-1]["stage"] == "FAILED"


def test_provider_malformed_json_rejected_and_not_stored_as_analysis(setup):
    app, client, tokens = setup

    class Broken(MockAIProvider):
        async def analyze(self, context):
            return '{"password":"CANARY"}'

    app.state.provider = Broken()
    result = client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens)).json()
    assert result["status"] == "rejected" and result["analysis"] is None
    assert "CANARY" not in json.dumps(result)
