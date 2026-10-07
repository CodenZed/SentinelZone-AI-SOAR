from app.soar.executors.dry_run import DryRunExecutor
from tests.conftest import approved, auth


def test_verification_failure_is_failed_and_rollback_restores(setup):
    app, client, tokens = setup

    class FailedVerification(DryRunExecutor):
        async def verify(self, proposal, *, restored=False):
            return await super().verify(proposal, restored=restored) if restored else False

    app.state.executor = FailedVerification(app.state.sessions)
    pid = approved(client, tokens)
    result = client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).json()
    assert result["status"] == "FAILED"
    result = client.post(f"/v1/actions/{pid}/rollback", headers=auth(tokens, "operator")).json()
    assert result["status"] == "RESTORED" and result["dry_run"]
    detail = client.get(f"/v1/actions/{pid}", headers=auth(tokens)).json()
    assert detail["executions"][1]["result"]["verified_removed"] is True


def test_successful_rollback_and_duplicate_denied(setup):
    _, client, tokens = setup
    pid = approved(client, tokens)
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).json()["status"] == "SUCCESS"
    assert client.post(f"/v1/actions/{pid}/rollback", headers=auth(tokens, "operator")).json()["status"] == "RESTORED"
    assert client.post(f"/v1/actions/{pid}/rollback", headers=auth(tokens, "operator")).status_code == 409
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).status_code == 409


def test_failed_rollback_verification_is_not_restored(setup):
    app, client, tokens = setup

    class BrokenRemoval(DryRunExecutor):
        async def verify(self, proposal, *, restored=False):
            return False if restored else await super().verify(proposal)

    app.state.executor = BrokenRemoval(app.state.sessions)
    pid = approved(client, tokens)
    client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator"))
    result = client.post(f"/v1/actions/{pid}/rollback", headers=auth(tokens, "operator")).json()
    assert result["status"] == "ROLLBACK_FAILED"
