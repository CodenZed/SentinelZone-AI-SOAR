from app.ai.providers.openai import OpenAIProvider
from app.soar.executors.base import UnavailableExecutor
from tests.conftest import approved, auth, propose
from tests.test_approval import zero_executions


def test_auth_and_tenant_isolation(setup):
    _, client, tokens = setup
    assert client.get("/v1/actions").status_code == 401
    pid = propose(client, tokens).json()["proposal_id"]
    assert client.get(f"/v1/actions/{pid}", headers=auth(tokens, "other")).status_code == 404
    assert client.get("/v1/actions", headers=auth(tokens, "other")).json()["items"] == []
    run = client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens)).json()
    assert client.get(f"/v1/ai/runs/{run['run_id']}", headers=auth(tokens, "other")).status_code == 404
    assert client.get("/v1/incidents/SZ-000042/analyses", headers=auth(tokens, "other")).json()["items"] == []


def test_health_degraded_missing_key_keeps_soar_available(setup):
    app, client, tokens = setup
    assert client.get("/health").json()["status"] == "healthy"
    app.state.provider = OpenAIProvider(app.state.settings)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "degraded" and health.json()["ai_provider"] == "unavailable"
    assert propose(client, tokens).status_code == 201


def test_unimplemented_real_executor_fails_closed(setup):
    app, client, tokens = setup
    pid = approved(client, tokens)
    app.state.executor = UnavailableExecutor("windows_firewall")
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).status_code == 503
    zero_executions(app)


def test_validation_errors_do_not_echo_request_secrets(setup):
    _, client, tokens = setup
    response = client.post("/v1/actions", json={"password": "CANARY"}, headers=auth(tokens))
    assert response.status_code == 422 and "CANARY" not in response.text
