import io
import json
import os

import jsonschema
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.api.responses import AIRunView, ActionView, ErrorResponse
from app.config import ROOT
from app.db.session import database
from app.main import create_app
from app.soar.executors.contracts import ExecutionReceipt, VerificationReport
from app.soar.executors.factory import ExternalExecutorConfig
from app.soar.verification.service import verify_effect
from tests.conftest import approved, auth


def test_response_schemas_and_openapi_match_exports(setup):
    app, client, tokens = setup
    for name, model in [
        ("ai-run", AIRunView),
        ("action-view", ActionView),
        ("api-error", ErrorResponse),
        ("execution-receipt", ExecutionReceipt),
        ("verification-report", VerificationReport),
        ("executor-config", ExternalExecutorConfig),
    ]:
        assert json.loads((ROOT / f"contracts/{name}.schema.json").read_text()) == model.model_json_schema()
    assert json.loads((ROOT / "docs/openapi.json").read_text()) == create_app(app.state.settings).openapi()
    run = client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens)).json()
    jsonschema.validate(run, AIRunView.model_json_schema())
    assert run["created_at"].endswith("Z") and run["data_mode"] == "TEST"
    assert run["observed_facts"] == run["analysis"]["observed_facts"]
    assert run["citations"][0]["event_uid"] == "EVT-001"
    pid = approved(client, tokens)
    before = client.get(f"/v1/actions/{pid}", headers=auth(tokens)).json()
    assert before["approval_status"] == "approved" and not before["rollback_available"]
    after = client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).json()
    jsonschema.validate(after, ActionView.model_json_schema())
    assert after["dry_run"] and after["effect_scope"] == "simulated"
    assert after["verification_result"] is True and after["rollback_available"]
    assert "WOULD EXECUTE" in json.dumps(after["execution_result"])
    restored = client.post(f"/v1/actions/{pid}/rollback", headers=auth(tokens, "operator")).json()
    assert restored["restoration_verified"] is True and not restored["rollback_available"]
    jsonschema.validate(client.get("/v1/actions").json(), ErrorResponse.model_json_schema())


async def test_live_verifier_rejects_exit_code_boolean():
    from types import SimpleNamespace

    class ExitCodeOnly:
        dry_run = False

        async def verify(self, proposal, *, restored=False):
            return True

    with pytest.raises(ValueError):
        await verify_effect(ExitCodeOnly(), SimpleNamespace())


@pytest.mark.parametrize(
    "field,value", [("target", "different"), ("restored", True), ("dry_run", True), ("proposal_id", "OTHER")]
)
async def test_live_verification_report_must_match_exact_operation(field, value):
    from types import SimpleNamespace
    from app.db.models import utcnow
    from app.errors import ServiceError

    proposal = SimpleNamespace(proposal_id="ACT-test", target="192.0.2.10", action_type="BLOCK_IP")

    class Reports:
        dry_run = False

        async def verify(self, proposal, *, restored=False):
            return {
                "proposal_id": proposal.proposal_id,
                "target": proposal.target,
                "action_type": proposal.action_type,
                "restored": False,
                "verified": True,
                "dry_run": False,
                "queried_at": utcnow(),
                "observation": "synthetic state query",
                "query_reference": "synthetic-check",
                field: value,
            }

    with pytest.raises(ServiceError):
        await verify_effect(Reports(), proposal)


def test_upgrade_preserves_v0290_proposal_and_claim(tmp_path):
    url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "0001")
    engine, _ = database(url)
    with engine.begin() as db:
        for pid, dry_run in [("ACT-old", True), ("ACT-unbound", False)]:
            db.execute(
                text("""INSERT INTO action_proposals
                (proposal_id,tenant_id,incident_id,action_type,target,parameters,requested_by,status,
                 expires_at,created_at,playbook_id,playbook_snapshot,rollback_available,dry_run)
                VALUES (:pid,'lab','SZ-000042','BLOCK_IP','192.0.2.10','{}','old-analyst','EXECUTING',
                '2026-10-06 00:00:00','2026-10-06 00:00:00','SZ-PB-001','{}',true,:dry_run)"""),
                {"pid": pid, "dry_run": dry_run},
            )
        db.execute(
            text("""INSERT INTO action_executions
            (id,proposal_id,operation,status,executor,result,started_at)
            VALUES ('EXE-old','ACT-old','execute','STARTED','dry_run','{}','2026-10-06 00:00:00')""")
        )
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as db:
        assert (
            db.execute(text("SELECT executor FROM action_proposals WHERE proposal_id='ACT-old'")).scalar() == "dry_run"
        )
        assert (
            db.execute(text("SELECT executor FROM action_proposals WHERE proposal_id='ACT-unbound'")).scalar()
            == "legacy_unbound"
        )
        assert db.execute(text("SELECT count(*) FROM action_executions")).scalar() == 1
    engine.dispose()


def test_postgres_offline_downgrade_compiles():
    output = io.StringIO()
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output)
    config.attributes["database_url"] = "postgresql+psycopg://localhost/sentinelzone_ai_soar_test"
    command.downgrade(config, "0002:base", sql=True)
    assert "DROP COLUMN executor" in output.getvalue()


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="Live PostgreSQL not configured; offline SQL is not a runtime test"
)
def test_live_postgresql_migrations_and_schema(setup):
    app, client, _ = setup
    assert app.state.engine.dialect.name == "postgresql"
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = app.state.settings.database_url
    command.check(config)
    assert "action_audit" in inspect(app.state.engine).get_table_names()
    assert client.get("/health").status_code == 200
    # This suite's explicitly disposable database only; conftest rejects all other names.
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
