import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest

from app.config import ROOT, Settings
from app.main import create_app
from app.security.auth import create_user


def migrate(url):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")


@pytest.fixture
def setup(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    if os.environ.get("TEST_DATABASE_URL"):
        from sqlalchemy.engine import make_url

        if make_url(url).database != "sentinelzone_ai_soar_test":
            raise RuntimeError("TEST_DATABASE_URL must identify a disposable sentinelzone_ai_soar_test database")
        from app.db.models import Base
        from app.db.session import database

        engine, _ = database(url)
        Base.metadata.drop_all(engine)
        from sqlalchemy import text

        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()
    migrate(url)
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=url,
        core_mode="mock",
        ai_provider="mock",
        soar_executor="dry_run",
        openai_api_key="",
        openai_model="",
        local_ai_url="",
        local_ai_model="",
        core_api_token="",
        protected_networks="",
        fixture_dir=ROOT / "fixtures",
        playbook_dir=ROOT / "playbooks",
        policy_file=ROOT / "config/policy.yml",
    )
    app = create_app(settings)
    tokens = {}
    with app.state.sessions() as session:
        for role in ("analyst", "operator", "admin"):
            tokens[role] = create_user(session, role, role, "lab")
        tokens["other"] = create_user(session, "other", "analyst", "other")
    with TestClient(app) as client:
        yield app, client, tokens


def auth(tokens, role="analyst"):
    return {"Authorization": f"Bearer {tokens[role]}"}


def propose(client, tokens, **overrides):
    body = {
        "incident_id": "SZ-000042",
        "action_type": "BLOCK_IP",
        "target": "192.0.2.10",
        "playbook_id": "SZ-PB-001",
        "parameters": {},
    }
    body.update(overrides)
    return client.post("/v1/actions", json=body, headers=auth(tokens))


def approved(client, tokens):
    response = propose(client, tokens)
    assert response.status_code == 201, response.text
    pid = response.json()["proposal_id"]
    response = client.post(f"/v1/actions/{pid}/approve", json={}, headers=auth(tokens, "operator"))
    assert response.status_code == 200, response.text
    return pid
