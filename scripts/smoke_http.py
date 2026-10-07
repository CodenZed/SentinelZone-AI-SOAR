"""Real loopback HTTP + SQLite smoke, synthetic core/provider and durable dry-run only."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from alembic import command
from alembic.config import Config
from app.config import ROOT
from app.db.session import database
from app.security.auth import create_user


def main():
    with tempfile.TemporaryDirectory(prefix="sentinelzone-smoke-") as tmp:
        url = f"sqlite:///{Path(tmp) / 'sentinelzone_ai_soar.db'}"
        config = Config(str(ROOT / "alembic.ini"))
        config.attributes["database_url"] = url
        command.upgrade(config, "head")
        engine, sessions = database(url)
        with sessions() as db:
            analyst = create_user(db, "smoke-analyst", "analyst", "lab")
            operator = create_user(db, "smoke-operator", "operator", "lab")
        engine.dispose()
        with socket.socket() as bound:
            bound.bind(("127.0.0.1", 0))
            port = bound.getsockname()[1]
        env = {
            **os.environ,
            "APP_ENV": "test",
            "DATABASE_URL": url,
            "CORE_MODE": "mock",
            "AI_PROVIDER": "mock",
            "SOAR_EXECUTOR": "dry_run",
            "CORE_API_TOKEN": "",
            "POLICY_FILE": str(ROOT / "config/policy.yml"),
            "PROTECTED_NETWORKS": "",
        }
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=10) as client:
                for _ in range(100):
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.05)
                else:
                    raise RuntimeError("smoke server did not start")
                a, o = {"Authorization": f"Bearer {analyst}"}, {"Authorization": f"Bearer {operator}"}
                result = client.post("/v1/ai/analyze", headers=a, json={"incident_id": "SZ-000042"})
                assert result.status_code == 201 and result.json()["trusted"]
                result = client.post(
                    "/v1/actions",
                    headers=a,
                    json={
                        "incident_id": "SZ-000042",
                        "action_type": "BLOCK_IP",
                        "target": "192.0.2.10",
                        "playbook_id": "SZ-PB-001",
                        "parameters": {},
                    },
                )
                assert result.status_code == 201
                path = "/v1/actions/" + result.json()["proposal_id"]
                assert client.post(path + "/approve", headers=o, json={}).status_code == 200
                executed = client.post(path + "/execute", headers=o).json()
                assert executed["status"] == "SUCCESS" and executed["dry_run"] and executed["verification_result"]
                assert client.post(path + "/execute", headers=o).status_code == 409
                restored = client.post(path + "/rollback", headers=o).json()
                assert restored["status"] == "RESTORED" and restored["restoration_verified"]
                print(
                    json.dumps(
                        {
                            "status": "PASS",
                            "transport": "loopback HTTP",
                            "database": "temporary SQLite",
                            "core": "mock",
                            "provider": "mock",
                            "dry_run": True,
                            "live_containment": False,
                        }
                    )
                )
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
