import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.config import ROOT, Settings
from app.main import create_app
from app.db.models import BrowserSession, StoredEvent, StoredIncident, User, utcnow
from app.security.auth import create_user
from tests.conftest import migrate


@pytest.fixture
def standalone(tmp_path):
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'product.db'}",
        core_mode="standalone",
        bootstrap_token="synthetic-bootstrap-" + "x" * 32,
        cookie_secure=False,
        enable_demo=True,
    )
    migrate(settings.database_url)
    app = create_app(settings)
    with TestClient(app) as client:
        yield app, client, settings


def bootstrap(client, settings):
    return client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_id": "acme",
            "name": "owner",
            "password": "unique-long-owner-password",
            "bootstrap_token": settings.bootstrap_token,
        },
    )


def token_users(app):
    with app.state.sessions() as db:
        return {
            role: {"Authorization": "Bearer " + create_user(db, role, role, "acme")}
            for role in ("viewer", "analyst", "operator", "admin")
        }


def event(external="external-1", **kw):
    return {
        "source_id": "sensor",
        "external_id": external,
        "event_time": "2026-01-01T16:00:00+04:00",
        "summary": "Observation with UNKNOWN process context",
        "data_mode": "TEST",
        **kw,
    }


def incident(**kw):
    return {
        "source_id": "sensor",
        "external_id": "case-1",
        "title": "Selected investigation",
        "data_mode": "TEST",
        "events": [{"source_id": "sensor", "external_id": "external-1"}],
        **kw,
    }


def seed(client, headers):
    e = client.post("/v1/ingest/events", json={"events": [event()]}, headers=headers)
    assert e.status_code == 201, e.text
    i = client.post("/v1/ingest/incidents", json={"incidents": [incident()]}, headers=headers)
    assert i.status_code == 201, i.text
    return e.json()["items"][0]["id"], i.json()["items"][0]["id"]


def test_fresh_standalone_no_core_or_fixture_dependency(standalone):
    app, c, s = standalone
    assert s.core_tenant_id == ""
    assert c.get("/health").json()["core_mode"] == "standalone"
    assert c.get("/v1/auth/bootstrap-status").json()["available"]
    assert bootstrap(c, s).status_code == 201
    assert bootstrap(c, s).status_code == 409
    with app.state.sessions() as db:
        assert not db.scalars(select(StoredIncident)).all()


def test_password_cookie_csrf_logout_and_role_separation(standalone):
    app, c, s = standalone
    bootstrap(c, s)
    login = c.post(
        "/v1/auth/login", json={"tenant_id": "acme", "name": "owner", "password": "unique-long-owner-password"}
    )
    assert login.status_code == 200
    assert "HttpOnly" in login.headers.get_list("set-cookie")[0]
    assert "sz_session" not in login.text
    body = {"name": "investigator", "role": "analyst", "password": "another-unique-long-password"}
    assert c.post("/v1/users", json=body).status_code == 403
    csrf = {"x-csrf-token": c.cookies.get("sz_csrf")}
    assert c.post("/v1/users", json=body, headers=csrf).status_code == 201
    assert c.post("/v1/ai/analyze", json={"incident_id": "anything"}, headers=csrf).status_code == 403
    assert c.post("/v1/users", json=body, headers={**csrf, "origin": "https://evil.invalid"}).status_code == 403
    assert c.post("/v1/auth/logout", headers=csrf).status_code == 200
    assert c.get("/v1/auth/me").status_code == 401
    with app.state.sessions() as db:
        u = db.scalar(select(User).where(User.name == "owner"))
        assert u.password_hash.startswith("pbkdf2_sha256$600000$")
        assert "unique-long" not in u.password_hash


def test_login_throttle_and_expired_session(standalone):
    app, c, s = standalone
    bootstrap(c, s)
    body = {"tenant_id": "acme", "name": "owner", "password": "wrong"}
    for _ in range(10):
        assert c.post("/v1/auth/login", json=body).status_code == 401
    assert c.post("/v1/auth/login", json=body).status_code == 429
    with app.state.sessions() as db:
        from app.db.models import LoginThrottle

        for row in db.scalars(select(LoginThrottle)):
            row.reset_at = utcnow() - timedelta(seconds=1)
        db.commit()
    body["password"] = "unique-long-owner-password"
    assert c.post("/v1/auth/login", json=body).status_code == 200
    with app.state.sessions() as db:
        for row in db.scalars(select(BrowserSession)):
            row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert c.get("/v1/auth/me").status_code == 401


