import json

import pytest
from sqlalchemy import func, select

from app.config import ROOT
from app.db.models import Proposal
from tests.conftest import auth

CASES = json.loads((ROOT / "tests/eval_data/cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_deterministic_offline_evaluations(setup, case):
    app, client, tokens = setup
    app.state.core.contexts[("lab", "SZ-000042")].evidence[0].summary = case["summary"]
    value = client.post("/v1/ai/analyze", json={"incident_id": "SZ-000042"}, headers=auth(tokens)).json()
    assert value["trusted"] is case["expected_trusted"]
    assert value["analysis"]["observed_facts"] == [
        {"text": "An event was recorded by wazuh.", "evidence_event_ids": ["EVT-001"]}
    ]
    assert "REDACTION_CANARY" not in json.dumps(value)
    assert any("UNKNOWN" in item for item in value["analysis"]["missing_evidence"])
    with app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Proposal)) == 0
