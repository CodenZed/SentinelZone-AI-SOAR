import pytest

from tests.conftest import approved, auth, propose
from tests.test_approval import zero_executions


@pytest.mark.parametrize(
    "target",
    [
        "splunk",
        "SPLUNK.",
        "192.0.2.50",
        "wazuh_manager",
        "domain-controller",
        "pfsense",
        "backup_server",
        "admin_host",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
    ],
)
def test_protected_target_denied(setup, target):
    app, client, tokens = setup
    response = propose(client, tokens, target=target)
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "DENIED_PROTECTED_TARGET"
    zero_executions(app)


def test_protection_rechecked_after_approval(setup):
    app, client, tokens = setup
    pid = approved(client, tokens)
    app.state.core.assets[0].role = "domain-controller"
    response = client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator"))
    assert response.status_code == 403
    zero_executions(app)


def test_cidr_and_mapped_address_protection(setup):
    app, client, tokens = setup
    app.state.settings.protected_networks = "192.0.2.0/24"
    assert propose(client, tokens).status_code == 403
    assert propose(client, tokens, target="::ffff:192.0.2.10").status_code == 403
