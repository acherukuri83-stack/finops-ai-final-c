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

    # Phase D — event-driven investigations
    events_enabled: bool = False  # run the in-process outbox consumer in the app lifespan
    event_bus: str = "outbox"  # outbox | kafka | none
    event_poll_seconds: float = 3.0  # outbox poll interval
    event_batch: int = 20  # rows drained per poll
    kafka_bootstrap: str = ""  # host:port — only for event_bus=kafka

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
