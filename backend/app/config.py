from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite:///./debtmap.db"
    fernet_key: str = ""
    github_token: str = ""
    max_files_per_repo: int = 500
    max_file_bytes: int = 500_000
    clone_depth: int = 300
    supported_extensions_csv: str = ".py,.ts,.tsx,.js,.jsx"
    rate_limit_per_hour: int = 10
    cors_origins_csv: str = "http://localhost:3000"

    @property
    def supported_extensions(self) -> list[str]:
        return [s.strip() for s in self.supported_extensions_csv.split(",") if s.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [s.strip() for s in self.cors_origins_csv.split(",") if s.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
