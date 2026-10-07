import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.ai.context.redactor import redact
from app.config import Settings
from app.connectors.core_backend import RealCoreBackendClient
from app.connectors.http import http_client
from app.db.models import Approval, Execution, Proposal, User, utcnow
from app.errors import DependencyUnavailable, ServiceError
from app.main import create_app
from app.security.auth import hash_token
from app.soar.executors.dry_run import DryRunExecutor
from app.soar.executors.factory import build_executor
from tests.conftest import approved, auth, propose
from tests.test_adapters import core_handler


def settings(**kw):
    return Settings(
        _env_file=None,
        **{
            "core_tenant_id": "lab",
            "core_mode": "real",
            "core_api_url": "https://core.example.invalid",
            "core_api_token": "synthetic-contract-only",
            **kw,
        },
    )


def tenant_handler(request):
    response = core_handler(request)
    if response.status_code != 200:
        return response
    value = response.json()
    if request.url.path == "/v1/assets":
        for row in value["items"]:
            row["tenant_id"] = "lab"
    elif "/timeline" not in request.url.path:
        value["tenant_id"] = "lab"
    return httpx.Response(200, json=value)


async def test_tenant_aware_core_without_legacy_ack():
    calls = []

    def handler(request):
        calls.append(request)
        return tenant_handler(request)

    core = RealCoreBackendClient(settings(), httpx.MockTransport(handler))
    try:
        context = await core.get_incident_context("SZ-000042", "lab")
        assert context.tenant_id == "lab"
        assert await core.event_exists("EVT-001")
        assert await core.event_belongs("EVT-001", "SZ-000042", "lab")
        assert all(r.method == "GET" and r.headers["authorization"] == "Bearer synthetic-contract-only" for r in calls)
    finally:
        await core.close()


async def test_missing_tenant_requires_explicit_ack():
    core = RealCoreBackendClient(settings(), httpx.MockTransport(core_handler))
    with pytest.raises(DependencyUnavailable, match="core_tenant_missing"):
        await core.get_incident_context("SZ-000042", "lab")
    await core.close()
    settings(core_single_tenant_ack=True, core_tenant_id="customer")


@pytest.mark.parametrize("resource", ["incident", "alert", "asset", "timeline", "detail"])
async def test_explicit_foreign_tenant_never_overridden_by_ack(resource):
    def handler(request):
        response = core_handler(request)
        value = response.json()
        if resource == "incident" and request.url.path == "/v1/incidents/SZ-000042":
            value["tenant_id"] = "foreign"
        elif resource == "alert" and "/alerts/" in request.url.path:
            value["tenant_id"] = "foreign"
        elif resource == "asset" and request.url.path == "/v1/assets":
            value["items"][0]["tenant_id"] = "foreign"
        elif resource in {"timeline", "detail"} and "/timeline" in request.url.path:
            item = value["items"][0]
            (item["detail"] if resource == "detail" else item)["tenant_id"] = "foreign"
        return httpx.Response(200, json=value)

    core = RealCoreBackendClient(settings(core_single_tenant_ack=True), httpx.MockTransport(handler))
    with pytest.raises(ServiceError) as error:
        if resource == "alert":
            await core.event_exists("EVT-001")
        else:
            await core.get_incident_context("SZ-000042", "lab")
    assert error.value.status == 404
    await core.close()