def test_ingestion_scope_duplicate_conflict_provenance_utc(standalone):
    app, c, _ = standalone
    h = token_users(app)
    eid, iid = seed(c, h["analyst"])
    again = c.post("/v1/ingest/events", json={"events": [event()]}, headers=h["analyst"])
    assert again.json()["items"] == [{"id": eid, "duplicate": True}]
    assert (
        c.post("/v1/ingest/events", json={"events": [event(summary="different")]}, headers=h["analyst"]).status_code
        == 409
    )
    duplicate = c.post("/v1/ingest/incidents", json={"incidents": [incident()]}, headers=h["analyst"])
    assert duplicate.json()["items"][0]["duplicate"]
    data = c.get("/v1/events/" + eid, headers=h["viewer"]).json()
    assert data["external_id"] == "external-1" and data["source_id"] == "sensor"
    assert data["event_time"].endswith("Z") and data["priority"] == "UNKNOWN"
    assert data["received_at"].endswith("Z") and len(data["content_hash"]) == 64
    with app.state.sessions() as db:
        foreign = {"Authorization": "Bearer " + create_user(db, "foreign", "analyst", "other")}
    assert c.get("/v1/events/" + eid, headers=foreign).status_code == 404
    assert c.get("/v1/incidents/" + iid, headers=foreign).status_code == 404
    assert c.get("/v1/events", headers=foreign).json()["items"] == []
    for role in ("viewer", "admin", "operator"):
        assert c.post("/v1/ingest/events", json={"events": [event()]}, headers=h[role]).status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"events": []},
        {"events": [event(event_time="2026-01-01T00:00:00")]},
        {"events": [event(tenant_id="other")]},
        {"events": [event(source_id="")]},
        {"events": [event(summary="x" * 8001)]},
    ],
)
def test_invalid_ingestion_structured_error(standalone, payload):
    app, c, _ = standalone
    h = token_users(app)["analyst"]
    response = c.post("/v1/ingest/events", json=payload, headers=h)
    assert response.status_code == 422 and response.json()["detail"]["code"] == "validation_error"


def test_ingestion_atomic_modes_membership_and_bounds(standalone):
    app, c, _ = standalone
    h = token_users(app)["analyst"]
    eid, iid = seed(c, h)
    assert (
        c.post(
            "/v1/ingest/incidents", json={"incidents": [incident(external_id="mixed", data_mode="REAL")]}, headers=h
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/v1/ingest/incidents",
            json={
                "incidents": [incident(external_id="absent", events=[{"source_id": "sensor", "external_id": "absent"}])]
            },
            headers=h,
        ).status_code
        == 422
    )
    result = c.post("/v1/ingest/events", json={"events": [event("new"), event(summary="conflict")]}, headers=h)
    assert result.status_code == 409
    assert len(c.get("/v1/events", headers=h).json()["items"]) == 1
    assert (
        c.post("/v1/ingest/events", content=b"x" * 64001, headers={**h, "content-type": "application/json"}).status_code
        == 413
    )


def test_concurrent_duplicate_ingestion(standalone):
    app, c, _ = standalone
    h = token_users(app)["analyst"]

    def call(_):
        return c.post("/v1/ingest/events", json={"events": [event()]}, headers=h)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(call, range(4)))
    assert all(r.status_code == 201 for r in results), [r.text for r in results]
    with app.state.sessions() as db:
        assert len(db.scalars(select(StoredEvent)).all()) == 1


