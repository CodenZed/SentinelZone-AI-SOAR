import io
import json

from alembic import command
from alembic.config import Config
import jsonschema
from sqlalchemy import inspect

from app.config import ROOT
from app.contracts import ActionProposal, AIOutput, IncidentContext, Playbook
from app.db.models import Base
from app.db.session import database


def test_migration_roundtrip_and_no_schema_drift(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    command.check(config)
    engine, _ = database(url)
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    engine.dispose()


def test_postgresql_migration_sql_generation():
    output = io.StringIO()
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output)
    config.attributes["database_url"] = "postgresql+psycopg://localhost/sentinelzone_ai_soar"
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "UNIQUE (proposal_id, operation)" in sql
    assert "CREATE TABLE ai_runs" in sql


def test_exported_contracts_match_implementation_and_fixtures():
    for name, model in [
        ("incident-context", IncidentContext),
        ("ai-output", AIOutput),
        ("action-proposal", ActionProposal),
        ("playbook", Playbook),
    ]:
        assert json.loads((ROOT / f"contracts/{name}.schema.json").read_text()) == model.model_json_schema()
    schema = IncidentContext.model_json_schema()
    for fixture in (ROOT / "fixtures/incidents").glob("*.json"):
        jsonschema.validate(json.loads(fixture.read_text()), schema)