async def test_normalized_mapping_telemetry_drops_raw_fields():
    def handler(request):
        value = tenant_handler(request).json()
        if request.url.path == "/v1/incidents/SZ-000042":
            value["incident_id"] = value.pop("id")
            value["asset_id"] = value.pop("host_id")
            value["summary"] = "Real response shape contract; synthetic input"
            value["correlation_reasons"] = value.pop("reason_codes")
            value["identity_context"] = ["identity enrichment available"]
            value["data_mode"] = "REAL"
            value["telemetry"] = [
                {
                    "host": "CLIENT01",
                    "platform": "Windows",
                    "agent_id": "CG-01",
                    "cpu": 15.5,
                    "ram": 42,
                    "gpu": None,
                    "temperature": None,
                    "processes": [{"name": "test-worker", "pid": 7, "command_line": "RAW_CANARY"}],
                    "network_connections": [{"remote_address": "192.0.2.10:443", "raw": "RAW_CANARY"}],
                    "persistence_observations": ["No conclusion available"],
                    "sensor_availability": {"gpu": "unavailable", "processes": "available"},
                    "security_risk": "unknown",
                    "resource_impact": "low",
                    "reasons": [],
                    "last_seen": "2026-01-01T12:00:00Z",
                    "availability": "available",
                    "raw_logs": "RAW_CANARY",
                }
            ]
        elif request.url.path == "/v1/assets":
            for row in value["items"]:
                row["asset_id"] = row.pop("host_id")
                row["aliases"] = ["endpoint-alias"] if row["asset_id"] == "CLIENT01" else []
                row["lab_asset"] = True
        elif "/timeline" in request.url.path:
            row = value["items"][0]
            row["timestamp"] = row.pop("ts")
            row["detail"]["original_sensor"] = "wazuh"
            row["detail"]["source"] = "splunk"
            row["detail"]["raw"] = "RAW_CANARY"
        return httpx.Response(200, json={"data": value})

    core = RealCoreBackendClient(settings(), httpx.MockTransport(handler))
    context = await core.get_incident_context("SZ-000042", "lab")
    assert context.telemetry[0].gpu is None and context.telemetry[0].temperature is None
    assert context.telemetry[0].cpu == 15.5
    assert "RAW_CANARY" not in context.model_dump_json()
    assert context.data_mode == "REAL" and context.evidence[0].source == "wazuh"
    assert (await core.get_asset("endpoint-alias", "lab")).asset_id == "CLIENT01"
    await core.close()


@pytest.mark.parametrize("damage", ["cycle", "incomplete", "wrong_incident", "malformed"])
async def test_incomplete_or_wrong_timeline_fails_closed(damage):
    def handler(request):
        if "/timeline" not in request.url.path:
            return core_handler(request)
        value = core_handler(request).json()
        if damage == "cycle":
            value["next_cursor"] = "repeat"
        elif damage == "incomplete":
            value["data_complete"] = False
        elif damage == "wrong_incident":
            value["items"][0]["detail"]["incident_id"] = "OTHER"
        else:
            value["items"] = [None]
        return httpx.Response(200, json=value)

    core = RealCoreBackendClient(settings(core_single_tenant_ack=True), httpx.MockTransport(handler))
    with pytest.raises(DependencyUnavailable):
        await core.get_incident_context("SZ-000042", "lab")
    await core.close()


async def test_timeline_pagination_collects_evidence_on_later_page():
    def handler(request):
        if "/timeline" not in request.url.path:
            return core_handler(request)
        if "cursor" not in request.url.params:
            return httpx.Response(200, json={"items": [], "next_cursor": "page2"})
        return core_handler(request)

    core = RealCoreBackendClient(settings(core_single_tenant_ack=True), httpx.MockTransport(handler))
    assert len((await core.get_incident_context("SZ-000042", "lab")).evidence) == 1
    await core.close()


async def test_alert_wrong_incident_invalidates_membership():
    def handler(request):
        if "/alerts/" in request.url.path:
            return httpx.Response(200, json={"event_uid": "EVT-001", "incident_id": "OTHER"})
        return core_handler(request)

    core = RealCoreBackendClient(settings(core_single_tenant_ack=True), httpx.MockTransport(handler))
    assert not await core.event_belongs("EVT-001", "SZ-000042", "lab")
    await core.close()


@pytest.mark.parametrize("identifier", [".", "..", "a/b", "?x=y", "%2f", "a#b"])
async def test_no_path_injection(identifier):
    calls = []
    core = RealCoreBackendClient(settings(), httpx.MockTransport(lambda r: calls.append(r)))
    with pytest.raises(ServiceError):
        await core.get_incident_context(identifier, "lab")
    assert not calls
    await core.close()


@pytest.mark.parametrize("url", ["http://public.invalid", "http://10.0.0.1", "http://127.0.0.2"])
def test_insecure_http_requires_explicit_dev_host(url):
    with pytest.raises(DependencyUnavailable):
        http_client(url, "", Settings(_env_file=None, core_tenant_id="lab", allow_insecure_http=True))


async def test_loopback_http_and_explicit_dev_host_allowed():
    for url, trusted in [("http://127.0.0.1:8081", ""), ("http://upstream.example.invalid:8081", "upstream.example.invalid")]:
        client = http_client(url, "", Settings(_env_file=None, core_tenant_id="lab", allow_insecure_http=True, trusted_http_hosts=trusted))
        assert client.follow_redirects is False
        await client.aclose()