def test_standalone_ai_soar_full_workflow_and_restart(standalone):
    app, c, s = standalone
    h = token_users(app)
    eid, iid = seed(c, h["analyst"])
    run = c.post("/v1/ai/analyze", json={"incident_id": iid}, headers=h["analyst"]).json()
    assert run["status"] == "completed" and run["trusted"] and run["data_mode"] == "TEST"
    assert run["citations"][0]["event_uid"] == eid
    assert any("UNKNOWN" in x for x in run["missing_evidence"])
    body = {"incident_id": iid, "action_type": "BLOCK_IP", "target": "192.0.2.25", "playbook_id": "SZ-PB-001"}
    action = c.post("/v1/actions", json=body, headers=h["analyst"])
    assert action.status_code == 201, action.text
    pid = action.json()["proposal_id"]
    assert c.post(f"/v1/actions/{pid}/approve", json={}, headers=h["admin"]).status_code == 403
    assert c.post(f"/v1/actions/{pid}/approve", json={}, headers=h["operator"]).status_code == 200
    executed = c.post(f"/v1/actions/{pid}/execute", headers=h["operator"]).json()
    assert executed["dry_run"] and executed["verification_result"] is True
    restarted = create_app(s)
    with TestClient(restarted) as other:
        assert other.post(f"/v1/actions/{pid}/execute", headers=h["operator"]).status_code == 409
        rollback = other.post(f"/v1/actions/{pid}/rollback", headers=h["operator"]).json()
        assert rollback["restoration_verified"] and rollback["status"] == "RESTORED"
    assert len(c.get("/v1/audit", headers=h["viewer"]).json()["items"]) >= 7


def test_demo_idempotent_disabled_by_default(standalone):
    app, c, s = standalone
    h = token_users(app)["analyst"]
    for _ in range(2):
        assert c.post("/v1/demo", headers=h).status_code == 201
    assert len(c.get("/v1/events", headers=h).json()["items"]) == 2
    assert {x["data_mode"] for x in c.get("/v1/incidents", headers=h).json()["items"]} == {"TEST"}
    s.enable_demo = False
    assert c.post("/v1/demo", headers=h).status_code == 403
    assert Settings(_env_file=None).enable_demo is False


def test_generic_connectors_and_vendor_skeletons():
    from app.connectors.base import ConnectorConfig
    from app.connectors.generic_rest import GenericRESTConnector
    from app.connectors.webhook import WebhookConnector
    from app.connectors.wazuh import WazuhConnector
    from app.connectors.splunk import SplunkConnector
    from app.errors import ServiceError

    config = ConnectorConfig(source_id="sensor", enabled=True)
    for cls in (GenericRESTConnector, WebhookConnector):
        assert cls(config).normalize_events({"events": [event()]}).events[0].source_id == "sensor"
        with pytest.raises(ServiceError):
            cls(config).normalize_events({"events": [event(source_id="other")]})
    for cls in (WazuhConnector, SplunkConnector):
        with pytest.raises(ServiceError):
            cls(config).normalize_events({})


async def test_ollama_mock_contract_no_tools_or_thinking():
    from app.ai.providers.ollama import OllamaProvider

    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(
            200, json={"done": True, "done_reason": "stop", "message": {"content": "{}", "thinking": "DO_NOT_STORE"}}
        )

    provider = OllamaProvider(
        Settings(_env_file=None, ollama_url="https://ollama.example.invalid", ollama_model="test"),
        httpx.MockTransport(handler),
    )
    assert await provider.analyze({"classification": "UNTRUSTED EVENT DATA"}) == "{}"
    assert "tools" not in calls[0] and calls[0]["format"]["type"] == "object"
    await provider.close()


def test_production_standalone_config_arbitrary_dedicated_db():
    s = Settings(
        _env_file=None, app_env="production", database_url="postgresql+psycopg://product_role@database/product_db"
    )
    assert s.core_mode == "standalone" and not s.core_api_url and not s.core_tenant_id


def test_ui_contract_and_no_shared_token():
    source = (ROOT / "frontend/src/app.mjs").read_text(encoding="utf-8")
    assert "localStorage" not in source and "sessionStorage" not in source
    assert "Simulation" in source and "semantic proof" in source
    for route in ("/v1/ingest/events", "/v1/auth/login", "/v1/incidents", "/v1/audit"):
        assert route in create_app(Settings(_env_file=None)).openapi()["paths"]
