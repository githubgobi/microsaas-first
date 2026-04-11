from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "AI Error Debugger"
    DEBUG: bool = False

    # Security — ALGORITHM is intentionally NOT env-configurable (algorithm confusion attacks)
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS — never use "*" with credentials; list allowed origins explicitly
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@host:port/db
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    # Recycle connections after this many seconds — prevents stale sockets behind
    # load balancers or firewalls that silently drop idle TCP connections
    DB_POOL_RECYCLE: int = 1800
    # Hard ceiling on any single statement (ms). Guards against runaway queries
    # holding a pool connection indefinitely. Keep well above longest expected query.
    DB_STATEMENT_TIMEOUT_MS: int = 30_000

    # AI
    ANTHROPIC_API_KEY: str = ""  # empty = AI disabled; raises 503 at call time
    AI_MODEL: str = "claude-sonnet-4-6"
    AI_TIMEOUT_SECONDS: float = 60.0   # per-request ceiling for the AI API call
    MAX_ANALYSES_PER_DAY: int = 20     # per-user daily cap; 0 = unlimited

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v


# Algorithm is a security constant — never read from environment
JWT_ALGORITHM = "HS256"


@lru_cache
def get_settings() -> Settings:
    return Settings()
