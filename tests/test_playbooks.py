from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.config import ROOT
from app.errors import ServiceError
from app.soar.playbooks.engine import execution_plan, load_playbook, validate_playbook
from tests.conftest import auth, propose


@pytest.mark.parametrize(
    "damage", ["cycle", "unknown", "approval", "no_dependency", "conditional_gate", "arbitrary_code", "duplicate"]
)
def test_unsafe_yaml_graph_rejected(damage):
    book = load_playbook(ROOT / "playbooks/block_ip.yml").model_dump()
    if damage == "cycle":
        book["steps"][0]["depends_on"] = ["execute"]
    elif damage == "unknown":
        book["steps"][2]["depends_on"] = ["nonexistent"]
    elif damage == "approval":
        book["steps"][2]["requires_approval"] = False
    elif damage == "no_dependency":
        book["steps"][2]["depends_on"] = []
    elif damage == "conditional_gate":
        book["steps"][0]["condition"] = {"field": "target", "equals": "skip"}
    elif damage == "arbitrary_code":
        book["steps"][2]["action"] = "shell_command"
    else:
        book["steps"].append(deepcopy(book["steps"][0]))
    with pytest.raises(ValueError):
        validate_playbook(book)


def test_branch_condition_prevents_execution():
    book = load_playbook(ROOT / "playbooks/suspend_test_process.yml")
    with pytest.raises(ServiceError, match="playbook_condition_not_met"):
        execution_plan(
            book, SimpleNamespace(action_type="SUSPEND_TEST_PROCESS", target="CLIENT01", parameters={"lab_only": False})
        )


def test_test_process_workflow(setup):
    _, client, tokens = setup
    response = propose(
        client,
        tokens,
        action_type="SUSPEND_TEST_PROCESS",
        target="CLIENT01",
        playbook_id="SZ-PB-002",
        parameters={"lab_only": True, "process_name": "test-worker.exe"},
    )
    assert response.status_code == 201
    pid = response.json()["proposal_id"]
    assert client.post(f"/v1/actions/{pid}/approve", json={}, headers=auth(tokens, "operator")).status_code == 200
    assert client.post(f"/v1/actions/{pid}/execute", headers=auth(tokens, "operator")).json()["status"] == "SUCCESS"


def test_arbitrary_parameters_rejected(setup):
    _, client, tokens = setup
    assert propose(client, tokens, parameters={"command": "do-anything"}).status_code == 422
    assert (
        propose(
            client,
            tokens,
            action_type="SUSPEND_TEST_PROCESS",
            target="CLIENT01",
            playbook_id="SZ-PB-002",
            parameters={"lab_only": True, "process_name": "production-process.exe"},
        ).status_code
        == 422
    )
