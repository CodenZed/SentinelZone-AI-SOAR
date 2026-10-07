import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.api.responses import HealthView

router = APIRouter(tags=["Health"])


async def safe_probe(dependency):
    try:
        return await asyncio.wait_for(dependency.health(), 5)
    except Exception:
        return "unavailable"


@router.get("/health", response_model=HealthView)
async def health(request: Request):
    state = request.app.state
    try:
        with state.sessions() as session:
            revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
            if revision != "0003":
                raise ValueError("schema_not_current")
        database = "healthy"
    except Exception:
        database = "unavailable"
    core, provider, executor = await asyncio.gather(
        safe_probe(state.repository), safe_probe(state.provider), safe_probe(state.executor)
    )
    healthy = all(v == "healthy" for v in (database, core, provider, executor))
    return JSONResponse(
        status_code=200 if database == "healthy" else 503,
        content={
            "status": "healthy" if healthy else "degraded",
            "database": database,
            "core_backend": core,
            "core_mode": state.settings.core_mode,
            "ai_provider": provider,
            "soar_executor": state.executor.name,
            "executor_status": executor,
            "dry_run": state.executor.dry_run,
            "version": __version__,
        },
    )
