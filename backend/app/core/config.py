from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "jac-rag"
APP_VERSION = "0.1.0"
DEFAULT_JWT_SECRET = "dev-insecure-secret-change-me-0123456789"
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str
    database_url: str
    sql_echo: bool

    jwt_secret: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    invitation_expire_days: int

    storage_dir: str
    max_upload_mb: int

    qdrant_url: str
    qdrant_api_key: str | None = None

    embedding_model: str
    embedding_dim: int
    chunk_size: int
    chunk_overlap: int
    chunk_max_size: int
    chunk_table_context: bool
    chunk_section_context: bool
    chunk_include_metadata: bool
    drop_repeated_layout: bool
    parser_debug: bool
    min_chars_per_page: int
    relevance_threshold: float
    retrieval_top_k: int
    hybrid_enabled: bool
    rrf_k: int

    ocr_enabled: bool
    ocr_dpi: int
    ocr_min_confidence: float
    ocr_image_dominance_ratio: float

    ollama_base_url: str
    ollama_default_model: str
    llm_default_provider: str

    redis_url: str
    cors_origins: str

    cookie_secure: bool
    cookie_samesite: str
    cookie_domain: str | None = None

    @property
    def is_development(self) -> bool:
        return self.environment.strip().lower() in {"development", "dev", "local", "test"}

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        if self.is_development:
            return self
        if self.jwt_secret == DEFAULT_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET must be changed from the default value outside development"
            )
        if len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters long"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