def test_production_config_has_separate_db_role_and_no_fixtures():
    good = dict(
        app_env="production",
        core_mode="real",
        database_url="postgresql+psycopg://sentinelzone_ai_soar@localhost/sentinelzone_ai_soar",
    )
    assert Settings(_env_file=None, core_tenant_id="lab", **good)
    for override in [
        dict(core_mode="mock"),
        dict(database_url="sqlite:///main.db"),
        dict(database_url="postgresql+psycopg://postgres@localhost/product"),
        dict(database_url="postgresql+psycopg://localhost/product"),
    ]:
        with pytest.raises(ValueError):
            Settings(_env_file=None, core_tenant_id="lab", **{**good, **override})
    production = Settings(_env_file=None, core_tenant_id="lab", **good, allow_insecure_http=True, trusted_http_hosts="core.lab.invalid")
    with pytest.raises(DependencyUnavailable):
        http_client("http://core.lab.invalid:8003", "", production)


@pytest.mark.parametrize(
    "provider,kwargs",
    [
        ("openai", {"openai_api_url": "http://public.invalid"}),
        ("local", {"local_ai_url": "https://local.invalid", "local_ai_ca_file": "/missing/ca.pem"}),
    ],
)
def test_bad_provider_configuration_degrades_service(setup, provider, kwargs):
    app, _, _ = setup
    updated = Settings(_env_file=None, core_tenant_id="lab", database_url=app.state.settings.database_url, ai_provider=provider, **kwargs)
    other = create_app(updated)
    with TestClient(other) as client:
        value = client.get("/health")
        assert value.status_code == 200
        assert value.json()["ai_provider"] == "unavailable"


def test_core_credential_never_accepted_as_service_token_even_if_hash_inserted(setup):
    app, client, tokens = setup
    app.state.settings.core_api_token = tokens["analyst"]
    with app.state.sessions() as db:
        assert db.scalar(select(User).where(User.token_hash == hash_token(tokens["analyst"])))
    assert client.get("/v1/actions", headers=auth(tokens)).status_code == 401


@pytest.mark.parametrize(
    "value",
    [
        "https://test.invalid/?%70assword=REDACTION_CANARY",
        "API key=REDACTION_CANARY",
        "passphrase=REDACTION_CANARY",
        {"smtp_credentials": "REDACTION_CANARY"},
    ],
)
def test_additional_secret_formats(value):
    assert "REDACTION_CANARY" not in json.dumps(redact(value))


@pytest.mark.parametrize(
    "target",
    [
        "192.0.2.10 ",
        "192.0.2.10.",
        "2001:0db8::1",
        "2001:DB8::1",
        "2001:db8::1%eth0",
        "0192.0.2.10",
        "https://192.0.2.10",
        "192.0.2.0/24",
    ],
)
def test_block_ip_rejects_noncanonical_or_nonliteral_target(setup, target):
    _, client, tokens = setup
    assert propose(client, tokens, target=target).status_code == 422


def test_canonical_ipv6_is_allowed_in_simulator(setup):
    _, client, tokens = setup
    assert propose(client, tokens, target="2001:db8::10").status_code == 201


def test_protected_alias_rechecked_at_approval(setup):
    app, client, tokens = setup
    pid = propose(client, tokens).json()["proposal_id"]
    app.state.core.assets[0].aliases.append("admin-host")
    response = client.post(f"/v1/actions/{pid}/approve", json={}, headers=auth(tokens, "operator"))
    assert response.status_code == 403


def test_registered_asset_without_lab_designation_cannot_suspend(setup):
    app, client, tokens = setup
    app.state.core.assets[0].lab_asset = False
    response = propose(
        client,
        tokens,
        action_type="SUSPEND_TEST_PROCESS",
        target="CLIENT01",
        playbook_id="SZ-PB-002",
        parameters={"lab_only": True, "process_name": "test-worker"},
    )
    assert response.status_code == 403
    app.state.settings.lab_asset_ids = "CLIENT01"
    response = propose(
        client,
        tokens,
        action_type="SUSPEND_TEST_PROCESS",
        target="CLIENT01",
        playbook_id="SZ-PB-002",
        parameters={"lab_only": True, "process_name": "test-worker"},
    )
    assert response.status_code == 201


