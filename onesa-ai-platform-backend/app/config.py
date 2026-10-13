"""Validated deployment configuration; no implicit backend fallback."""

import ipaddress
import os
import re
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ONESA_", extra="ignore", hide_input_in_errors=True
    )

    model_backend: Literal["mock", "ollama", "vllm", "cloudflare"] = "mock"
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
    registration_mode: Literal["open", "invitation"] = "open"
    access_operator_user_ids: list[str] = Field(default_factory=list)
    auth_delivery_key: str = ""
    mail_provider: Literal["disabled", "resend"] = "disabled"
    resend_api_key: str = ""
    mail_from: str = ""
    mail_reply_to: str = ""
    invitation_hours: int = Field(default=48, ge=1, le=168)
    recovery_minutes: int = Field(default=10, ge=5, le=10)
    model_user_concurrency: int = Field(default=2, ge=1, le=32)
    model_global_concurrency: int = Field(default=8, ge=1, le=128)
    model_user_requests_per_minute: int = Field(default=20, ge=1, le=1000)
    model_global_requests_per_minute: int = Field(default=120, ge=1, le=10000)
    model_user_reserved_tokens_per_minute: int = Field(default=256000, ge=1024)
    model_global_reserved_tokens_per_minute: int = Field(default=1024000, ge=1024)
    knowledge_max_documents: int = Field(default=100, ge=1, le=10000)
    knowledge_user_text_bytes: int = Field(default=16 * 1024 * 1024, ge=256000)
    knowledge_global_text_bytes: int = Field(default=256 * 1024 * 1024, ge=256000)
    generation_timeout: float = Field(default=60, ge=1, le=120)
    model_base_url: str = ""
    model_api_key: str = ""
    embedding_backend: Literal["lexical", "http", "cloudflare"] = "lexical"
    embedding_name: str = "onesa-lexical-256-v1"
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    metrics_token: str = ""
    embedding_revision: str = "1"
    embedding_query_instruction: str = Field(default="", max_length=800)
    documentation_sources_directory: str = "/app/docs-sources"
    documentation_engineering_user_ids: list[str] = Field(default_factory=list)
    environment: Literal["development", "test", "staging", "production"] = "development"

    @field_validator("model_quantization", "model_revision", mode="before")
    @classmethod
    def optional_metadata(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def production_defaults(self) -> Self:
        if os.environ.get("RENDER") == "true" and self.environment not in {
            "staging",
            "production",
        }:
            raise ValueError("Render requires explicit staging or production configuration")
        origin = urlsplit(self.public_origin)
        if (
            not origin.hostname
            or origin.username
            or origin.password
            or origin.path
            or origin.query
            or origin.fragment
        ):
            raise ValueError("Public origin must be an exact origin without a path or credentials")
        if self.environment in {"staging", "production"}:
            if not self.secure_cookies or not self.public_origin.startswith("https://"):
                raise ValueError("Production requires HTTPS origin and Secure cookies")
            if not self.database_url or len(self.metrics_token) < 32:
                raise ValueError("Production requires database and a 32-character metrics token")
        if self.mail_provider != "disabled" and (
            len(self.auth_delivery_key) < 48 or not self.resend_api_key or not self.mail_from
        ):
            raise ValueError(
                "Authentication mail requires a persistent delivery key and sender credentials"
            )
        if self.model_backend == "cloudflare":
            if (
                not re.fullmatch(
                    r"https://api\.cloudflare\.com/client/v4/accounts/[a-f0-9]{32}/ai/v1/?",
                    self.model_base_url,
                )
                or len(self.model_api_key) < 32
                or self.model_name != "@cf/qwen/qwen3-30b-a3b-fp8"
            ):
                raise ValueError(
                    "Cloudflare inference requires its account HTTPS endpoint, "
                    "token and reviewed model"
                )
        if self.embedding_backend == "cloudflare":
            if (
                not re.fullmatch(
                    r"https://api\.cloudflare\.com/client/v4/accounts/[a-f0-9]{32}/ai/?",
                    self.embedding_base_url,
                )
                or len(self.embedding_api_key) < 32
                or self.embedding_name != "@cf/qwen/qwen3-embedding-0.6b"
                or self.embedding_revision != "cf-qwen3-mrl256-v1"
            ):
                raise ValueError(
                    "Cloudflare embeddings require their account HTTPS endpoint, "
                    "token and versioned Qwen256 profile"
                )
        if self.environment == "production":
            if self.model_backend == "mock":
                raise ValueError("Production AI requires a configured real inference service")
            endpoint = urlsplit(self.model_base_url)
            host = (endpoint.hostname or "").lower().rstrip(".")
            local = host in {
                "localhost",
                "host.docker.internal",
                "inference",
                "ollama",
            } or host.endswith(".localhost")
            try:
                address = ipaddress.ip_address(host)
                local = (
                    local
                    or address.is_loopback
                    or address.is_unspecified
                    or address.is_link_local
                    or (
                        isinstance(address, ipaddress.IPv6Address)
                        and address.ipv4_mapped is not None
                        and address.ipv4_mapped.is_loopback
                    )
                )
            except ValueError:
                pass
            if (
                endpoint.scheme != "https"
                or local
                or not host
                or endpoint.username
                or endpoint.password
                or not self.model_api_key
            ):
                raise ValueError(
                    "Production inference requires an authenticated HTTPS "
                    "endpoint without development addresses"
                )
        if self.environment == "production" and self.embedding_backend == "http":
            endpoint = urlsplit(self.embedding_base_url)
            host = (endpoint.hostname or "").lower().rstrip(".")
            local = host in {"localhost", "host.docker.internal", "embeddings"} or host.endswith(
                ".localhost"
            )
            try:
                address = ipaddress.ip_address(host)
                local = (
                    local or address.is_loopback or address.is_unspecified or address.is_link_local
                )
            except ValueError:
                pass
            if (
                endpoint.scheme != "https"
                or not host
                or local
                or endpoint.username
                or endpoint.password
                or not self.embedding_api_key
            ):
                raise ValueError("Production embeddings require an authenticated HTTPS endpoint")
        return self
