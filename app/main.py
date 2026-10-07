from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from app.api.responses import ErrorResponse
from app.security.limits import RequestLimitMiddleware

from app import __version__
from app.ai.providers.base import UnavailableAIProvider
from app.ai.providers.local import LocalModelProvider
from app.ai.providers.mock import MockAIProvider
from app.ai.providers.openai import OpenAIProvider
from app.api import actions, ai, health, playbooks, identity, product
from app.repositories.sql import SQLEvidenceRepository
from app.ai.providers.ollama import OllamaProvider
from app.config import Settings
from app.connectors.core_backend import CoreBackendClient, MockCoreBackendClient, RealCoreBackendClient
from app.db.session import database
from app.errors import DependencyUnavailable, ServiceError
from app.soar.executors.factory import build_executor
from app.soar.playbooks.engine import catalog
from app.soar.proposals.policy import TargetPolicy


class UnavailableCore(CoreBackendClient):
    async def get_incident_context(self, incident_id, tenant_id):
        raise DependencyUnavailable("core_unconfigured")

    async def event_exists(self, event_uid):
        raise DependencyUnavailable("core_unconfigured")

    async def get_asset(self, asset_id, tenant_id):
        raise DependencyUnavailable("core_unconfigured")

    async def health(self):
        return "unavailable"


def create_app(settings=None, *, core=None, provider=None, executor=None):
    settings = settings or Settings()
    engine, sessions = database(settings.database_url)
    if core is None:
        try:
            core = (SQLEvidenceRepository(sessions) if settings.core_mode == "standalone" else
                    MockCoreBackendClient(settings.fixture_dir) if settings.core_mode == "mock" else
                    RealCoreBackendClient(settings))
        except DependencyUnavailable:
            core = UnavailableCore()
    if provider is None:
        try:
            provider = {
                "mock": MockAIProvider,
                "openai": lambda: OpenAIProvider(settings),
                "local": lambda: LocalModelProvider(settings),
                "openai_compatible": lambda: LocalModelProvider(settings),
                "ollama": lambda: OllamaProvider(settings),
            }[settings.ai_provider]()
        except DependencyUnavailable:
            model = settings.openai_model if settings.ai_provider == "openai" else settings.local_ai_model
            provider = UnavailableAIProvider(settings.ai_provider, model)
    executor = executor or build_executor(settings, sessions)

    @asynccontextmanager
    async def lifespan(app):
        TargetPolicy(settings)
        catalog(settings.playbook_dir)
        yield
        await core.close()
        await provider.close()
        engine.dispose()

    app = FastAPI(
        title="SentinelZone AI/SOAR",
        version=__version__,
        lifespan=lifespan,
        responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 413, 422, 500, 503)},
        description="Standalone investigation and human-approved SOAR platform. Dry-run results never represent live containment.",
    )
    app.add_middleware(RequestLimitMiddleware, limit=settings.max_request_bytes)
    app.state.settings, app.state.engine, app.state.sessions = settings, engine, sessions
    app.state.core, app.state.provider, app.state.executor = core, provider, executor
    app.state.repository = core
    for router in (health.router, ai.router, actions.router, playbooks.router, identity.router, product.router):
        app.include_router(router)

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": {"code": exc.code}})

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": {"code": "http_error"}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc):
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "validation_error",
                    "issues": [{"loc": [str(e["loc"][0])], "type": e["type"]} for e in exc.errors()],
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc):
        return JSONResponse(status_code=503, content={"detail": {"code": "database_unavailable"}})

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc):
        return JSONResponse(status_code=500, content={"detail": {"code": "internal_error"}})

    return app


app = create_app()
