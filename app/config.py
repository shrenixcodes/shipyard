from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "shipyard"
    app_version: str = "0.1.0"
    git_sha: str = "unknown"
    log_level: str = "INFO"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "shipyard"
    postgres_password: str = "shipyard"
    postgres_db: str = "shipyard"

    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")

    db_pool_size: int = 5
    db_pool_max_overflow: int = 5
    db_pool_timeout_seconds: int = 5

    @computed_field
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
