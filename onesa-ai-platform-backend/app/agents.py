import asyncio
from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app import capacity
from app.agent_runtime import (
    BasicPlanner,
    ModelToolPlanner,
    Tool,
    ToolCall,
    ToolRegistry,
    default_registry,
    planning_failure_reason,
)
from app.auth import DB, Auth, authenticated
from app.errors import fail
from app.models import AgentRun, now
from app.observability import (
    agent_outcomes,
    agent_planning_failure_reasons,
    agent_planning_failures,
)
from app.pagination import page
from app.responses import AgentRunList, AgentRunOut, ToolList
from app.schemas import Strict

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])
registry = default_registry()


class InvestigationFacts(Strict):
    investigation_id: UUID
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def scoped_registry(request: Request, user_id: UUID) -> ToolRegistry:
    """Bind authority in server context, never in model-supplied arguments."""
    from app.industrial import owned

    if not (
        request.app.state.settings.industrial_demo_enabled
        and request.app.state.settings.industrial_import_enabled
    ):
        return registry
    current = ToolRegistry()
    current.tools.update(registry.tools)
    if (
        request.app.state.settings.industrial_demo_enabled
        and request.app.state.settings.industrial_import_enabled
    ):

        async def facts(arguments: Any) -> dict[str, Any]:
            body = InvestigationFacts.model_validate(arguments.model_dump())

            def read() -> dict[str, Any]:
                with Session(request.app.state.engine) as check:
                    identity = authenticated(request, check, request.cookies.get("onesa_session"))
                    if identity[0].id != user_id:
                        fail(403, "source_access_denied", "Evidence access is no longer available")
                    row = owned(check, body.investigation_id, user_id)
                    if row.payload["snapshot_sha256"] != body.snapshot_sha256:
                        fail(
                            409, "source_revision_changed", "Select the saved source revision again"
                        )
                    return {
                        "investigation_id": str(row.id),
                        "snapshot_sha256": body.snapshot_sha256,
                        "selection": row.payload["selection"],
                        "facts": row.payload["facts"],
                        "coverage": row.payload["coverage"],
                        "cause": "not_established",
                    }

            return await run_in_threadpool(read)

        current.register("industrial_facts", Tool(InvestigationFacts, facts))
    return current


class RunRequest(Strict):
    id: UUID = Field(default_factory=uuid4)
    goal: str = Field(min_length=1, max_length=4000)
    steps: list[ToolCall] = Field(default_factory=list, max_length=8)
    allowed_tools: list[str] = Field(default_factory=list, max_length=8)


def output(row: AgentRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "goal": row.goal,
        "status": row.status,
        "steps": row.steps,
        "created_at": row.created_at,
    }


@router.get("/tools", response_model=ToolList)
def tools(request: Request, auth: Auth) -> dict[str, Any]:
    return {
        "items": [
            {
                "name": name,
                "schema": tool.schema.model_json_schema(),
                "effect": "read-only owned evidence"
                if name == "industrial_facts"
                else "local computation",
            }
            for name, tool in scoped_registry(request, auth[0].id).tools.items()
        ]
    }


@router.post("/runs", status_code=201, response_model=AgentRunOut)
async def execute(body: RunRequest, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    current = scoped_registry(request, auth[0].id)
    allowed = set(body.allowed_tools) & set(current.tools)
    if not allowed:
        fail(403, "tool_not_allowed", "Grant permission for each requested tool")
    if any(call.tool not in allowed for call in body.steps):
        fail(403, "tool_not_allowed", "Grant permission for each requested tool")
    # Invalid permissions must not reserve model capacity or enter response-stream
    # lease checks. Valid runs retain the same shared admission and expiry limits.
    lease = await run_in_threadpool(capacity.begin, request)
    try:
        result = await execute_admitted(body, request, db, auth[0].id, allowed, current)
        if not await run_in_threadpool(capacity.active, request, lease):
            fail(503, "generation_lease_lost", "Unable to verify active request authority")
        return result
    finally:
        await run_in_threadpool(capacity.end, request, lease)


async def execute_admitted(
    body: RunRequest,
    request: Request,
    db: Session,
    user_id: UUID,
    allowed: set[str],
    tool_registry: ToolRegistry,
) -> dict[str, Any]:
    try:
        async with asyncio.timeout(request.app.state.settings.generation_timeout):
            planner = (
                BasicPlanner()
                if request.app.state.settings.model_backend == "mock"
                else ModelToolPlanner(request.app.state.model_client, tool_registry, allowed)
            )
            calls = body.steps or await planner.plan(body.goal)
    except Exception as error:
        agent_planning_failures.inc()
        agent_planning_failure_reasons.labels(planning_failure_reason(error)).inc()
        fail(503, "planning_failed", "Unable to produce a valid tool plan")
    if any(call.tool not in allowed for call in calls):
        agent_planning_failures.inc()
        fail(403, "tool_not_allowed", "Grant permission for each requested tool")
    row = AgentRun(id=body.id, user_id=user_id, goal=body.goal)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "run_exists", "Run identifier already exists")
    saved: dict[str, Any] | None = None
    steps: list[dict[str, Any]] = []
    status = "cancelled"
    try:
        async with asyncio.timeout(10):
            for call in calls:
                with Session(request.app.state.engine) as check:
                    current = check.get(AgentRun, row.id)
                    cancelled = current is None or current.status == "cancelled"
                if cancelled or await request.is_disconnected():
                    break
                result = await tool_registry.execute(call, allowed)
                steps.append({"tool": call.tool, "status": "completed", "result": result})
            else:
                status = "completed"
    except Exception:
        status = "failed"
        steps.append({"status": "failed", "error": "Tool validation or execution failed"})
    finally:
        with Session(request.app.state.engine) as save:
            current = save.scalar(select(AgentRun).where(AgentRun.id == row.id).with_for_update())
            if current:
                current.status = "cancelled" if current.status == "cancelled" else status
                current.steps = steps
                save.commit()
                agent_outcomes.labels(current.status).inc()
                saved = output(current)
    if saved is None:
        fail(404, "not_found", "Agent run no longer exists")
    return saved


def owned_run(db: Session, identifier: UUID, user_id: UUID) -> AgentRun:
    row = db.scalar(select(AgentRun).where(AgentRun.id == identifier, AgentRun.user_id == user_id))
    if row is None:
        fail(404, "not_found", "Agent run not found")
    if row.status == "running" and row.created_at < now() - timedelta(seconds=15):
        row.status = "failed"
        db.commit()
    return row


@router.get("/runs", response_model=AgentRunList)
def listing(
    db: DB,
    auth: Auth,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> dict[str, Any]:
    rows, following = page(
        db,
        AgentRun,
        select(AgentRun).where(AgentRun.user_id == auth[0].id),
        limit,
        0,
        cursor,
        auth[0].id,
        "runs",
    )
    return {
        "items": [output(owned_run(db, row.id, auth[0].id)) for row in rows],
        "next_cursor": following,
    }


@router.get("/runs/{identifier}", response_model=AgentRunOut)
def detail(identifier: UUID, db: DB, auth: Auth) -> dict[str, Any]:
    return output(owned_run(db, identifier, auth[0].id))


@router.post("/runs/{identifier}/cancel", response_model=AgentRunOut)
def cancel(identifier: UUID, db: DB, auth: Auth) -> dict[str, Any]:
    row = owned_run(db, identifier, auth[0].id)
    if row.status != "running":
        fail(409, "run_finished", "Run is no longer running")
    row.status = "cancelled"
    db.commit()
    return output(row)
