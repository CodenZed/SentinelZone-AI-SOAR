from datetime import timedelta

from sqlalchemy import func, select

from app.db.models import Execution, Proposal, User, utcnow
from tests.conftest import auth, propose


def zero_executions(app):
    with app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Execution)) == 0


def test_no_approval_zero_execution(setup):
    app, client, tokens = setup
    pid = propose(client, tokens).json()["proposal_id"]
    response = client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator"))
    assert response.status_code == 409 and response.json()["detail"]["code"] == "approval_required"
    zero_executions(app)


def test_wrong_role_403(setup):
    app, client, tokens = setup
    pid = propose(client, tokens).json()["proposal_id"]
    assert client.post(f"/v1/actions/{pid}/approve", json={}, headers=auth(tokens)).status_code == 403
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens)).status_code == 403
    assert client.get("/v1/policy", headers=auth(tokens)).status_code == 403
    assert client.get("/v1/policy", headers=auth(tokens, "admin")).status_code == 200
    zero_executions(app)


def test_self_approval_after_role_change_denied(setup):
    app, client, tokens = setup
    pid = propose(client, tokens).json()["proposal_id"]
    with app.state.sessions() as session:
        user = session.scalar(select(User).where(User.name == "analyst"))
        user.role = "operator"
        session.commit()
    response = client.post(f"/v1/actions/{pid}/approve", json={}, headers=auth(tokens))
    assert response.status_code == 403 and response.json()["detail"]["code"] == "self_approval_forbidden"


def test_expired_proposal_zero_execution(setup):
    from tests.conftest import approved

    app, client, tokens = setup
    pid = approved(client, tokens)
    with app.state.sessions() as session:
        session.get(Proposal, pid).expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
    response = client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator"))
    assert response.status_code == 409 and response.json()["detail"]["code"] == "proposal_expired"
    zero_executions(app)


def test_rejected_proposal_cannot_execute_or_approve(setup):
    app, client, tokens = setup
    pid = propose(client, tokens).json()["proposal_id"]
    assert (
        client.post(
            f"/v1/actions/{pid}/reject", json={"reason": "not justified"}, headers=auth(tokens, "operator")
        ).json()["status"]
        == "REJECTED"
    )
    assert client.post(f"/v1/actions/{pid}/approve", json={}, headers=auth(tokens, "operator")).status_code == 409
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).status_code == 409
    zero_executions(app)
