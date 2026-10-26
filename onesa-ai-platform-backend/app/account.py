"""Password-confirmed, owner-scoped live account export and deletion."""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Request, Response
from sqlalchemy import select, text

from app.auth import DB, Auth, lock_account, prove_password
from app.errors import fail
from app.industrial import InvestigationOut
from app.industrial import output as investigation_output
from app.models import (
    AgentRun,
    Conversation,
    Document,
    IndustrialInvestigation,
    InferenceRun,
    Message,
    Trip,
    now,
)
from app.responses import AgentRunOut, DocumentDetail, TripOut
from app.schemas import ConversationOut, MessageOut, PasswordProof, SafeUser, Strict
from app.travel import output as trip_output
from app.twin_files import FileStore
from app.twin_models import TwinFile

router = APIRouter(prefix="/api/v1/account", tags=["account"])
MAX_ROWS = 10000
MAX_BYTES = 2 * 1024 * 1024


class ExportConversation(Strict):
    conversation: ConversationOut
    messages: list[MessageOut]


class AccountExport(Strict):
    format_version: Literal[1] = 1
    exported_at: datetime
    account: SafeUser
    conversations: list[ExportConversation]
    documents: list[DocumentDetail]
    agent_runs: list[AgentRunOut]
    trips: list[TripOut]
    industrial_investigations: list[InvestigationOut]
    digital_twins: dict[str, Any]
    scope: str


class DeleteAccount(PasswordProof):
    confirmation: Literal["DELETE MY ACCOUNT"]


@router.post("/export", response_model=AccountExport)
def export_account(
    body: PasswordProof, request: Request, response: Response, db: DB, auth: Auth
) -> AccountExport:
    prove_password(request, db, auth, body)
    db.commit()
    # Obtain one consistent snapshot after throttling has committed, then recheck
    # the session. A simultaneous password change cannot export through an old token.
    db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
    user = lock_account(db, auth)
    count, size = 0, 0
    # Static identifiers only: never interpolate caller-provided SQL identifiers.
    # Normal AI and the isolated demo migrate independently. Inspect this snapshot,
    # never a feature flag or cached result: disabled features still own user data.
    industrial_present = db.scalar(
        text("SELECT to_regclass('industrial_investigations') IS NOT NULL")
    )
    twins_present = db.scalar(text("SELECT to_regclass('twin_assets') IS NOT NULL"))
    scopes = [
        ("conversations t WHERE t.user_id=:owner", "pg_column_size(t)"),
        (
            "messages t JOIN conversations c ON c.id=t.conversation_id WHERE c.user_id=:owner",
            "octet_length(t.content::text)+pg_column_size(t)",
        ),
        ("documents t WHERE t.user_id=:owner", "octet_length(t.text)+pg_column_size(t)"),
        (
            "agent_runs t WHERE t.user_id=:owner",
            "octet_length(t.goal)+octet_length(t.steps::text)+pg_column_size(t)",
        ),
        (
            "trips t WHERE t.user_id=:owner",
            "octet_length(t.preferences)+octet_length(t.itinerary::text)+pg_column_size(t)",
        ),
    ]
    if industrial_present:
        scopes.append(
            (
                "industrial_investigations t WHERE t.user_id=:owner",
                "octet_length(t.payload::text)+pg_column_size(t)",
            )
        )
    if twins_present:
        for table in (
            "twin_templates",
            "twin_assets",
            "twin_files",
            "twin_models",
            "twin_sources",
            "twin_notes",
        ):
            scopes.append((table + " t WHERE t.user_id=:owner", "pg_column_size(t)"))
        for table in ("twin_readings", "twin_events"):
            scopes.append(
                (
                    table + " t JOIN twin_assets a ON a.id=t.asset_id WHERE a.user_id=:owner",
                    "pg_column_size(t)",
                )
            )
    for scope, length in scopes:
        row = db.execute(
            text("SELECT count(*),coalesce(sum(" + length + "),0) FROM " + scope),
            {"owner": user.id},
        ).one()
        count += row[0]
        size += row[1]
    if count > MAX_ROWS or size > MAX_BYTES:
        fail(
            413,
            "export_too_large",
            "This account exceeds the self-service export limit; "
            "request a secure full export from support",
        )
    conversations = db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.created_at, Conversation.id)
    ).all()
    messages = db.scalars(
        select(Message)
        .join(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Message.conversation_id, Message.sequence)
    ).all()
    grouped: dict[str, list[MessageOut]] = {}
    for message in messages:
        grouped.setdefault(str(message.conversation_id), []).append(
            MessageOut.model_validate(message)
        )
    exported = AccountExport(
        exported_at=now(),
        account=SafeUser.model_validate(user),
        conversations=[
            ExportConversation(
                conversation=ConversationOut.model_validate(row),
                messages=grouped.get(str(row.id), []),
            )
            for row in conversations
        ],
        documents=[
            DocumentDetail.model_validate(row)
            for row in db.scalars(
                select(Document)
                .where(Document.user_id == user.id)
                .order_by(Document.created_at, Document.id)
            )
        ],
        agent_runs=[
            AgentRunOut.model_validate(row)
            for row in db.scalars(
                select(AgentRun)
                .where(AgentRun.user_id == user.id)
                .order_by(AgentRun.created_at, AgentRun.id)
            )
        ],
        trips=[
            TripOut.model_validate(trip_output(row))
            for row in db.scalars(
                select(Trip).where(Trip.user_id == user.id).order_by(Trip.created_at, Trip.id)
            )
        ],
        industrial_investigations=[
            InvestigationOut.model_validate(investigation_output(row))
            for row in db.scalars(
                select(IndustrialInvestigation)
                .where(IndustrialInvestigation.user_id == user.id)
                .order_by(IndustrialInvestigation.created_at, IndustrialInvestigation.id)
            )
        ]
        if industrial_present
        else [],
        digital_twins=twin_export(db, user.id) if twins_present else {},
        scope=(
            "Live profile, conversations/messages (including saved sources), "
            "extracted document text/metadata, tool runs, trips and owned Industrial "
            "investigations (immutable evidence, drafts and review decisions), including "
            "records retained while Industrial is disabled. Passwords, session "
            "credentials, derived embedding vectors and internal inference telemetry "
            "are excluded. Digital Twin equipment, model/file metadata, readings, events "
            "and inspection evidence are included even when the feature is disabled; "
            "source credentials are excluded. Original Twin binaries require their owned "
            "file download and are not embedded in this JSON. Knowledge "
            "originals are not retained. "
            "Backups are outside this export."
        ),
    )
    if len(exported.model_dump_json().encode()) > MAX_BYTES:
        fail(
            413,
            "export_too_large",
            "This account exceeds the self-service export limit; "
            "request a secure full export from support",
        )
    response.headers["Content-Disposition"] = 'attachment; filename="onesa-account-export.json"'
    return exported


