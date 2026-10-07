from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import Execution, Proposal, SimulatedEffect, uid
from app.main import create_app
from tests.conftest import approved, auth


def test_duplicate_and_restart_one_execution(setup):
    app, client, tokens = setup
    pid = approved(client, tokens)
    url = f"/v1/actions/{pid}/execute"
    assert client.post(url, headers=auth(tokens, "operator")).json()["status"] == "SUCCESS"
    response = client.post(url, headers=auth(tokens, "operator"))
    assert response.status_code == 409 and response.json()["detail"]["code"] == "ALREADY_EXECUTED"
    restarted = create_app(app.state.settings)
    with TestClient(restarted) as second:
        assert second.post(url, headers=auth(tokens, "operator")).status_code == 409
        assert second.get(f"/v1/actions/{pid}", headers=auth(tokens)).json()["status"] == "SUCCESS"
    with app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Execution)) == 1
        assert session.scalar(select(func.count()).select_from(SimulatedEffect)) == 1


def test_concurrent_execute_claims_once(setup):
    app, client, tokens = setup
    pid = approved(client, tokens)

    def execute(_):
        return client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(execute, range(4)))
    assert codes.count(200) == 1 and codes.count(409) == 3, codes
    with app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Execution)) == 1


def test_crash_after_claim_before_effect_never_retried(setup):
    app, client, tokens = setup
    pid = approved(client, tokens)
    with app.state.sessions() as session:
        session.get(Proposal, pid).status = "EXECUTING"
        session.add(
            Execution(id=uid("EXE"), proposal_id=pid, operation="execute", status="STARTED", executor="dry_run")
        )
        session.commit()
    restarted = create_app(app.state.settings)
    with TestClient(restarted) as second:
        assert second.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).status_code == 409
        assert second.post(f"/v1/actions/{pid}/rollback", headers=auth(tokens, "operator")).status_code == 409
    with app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(SimulatedEffect)) == 0
