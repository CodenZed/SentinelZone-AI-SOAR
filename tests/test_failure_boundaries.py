import asyncio
import subprocess
import sys

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.ai.providers.mock import MockAIProvider
from app.config import ROOT, Settings
from app.db.models import Proposal, SimulatedEffect, User
from app.main import create_app
from app.soar.executors.dry_run import DryRunExecutor
from tests.conftest import approved, auth
from tests.test_approval import zero_executions


def test_revoked_approver_zero_execution(setup):
    app, client, tokens = setup
    pid = approved(client, tokens)
    with app.state.sessions() as session:
        session.scalar(select(User).where(User.name == "operator")).active = False
        session.commit()
    # Service entrypoint refuses the inactive operator before processing the proposal.
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).status_code == 401
    zero_executions(app)


def test_timeout_and_unexpected_provider_failure_are_safe(setup):
    app, client, tokens = setup

    class Slow(MockAIProvider):
        async def analyze(self, context):
            await asyncio.sleep(0.1)

    class Broken(MockAIProvider):
        async def analyze(self, context):
            raise RuntimeError("CANARY")

    app.state.settings.provider_timeout_seconds = 0.01
    for provider in (Slow(), Broken()):
        app.state.provider = provider
        response = client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens))
        assert response.json()["status"] == "failed"
        assert "CANARY" not in response.text


def test_side_effect_then_exception_never_reexecuted_and_can_rollback(setup):
    app, client, tokens = setup

    class Uncertain(DryRunExecutor):
        async def execute(self, proposal):
            await super().execute(proposal)
            raise RuntimeError("lost response")

    app.state.executor = Uncertain(app.state.sessions)
    pid = approved(client, tokens)
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).json()["status"] == "UNKNOWN"
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).status_code == 409
    assert client.post(f"/v1/actions/{pid}/rollback", headers=auth(tokens, "operator")).json()["status"] == "RESTORED"
    with app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(SimulatedEffect)) == 1


def test_database_not_migrated_unhealthy(tmp_path):
    app = create_app(Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"))
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 503 and response.json()["database"] == "unavailable"


def test_process_restart_reconciliation_does_not_reexecute(setup):
    import os

    app, client, tokens = setup
    pid = approved(client, tokens)
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).json()["status"] == "SUCCESS"
    with app.state.sessions() as session:
        session.get(Proposal, pid).status = "EXECUTING"
        session.commit()
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "reconcile", pid, "--workers-stopped"],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": app.state.settings.database_url},
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "SUCCESS" in result.stdout
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).status_code == 409
