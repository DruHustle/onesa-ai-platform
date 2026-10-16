import asyncio
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent_runtime import (
    BasicPlanner,
    ModelToolPlanner,
    ToolCall,
    default_registry,
    planning_failure_reason,
)
from app.auth import DB, Auth
from app.errors import fail
from app.models import AgentRun, now
from app.observability import (
    agent_outcomes,
    agent_planning_failure_reasons,
    agent_planning_failures,
)
from app.responses import AgentRunList, AgentRunOut, ToolList
from app.schemas import Strict

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])
registry = default_registry()


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
def tools(auth: Auth) -> dict[str, Any]:
    return {
        "items": [
            {"name": name, "schema": tool.schema.model_json_schema(), "effect": "local computation"}
            for name, tool in registry.tools.items()
        ]
    }


@router.post("/runs", status_code=201, response_model=AgentRunOut)
async def execute(body: RunRequest, request: Request, db: DB, auth: Auth) -> dict[str, Any]:
    allowed = set(body.allowed_tools) & set(registry.tools)
    try:
        async with asyncio.timeout(request.app.state.settings.generation_timeout):
            planner = (
                BasicPlanner()
                if request.app.state.settings.model_backend == "mock"
                else ModelToolPlanner(request.app.state.model_client, registry, allowed)
            )
            calls = body.steps or await planner.plan(body.goal)
    except Exception as error:
        agent_planning_failures.inc()
        agent_planning_failure_reasons.labels(planning_failure_reason(error)).inc()
        fail(503, "planning_failed", "Unable to produce a valid tool plan")
    if any(call.tool not in allowed for call in calls):
        agent_planning_failures.inc()
        fail(403, "tool_not_allowed", "Grant permission for each requested tool")
    row = AgentRun(id=body.id, user_id=auth[0].id, goal=body.goal)
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
                result = await registry.execute(call, allowed)
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
def listing(db: DB, auth: Auth) -> dict[str, Any]:
    rows = db.scalars(
        select(AgentRun)
        .where(AgentRun.user_id == auth[0].id)
        .order_by(AgentRun.created_at.desc())
        .limit(100)
    )
    return {"items": [output(owned_run(db, row.id, auth[0].id)) for row in rows]}


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
