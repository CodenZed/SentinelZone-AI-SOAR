"""Read-only deployment preflight. No AI inference, SOAR dispatch or Core DB access."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.connectors.core_backend import RealCoreBackendClient
from app.errors import ServiceError


async def check(incident_id):
    core = None
    try:
        settings = Settings()
        if settings.core_mode != "real":
            print(json.dumps({"status": "NOT_RUN", "reason": "CORE_MODE must be real"}))
            return 2
        core = RealCoreBackendClient(settings)
        health = await core.health()
        context = await core.get_incident_context(incident_id, settings.core_tenant_id)
        ids = [e.event_uid for e in context.evidence[: settings.max_evidence]]
        reason = await core.validate_event_ids(ids, context.incident_id, context.tenant_id)
        # Exercise inventory even if incident has no primary host.
        await core.get_asset("PREFLIGHT-NONEXISTENT-ASSET", settings.core_tenant_id)
        complete = health == "healthy" and reason is None and bool(ids)
        print(
            json.dumps(
                {
                    "status": "PASS" if complete else "INCOMPLETE",
                    "core_health": health,
                    "events_checked": len(ids),
                    "assets_in_incident": len(context.assets),
                    "telemetry_hosts": len(context.telemetry),
                    "data_mode": context.data_mode,
                    "validation": reason,
                    "writes_performed": False,
                    "note": "No selected events means citation route was not verified." if not ids else None,
                }
            )
        )
        return 0 if complete else 1
    except ServiceError as exc:
        print(json.dumps({"status": "FAIL", "code": exc.code, "writes_performed": False}))
        return 1
    except Exception:
        print(
            json.dumps(
                {"status": "FAIL", "code": "preflight_configuration_or_contract_error", "writes_performed": False}
            )
        )
        return 1
    finally:
        if core:
            await core.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("incident_id")
    raise SystemExit(asyncio.run(check(parser.parse_args().incident_id)))
