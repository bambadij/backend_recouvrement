from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "API Recouvrement"
    environment: str = "development"
    debug: bool = True

    database_url: str = (
        "postgresql+asyncpg://recouvrement_user:recouvrement_password@localhost:5432/recouvrement_db"
    )

    cors_origins: list[str] = ["http://localhost:4200"]

    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # Si definis, un compte SUPER_ADMIN est cree automatiquement au demarrage
    # (uniquement si aucun compte n'existe deja pour cet email).
    super_admin_email: str | None = None
    super_admin_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