def test_admin_is_not_implicit_operator_or_analyst(setup):
    _, client, tokens = setup
    pid = propose(client, tokens).json()["proposal_id"]
    for operation in ("approve", "reject", "execute", "rollback"):
        assert client.post(f"/v1/actions/{pid}/{operation}", json={}, headers=auth(tokens, "admin")).status_code == 403
    assert (
        client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens, "admin")).status_code
        == 403
    )


def test_concurrent_approval_is_one_decision(setup):
    app, client, tokens = setup
    pid = propose(client, tokens).json()["proposal_id"]

    def request(_):
        return client.post(f"/v1/actions/{pid}/approve", json={}, headers=auth(tokens, "operator")).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(request, range(4)))
    assert results.count(200) == 1 and results.count(409) == 3
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Approval)) == 1


def test_concurrent_rollback_claims_once(setup):
    app, client, tokens = setup
    pid = approved(client, tokens)
    client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator"))

    def request(_):
        return client.post(f"/v1/actions/{pid}/rollback", headers=auth(tokens, "operator")).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(request, range(4)))
    assert results.count(200) == 1 and results.count(409) == 3
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Execution).where(Execution.operation == "rollback")) == 1


def test_timeout_after_dispatch_is_unknown_and_claim_survives_restart(setup):
    import asyncio

    app, client, tokens = setup

    class Slow(DryRunExecutor):
        async def execute(self, proposal):
            await super().execute(proposal)
            await asyncio.sleep(0.2)

    app.state.executor = Slow(app.state.sessions)
    app.state.settings.executor_timeout_seconds = 0.01
    pid = approved(client, tokens)
    result = client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).json()
    assert result["status"] == "UNKNOWN" and result["verification_result"] is None
    with TestClient(create_app(app.state.settings)) as restarted:
        assert restarted.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).status_code == 409
        assert restarted.post(f"/v1/actions/{pid}/rollback", headers=auth(tokens, "operator")).json()[
            "restoration_verified"
        ]


@pytest.mark.parametrize("executor", ["shuffle", "pfsense"])
async def test_real_executor_stubs_always_fail_closed(setup, executor):
    app, _, _ = setup
    adapter = build_executor(Settings(_env_file=None, core_tenant_id="lab", soar_executor=executor), app.state.sessions)
    assert await adapter.health() == "unavailable" and not adapter.dry_run
    for call in (
        adapter.execute(None),
        adapter.verify(None),
        adapter.rollback(None),
        adapter.verify(None, restored=True),
    ):
        with pytest.raises(DependencyUnavailable, match="real_executor_not_implemented"):
            await call


def test_expired_approval_and_tenant_action_mutations_denied(setup):
    app, client, tokens = setup
    pid = propose(client, tokens).json()["proposal_id"]
    with app.state.sessions() as db:
        db.get(Proposal, pid).expires_at = utcnow() - timedelta(seconds=1)
        other = db.scalar(select(User).where(User.name == "other"))
        other.role = "operator"
        db.commit()
    assert client.post(f"/v1/actions/{pid}/approve", json={}, headers=auth(tokens, "operator")).status_code == 409
    for operation in ("approve", "reject", "execute", "rollback"):
        a = client.post(f"/v1/actions/{pid}/{operation}", json={}, headers=auth(tokens, "other"))
        b = client.post(f"/v1/actions/ABSENT/{operation}", json={}, headers=auth(tokens, "other"))
        assert a.status_code == b.status_code == 404 and a.json() == b.json()


def test_request_limit_and_structured_errors(setup):
    _, client, tokens = setup
    assert client.post("/v1/actions", content=b"x" * 65000, headers=auth(tokens)).status_code == 413
    value = client.post("/v1/actions", json={"secret-name-CANARY": "CANARY"}, headers=auth(tokens))
    assert value.status_code == 422 and value.json()["detail"]["code"] == "validation_error"
    assert "CANARY" not in value.text
    assert client.get("/v1/actions", headers=auth(tokens)).headers["cache-control"] == "no-store"