@router.post("/delete", status_code=204)
def delete_account(
    body: DeleteAccount, request: Request, response: Response, db: DB, auth: Auth
) -> None:
    user = prove_password(request, db, auth, body)
    active_chat = db.scalar(
        select(InferenceRun.id)
        .where(InferenceRun.user_id == user.id, InferenceRun.status == "running")
        .limit(1)
    )
    active_agent = db.scalar(
        select(AgentRun.id)
        .where(AgentRun.user_id == user.id, AgentRun.status == "running")
        .limit(1)
    )
    if active_chat or active_agent:
        fail(409, "account_busy", "Stop active chat and tool runs before deleting your account")
    twins_present = db.scalar(text("SELECT to_regclass('twin_files') IS NOT NULL"))
    if twins_present and db.scalar(select(TwinFile.id).where(TwinFile.user_id == user.id).limit(1)):
        storage = FileStore(request.app.state.settings.digital_twins_storage_directory)
        if not storage.ready():
            fail(
                503,
                "twin_storage_unavailable",
                "Restore the private file mount before deleting equipment files and this account",
            )
        # The locked account excludes concurrent upload/creation. File removal is
        # idempotent; a database commit failure remains retryable with the same account.
        storage.remove_owner(user.id)
    # The locked parent and FK cascades make live-data deletion atomic, including
    # messages, sessions, documents/chunks/vectors, inference records, agents and trips.
    db.delete(user)
    db.commit()
    response.delete_cookie("onesa_session", path="/")
    response.delete_cookie("onesa_csrf", path="/")


def twin_export(db: DB, owner: Any) -> dict[str, Any]:
    from app.twin_models import (
        TwinAsset,
        TwinEvent,
        TwinModel,
        TwinNote,
        TwinReading,
        TwinSource,
        TwinTemplate,
    )
    from app.twins import output, reading_output

    result: dict[str, Any] = {}
    for cls in (TwinTemplate, TwinAsset, TwinFile, TwinModel, TwinSource, TwinNote):
        result[cls.__tablename__] = [
            output(r)
            for r in db.scalars(
                select(cls)
                .where(cls.user_id == owner)
                .order_by(cls.created_at, cls.id)
                .limit(MAX_ROWS + 1)
            )
        ]
    result["twin_readings"] = [
        reading_output(r)
        for r in db.scalars(
            select(TwinReading)
            .join(TwinAsset)
            .where(TwinAsset.user_id == owner)
            .order_by(TwinReading.observed_at, TwinReading.id)
            .limit(MAX_ROWS + 1)
        )
    ]
    result["twin_events"] = [
        {
            "id": str(r.id),
            "asset_id": str(r.asset_id),
            "component_id": str(r.component_id),
            "reading_id": str(r.reading_id),
            "details": r.details,
        }
        for r in db.scalars(
            select(TwinEvent)
            .join(TwinAsset)
            .where(TwinAsset.user_id == owner)
            .order_by(TwinEvent.created_at, TwinEvent.id)
            .limit(MAX_ROWS + 1)
        )
    ]
    return result
