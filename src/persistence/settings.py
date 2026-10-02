"""Настройки подключения к постоянному хранилищу."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Берёт DATABASE_URL из окружения или локального .env."""

    database_url: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()
