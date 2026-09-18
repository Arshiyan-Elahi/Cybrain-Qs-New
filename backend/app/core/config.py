from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRET = "change-me-in-every-environment"


class Settings(BaseSettings):
    """
    Runtime configuration, resolved once and injected.

    Nothing imports a concrete value at module load; callers depend on
    `get_settings()` so tests can override it and the app can be constructed
    more than once in a process.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Cybrain QS API"
    api_v1_prefix: str = "/api/v1"
    environment: Literal["local", "staging", "production"] = "local"
    debug: bool = False

    # --- Database ----------------------------------------------------------
    database_url: str = Field(
        default="postgresql+psycopg://cybrain:cybrain_dev@localhost:5432/cybrain_qs"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle_seconds: int = 1800
    db_echo: bool = False

    # --- Auth --------------------------------------------------------------
    secret_key: str = Field(default=INSECURE_SECRET)
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"
    # Failed logins allowed per email+IP inside the window before lockout.
    login_max_attempts: int = 10
    login_window_seconds: int = 300

    # --- HTTP --------------------------------------------------------------
    cors_origins: str = "http://localhost:5173"
    max_upload_bytes: int = 25 * 1024 * 1024
    default_page_size: int = 50
    max_page_size: int = 200

    # --- Observability -----------------------------------------------------
    log_level: str = "INFO"
    # console (default local) or json (production shippers). log_json kept for
    # backward compatibility with older .env files.
    log_format: Literal["console", "json"] = "console"
    log_json: bool = False
    log_ai_content: bool = False
    log_ai_content_max_chars: int = 2000
    log_requests: bool = True
    log_retrieval: bool = True
    log_ai_routing: bool = True
    log_document_processing: bool = True

    # --- AI feature flag ---------------------------------------------------
    ai_features_enabled: bool = False

    # --- Local / remote LLM (only used when ai_features_enabled) ------------
    llm_provider: str = "ollama"
    llm_base_url: str = "http://localhost:11434"
    llm_chat_model: str = "llama3.1:8b"
    llm_embedding_model: str = "nomic-embed-text"
    llm_embedding_dimensions: int = 768
    llm_timeout_seconds: float = 120.0
    llm_api_key: str | None = None

    # --- AI primary/fallback routing ---------------------------------------
    # auto: remote OpenAI-compatible when healthy, else Gemini + local Nomic.
    # remote: remote only.  fallback: Gemini LLM + local embeddings only.
    ai_routing_mode: Literal["auto", "remote", "fallback"] = "auto"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: float = 60.0
    local_embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"
    local_embedding_dimensions: int = 768
    # Cheap remote reachability probe (connect/read); separate from generation timeout.
    ai_health_timeout_seconds: float = 2.0
    # After a remote failure, skip re-probing for this many seconds.
    ai_failover_cooldown_seconds: float = 30.0
    # Embedding compatibility self-test before allowing remote→local fallback.
    ai_embedding_compat_min_cosine: float = 0.85

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @field_validator("log_level")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _reject_insecure_production(self) -> "Settings":
        """
        A deploy that forgot SECRET_KEY must fail loudly at start-up rather
        than run with a signing key that is public in this repository.
        """
        if self.is_production:
            if self.secret_key == INSECURE_SECRET or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be set to a unique value of at least 32 characters "
                    "in production."
                )
            if self.debug:
                raise ValueError("DEBUG must be false in production.")
            if "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must not be a wildcard in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
