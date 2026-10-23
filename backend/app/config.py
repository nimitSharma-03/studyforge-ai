"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", description="development | production | test")
    database_url: str = Field(default=f"sqlite:///{(BACKEND_DIR / 'data' / 'studyforge.db').as_posix()}")
    # Uploaded files are parsed in memory and discarded, and exports are rendered in memory,
    # so no upload or export directory is needed (this also suits Render's ephemeral disk).
    max_upload_mb: int = Field(default=25, ge=1, le=200)
    max_pages: int = Field(default=400, ge=1)
    max_documents_per_workspace: int = Field(default=15, ge=1)
    processing_timeout_seconds: int = Field(default=120, ge=5)
    allowed_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")
    uploads_per_hour: int = Field(default=20, ge=1)
    quizzes_per_hour: int = Field(default=120, ge=1)
    workspaces_per_hour_per_ip: int = Field(default=30, ge=1)
    # Optional local LLM (Ollama). Empty means disabled.
    ollama_url: str = Field(default="")
    ollama_model: str = Field(default="llama3.2")
    ollama_timeout_seconds: float = Field(default=60.0)
    enable_docs: bool | None = Field(default=None, description="Expose /docs; defaults to on outside production")

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, value: str) -> str:
        # Render and Heroku style URLs use postgres:// or postgresql://; SQLAlchemy needs the psycopg driver name.
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def docs_enabled(self) -> bool:
        return self.enable_docs if self.enable_docs is not None else not self.is_production

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.ollama_url.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
