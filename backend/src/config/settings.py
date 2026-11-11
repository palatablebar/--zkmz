"""Runtime configuration (env-var overridable)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # --- database ---
    DB_NAME: str = "featpoint"
    DB_USER: str = "featpoint"
    DB_PASSWORD: str = "featpoint_pwd"
    DB_HOST: str = "db"
    DB_PORT: int = 5432

    # --- auth ---
    JWT_SECRET: str = "featpoint_local_demo_secret_change_me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 8

    # --- infra ---
    REDIS_URL: str = "redis://redis:6379/0"
    APP_ENV: str = "docker"

    # --- limits (cross-cutting rate limit / daily quota) ---
    RATE_WINDOW_SECONDS: int = 60
    RATE_WINDOW_MAX: int = 60
    DAILY_RUN_QUOTA: int = 20

    # --- demo seed ---
    SEED_DEMO: bool = True
    SEED_EVENT_DAYS: int = 90

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
