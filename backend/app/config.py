from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SOLVIX API"
    app_version: str = "1.0.0"
    app_env: str = "development"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "solvix"

    frontend_url: str = "http://localhost:5173"

    jwt_secret_key: str = "change-this-development-secret"
    jwt_access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
