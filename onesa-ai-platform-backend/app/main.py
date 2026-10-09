"""Application factory for the buildable M0 foundation."""

import asyncio
import json
import logging
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from app import agents, auth, chat, conversations, documentation, knowledge, observability, travel
from app.config import Settings
from app.database import REQUIRED_SCHEMA_REVISION, make_engine
from app.inference import ModelClient, build_model_client
from app.limits import BodyLimit


def create_app(settings: Settings | None = None, client: ModelClient | None = None) -> FastAPI:
    config = settings or Settings()
    model_client = client or build_model_client(config)
    engine = make_engine(config.database_url) if config.database_url else None

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        if engine is not None:
            engine.dispose()

    logging.getLogger("onesa.requests").setLevel(logging.INFO)
    api = FastAPI(title="Onesa AI API", version="0.1.0", lifespan=lifespan)
    api.add_middleware(BodyLimit)
    api.state.auth_hash_semaphore = threading.BoundedSemaphore(config.auth_hash_concurrency)
    api.state.ingestion_semaphore = asyncio.Semaphore(config.knowledge_upload_concurrency)
    api.state.settings = config
    api.state.engine = engine
    api.state.model_client = model_client
    api.state.trip_planner = (
        travel.MockItineraryPlanner()
        if config.model_backend == "mock"
        else travel.ModelItineraryPlanner(model_client)
    )
    api.include_router(auth.router)
    api.include_router(conversations.router)
    api.include_router(chat.router)
    api.include_router(knowledge.router)
    api.include_router(agents.router)
    api.include_router(travel.router)
    api.include_router(documentation.router)
    api.include_router(observability.router)

    @api.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        detail = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {"code": "http_error", "message": exc.detail}
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {**detail, "request_id": request.state.request_id}},
        )

    @api.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request",
                    "request_id": request.state.request_id,
                }
            },
        )

    @api.middleware("http")
    async def correlation_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # TLS terminates at trusted ingress; use configured transport.
        if config.environment in {"staging", "production"}:
            request.scope["scheme"] = "https"
        # Generate locally; untrusted caller headers must not enter logs or responses.
        request_id = str(uuid4())
        request.state.request_id = request_id
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            # Do not log exception strings: upstream URLs or content may contain secrets.
            logging.getLogger("onesa.requests").error(
                json.dumps({"event": "request_failure", "request_id": request_id})
            )
            response = JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "service_unavailable",
                        "message": "Service temporarily unavailable",
                        "request_id": request_id,
                    }
                },
            )
        observability.record(request, response.status_code, time.monotonic() - started)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/ready", responses={503: {"description": "Model backend unavailable"}})
    async def ready(request: Request) -> JSONResponse:
        def database_ready() -> bool:
            if engine is None:
                return False
            with Session(engine) as db:
                revision = db.scalar(text("SELECT version_num FROM alembic_version"))
                valid = revision == REQUIRED_SCHEMA_REVISION
                if config.environment in {"staging", "production"}:
                    superuser = db.scalar(
                        text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
                    )
                    valid = valid and superuser is False
                return bool(valid)

        model_ready = False
        db_ready = False
        try:
            model_ready = await asyncio.wait_for(
                request.app.state.model_client.healthy(), timeout=2.0
            )
        except Exception:
            pass
        if engine is not None:
            try:
                db_ready = await asyncio.wait_for(run_in_threadpool(database_ready), timeout=6.0)
            except Exception:
                pass
        observability.dependency_available.labels("model").set(int(model_ready))
        observability.dependency_available.labels("database").set(int(db_ready))
        healthy = model_ready and (db_ready or engine is None)
        if not healthy:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "dependency_unavailable",
                        "request_id": request.state.request_id,
                    }
                },
            )
        return JSONResponse({"status": "ready", "backend": config.model_backend})

    return api
