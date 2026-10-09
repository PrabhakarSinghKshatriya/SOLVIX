from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SOLVIX API"
    app_version: str = "1.0.0"
    app_env: str = "development"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "solvix"
    google_client_id: str = ""

    frontend_url: str = "http://localhost:5173"

    jwt_secret_key: str = "change-this-development-secret"
    jwt_access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_security_settings(self):
        if self.jwt_access_token_expire_minutes <= 0:
            raise ValueError(
                "JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be greater than zero"
            )

        if self.app_env.strip().lower() == "production":
            secret = self.jwt_secret_key

            if secret == "change-this-development-secret":
                raise ValueError(
                    "Production requires a custom JWT secret"
                )

            if len(secret) < 32:
                raise ValueError(
                    "Production JWT secret must be at least 32 characters"
                )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