def test_existing_event_outside_selected_context_is_untrusted(setup):
    from app.ai.providers.mock import MockAIProvider

    app, client, tokens = setup
    original = app.state.core.contexts[("lab", "SZ-000042")].evidence[0]
    app.state.core.contexts[("lab", "SZ-000042")].evidence.append(
        original.model_copy(update={"event_uid": "EVT-OMITTED", "priority": "low"})
    )
    app.state.settings.max_evidence = 1

    class WrongSelection(MockAIProvider):
        async def analyze(self, context):
            value = await super().analyze(context)
            value["observed_facts"][0]["evidence_event_ids"] = ["EVT-OMITTED"]
            return value

    app.state.provider = WrongSelection()
    value = client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens)).json()
    assert value["trusted"] is False and value["analysis"] is None
    assert value["validation"]["reason"] == "evidence_not_in_selected_context"


def test_core_unavailable_never_falls_back_to_fixture(setup):
    from app.main import UnavailableCore

    app, client, tokens = setup
    app.state.repository = UnavailableCore()
    value = client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens)).json()
    assert value["status"] == "failed" and value["trusted"] is False
    assert value["citations"] == [] and value["observed_facts"] is None
    assert client.get("/health").status_code == 200
    assert client.get("/health").json()["core_backend"] == "unavailable"
    assert propose(client, tokens).status_code == 503
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Execution)) == 0


@pytest.mark.parametrize(
    "damage,reason",
    [("missing", "fabricated_evidence_id"), ("wrong_incident", "evidence_scope_mismatch"), ("valid", None)],
)
async def test_live_rest_citation_batch_checks_alert_and_membership(damage, reason):
    def handler(request):
        if "/alerts/" in request.url.path:
            if damage == "missing":
                return httpx.Response(404)
            return httpx.Response(
                200,
                json={
                    "event_uid": "EVT-001",
                    "tenant_id": "lab",
                    "incident_ids": ["OTHER" if damage == "wrong_incident" else "SZ-000042"],
                },
            )
        return tenant_handler(request)

    core = RealCoreBackendClient(settings(), httpx.MockTransport(handler))
    assert await core.validate_event_ids(["EVT-001"], "SZ-000042", "lab") == reason
    await core.close()


def test_revoked_approver_blocks_different_active_executor(setup):
    from app.security.auth import create_user

    app, client, tokens = setup
    pid = approved(client, tokens)
    with app.state.sessions() as db:
        secondary = create_user(db, "operator2", "operator", "lab")
        db.scalar(select(User).where(User.name == "operator")).active = False
        db.commit()
    result = client.post(f"/v1/actions/{pid}/execute", headers={"Authorization": f"Bearer {secondary}"})
    assert result.status_code == 403 and result.json()["detail"]["code"] == "valid_independent_approval_required"


def test_executor_identity_cannot_change_after_approval(setup):
    app, client, tokens = setup
    pid = approved(client, tokens)

    class Different(DryRunExecutor):
        name = "different"

    app.state.executor = Different(app.state.sessions)
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).status_code == 503


def test_settings_repr_does_not_expose_credential_fields():
    value = Settings(
        _env_file=None, core_tenant_id="lab",
        core_api_token="CANARY",
        openai_api_key="CANARY",
        local_ai_token="CANARY",
        pfsense_api_token="CANARY",
        shuffle_api_key="CANARY",
    )
    assert "CANARY" not in repr(value)


@pytest.mark.parametrize("field", ["addresses", "aliases", "missing_telemetry"])
async def test_malformed_list_fields_do_not_hide_protected_ips_or_split_secrets(field):
    def handler(request):
        value = tenant_handler(request).json()
        if field == "missing_telemetry" and request.url.path == "/v1/incidents/SZ-000042":
            value[field] = "password=CANARY"
        elif field in {"addresses", "aliases"} and request.url.path == "/v1/assets":
            value["items"][0][field] = "192.0.2.50"
        return httpx.Response(200, json=value)

    core = RealCoreBackendClient(settings(), httpx.MockTransport(handler))
    with pytest.raises(DependencyUnavailable, match="invalid_core_contract"):
        await core.get_incident_context("SZ-000042", "lab")
    await core.close()


async def test_envelope_tenant_cannot_be_hidden_by_inner_data():
    core = RealCoreBackendClient(
        settings(core_single_tenant_ack=True),
        httpx.MockTransport(
            lambda request: httpx.Response(200, json={"tenant_id": "foreign", "data": core_handler(request).json()})
        ),
    )
    with pytest.raises(ServiceError):
        await core.get_incident_context("SZ-000042", "lab")
    await core.close()
