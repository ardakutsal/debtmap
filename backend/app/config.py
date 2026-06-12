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

    # Abuse / cost controls (Faz 1)
    # GitHub's `size` is the FULL server-side history; our depth-limited
    # shallow clone downloads ~5-20% of it (openclaw: reported 1.5 GB,
    # actual clone 285 MB). Cap generously; clone/task timeouts backstop.
    max_repo_size_kb: int = 2_000_000
    reuse_window_hours: int = 6      # serve a recent completed scan instead of re-running
    inflight_window_minutes: int = 30
    max_queue_depth: int = 25

    # Deep Scan (Faz 2) — disabled until an LLM key is set. Direct Anthropic
    # is preferred when both keys are present; OpenRouter routes to the same
    # Claude models for ~5% fee.
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    deep_scan_file_model: str = "claude-haiku-4-5"
    deep_scan_synthesis_model: str = "claude-sonnet-4-6"
    deep_scan_top_files: int = 12
    deep_scan_daily_per_ip: int = 3
    deep_scan_monthly_cap_usd: float = 100.0

    @property
    def supported_extensions(self) -> list[str]:
        return [s.strip() for s in self.supported_extensions_csv.split(",") if s.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [s.strip() for s in self.cors_origins_csv.split(",") if s.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
