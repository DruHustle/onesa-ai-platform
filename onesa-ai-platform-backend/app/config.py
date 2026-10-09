"""Validated deployment configuration; no implicit backend fallback."""

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ONESA_", extra="ignore")

    model_backend: Literal["mock", "ollama", "vllm"] = "mock"
    model_name: str = Field(default="Qwen/Qwen3-4B-Instruct-2507", min_length=1)
    model_max_output_tokens: int = Field(default=1024, ge=1, le=8192)
    model_context_length: int = Field(default=8192, ge=512, le=131072)
    model_quantization: str | None = Field(
        default=None, max_length=64, pattern=r"^[A-Za-z0-9_ .-]+$"
    )
    model_revision: str | None = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    model_modalities: list[Literal["text", "vision", "speech"]] = Field(default=["text"])
    model_temperature: float = Field(default=0.7, ge=0, le=2)
    database_url: str | None = None
    public_origin: str = "http://localhost:3000"
    secure_cookies: bool = False
    session_hours: int = Field(default=24, ge=1, le=168)
    auth_rate_limit: int = Field(default=10, ge=1, le=1000)
    auth_hash_concurrency: int = Field(default=4, ge=1, le=16)
    knowledge_upload_concurrency: int = Field(default=1, ge=1, le=4)
    auth_peer_rate_limit: int = Field(default=100, ge=1, le=10000)
    generation_timeout: float = Field(default=60, ge=1, le=120)
    model_base_url: str = "http://inference:8000/v1"
    model_api_key: str = ""
    embedding_backend: Literal["lexical", "http"] = "lexical"
    embedding_name: str = "onesa-lexical-256-v1"
    embedding_base_url: str = "http://embeddings:8000/v1"
    embedding_api_key: str = ""
    metrics_token: str = ""
    embedding_revision: str = "1"
    documentation_sources_directory: str = "/app/docs-sources"
    documentation_engineering_user_ids: list[str] = Field(default_factory=list)
    environment: Literal["development", "test", "staging", "production"] = "development"

    @field_validator("model_quantization", "model_revision", mode="before")
    @classmethod
    def optional_metadata(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def production_defaults(self) -> Self:
        if self.environment in {"staging", "production"}:
            if not self.secure_cookies or not self.public_origin.startswith("https://"):
                raise ValueError("Production requires HTTPS origin and Secure cookies")
            if not self.database_url or len(self.metrics_token) < 32:
                raise ValueError("Production requires database and a 32-character metrics token")
        return self
