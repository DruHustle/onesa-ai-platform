from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class Credentials(Strict):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class Register(Credentials):
    display_name: str = Field(min_length=1, max_length=80)
    invitation_token: str | None = Field(default=None, min_length=40, max_length=128)


class SafeUser(Strict):
    id: UUID
    email: str
    display_name: str


class ProfileUpdate(Strict):
    display_name: str = Field(min_length=1, max_length=80, pattern=r"\S")


class PasswordProof(Strict):
    current_password: str = Field(min_length=1, max_length=128)


class PasswordChange(PasswordProof):
    new_password: str = Field(min_length=12, max_length=128)


class SessionOut(Strict):
    id: UUID
    created_at: datetime
    expires_at: datetime
    current: bool


class SessionList(Strict):
    items: list[SessionOut]
    total: int
    limit: int


class ConversationCreate(Strict):
    title: str = Field(default="New conversation", min_length=1, max_length=200)
    selected_model_id: str = "default"


class Rename(Strict):
    title: str = Field(min_length=1, max_length=200)


class ConversationOut(Strict):
    id: UUID
    title: str
    selected_model_id: str
    created_at: datetime
    updated_at: datetime


class MessageOut(Strict):
    id: UUID
    role: str
    content: dict[str, Any]
    status: str
    sequence: int


class ChatRequest(Strict):
    conversation_id: UUID
    content: str = Field(min_length=1, max_length=32000)
    model_id: str = "default"
    stream: bool = True
    document_ids: list[UUID] = Field(default_factory=list, max_length=20)


class ConversationList(Strict):
    items: list[ConversationOut]
    total: int
    limit: int
    offset: int


class ConversationDetail(Strict):
    conversation: ConversationOut
    messages: list[MessageOut]


class CancelGeneration(Strict):
    run_id: UUID
