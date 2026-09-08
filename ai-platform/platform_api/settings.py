"""Single source of configuration. Everything comes from the environment."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    finops_strong_model: str = "claude-sonnet-4-6"
    finops_cheap_model: str = "claude-haiku-4-5-20251001"
    database_url: str = "postgresql+psycopg://finops:finops@localhost:5432/finops"
    enterprise_base_url: str = "http://localhost:8080"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    ai_platform_split: bool = False
    service_name: str = "ai-platform"
    traces_enabled: bool = True  # persist spans to Postgres for the Trace screen

    @field_validator("database_url")
    @classmethod
    def _require_psycopg_driver(cls, v: str) -> str:
        # managed Postgres (Railway, etc.) hands out a bare postgresql:// URL;
        # SQLAlchemy needs the driver named.
        return (
            v.replace("postgresql://", "postgresql+psycopg://", 1)
            if v.startswith("postgresql://")
            else v
        )


settings = Settings()
