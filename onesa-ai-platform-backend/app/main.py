"""Application factory for the buildable M0 foundation."""

import asyncio
import json
import logging
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from app import (
    account,
    agents,
    auth,
    capacity,
    chat,
    conversations,
    documentation,
    industrial,
    knowledge,
    observability,
    travel,
)
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
    from app.identity import router as identity_router

    api.include_router(identity_router)
    from app.uploads import router as uploads_router

    api.include_router(uploads_router)
    api.include_router(account.router)
    api.include_router(conversations.router)
    api.include_router(chat.router)
    api.include_router(knowledge.router)
    api.include_router(agents.router)
    api.include_router(travel.router)
    api.include_router(documentation.router)
    api.include_router(industrial.router)
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
        lease_id = None
        try:
            if engine is not None and capacity.applies(request):
                lease_id = await run_in_threadpool(capacity.begin, request)
            response = await call_next(request)
        except HTTPException as exc:
            response = await http_error(request, exc)
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
        if lease_id is not None:
            # Error handlers produce a regular response; release immediately in that case.
            if hasattr(response, "body_iterator"):
                stream = cast(StreamingResponse, response)
                original = stream.body_iterator
                identifier = lease_id

                async def bounded_stream() -> AsyncIterator[bytes | str]:
                    checked = 0.0
                    try:
                        async for item in original:
                            if time.monotonic() - checked >= 1:
                                if not await run_in_threadpool(
                                    capacity.active, request, identifier
                                ):
                                    return
                                checked = time.monotonic()
                            yield bytes(item) if isinstance(item, memoryview) else item
                    finally:
                        await run_in_threadpool(capacity.end, request, identifier)

                stream.body_iterator = bounded_stream()
            else:
                await run_in_threadpool(capacity.end, request, lease_id)
        observability.record(request, response.status_code, time.monotonic() - started)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/core-ready", responses={503: {"description": "Core database unavailable"}})
    @api.get("/ready", responses={503: {"description": "Model backend unavailable"}})
    async def ready(request: Request) -> JSONResponse:
        def database_ready() -> bool:
            if engine is None:
                return False
            with Session(engine) as db:
                revision = db.scalar(text("SELECT version_num FROM alembic_version"))
                valid = revision in {REQUIRED_SCHEMA_REVISION, "20261010_capacity"}
                if config.industrial_demo_enabled:
                    valid = revision == REQUIRED_SCHEMA_REVISION
                if config.environment in {"staging", "production"}:
                    superuser = db.scalar(
                        text(
                            "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR "
                            "rolreplication OR rolbypassrls "
                            "OR has_schema_privilege(current_user, 'public', 'CREATE') "
                            "OR has_table_privilege(current_user, "
                            "'public.alembic_version', "
                            "'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') "
                            "OR EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON "
                            "n.oid=c.relnamespace "
                            "WHERE n.nspname='public' AND "
                            "pg_has_role(current_user,c.relowner,'MEMBER')) "
                            "OR EXISTS(SELECT 1 FROM pg_roles r WHERE "
                            "(r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR "
                            "r.rolreplication OR r.rolbypassrls) "
                            "AND pg_has_role(current_user,r.oid,'MEMBER')) "
                            "FROM pg_roles WHERE rolname = current_user"
                        )
                    )
                    valid = valid and superuser is False
                return bool(valid)

        async def model_probe() -> bool:
            try:
                return bool(
                    await asyncio.wait_for(request.app.state.model_client.healthy(), timeout=2.0)
                )
            except Exception:
                return False

        async def database_probe() -> bool:
            if engine is None:
                return False
            try:
                return bool(await asyncio.wait_for(run_in_threadpool(database_ready), timeout=3.5))
            except Exception:
                return False

        model_ready, db_ready = await asyncio.gather(model_probe(), database_probe())
        observability.dependency_available.labels("model").set(int(model_ready))
        observability.dependency_available.labels("database").set(int(db_ready))
        healthy = (model_ready or request.url.path == "/core-ready") and db_ready
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
        body = {"status": "ready", "backend": config.model_backend}
        if request.url.path == "/core-ready":
            body["inference"] = "ready" if model_ready else "degraded"
        return JSONResponse(body)

    return api
