from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = Field(alias="DATABASE_URL")
    admin_token: str = Field(alias="ADMIN_TOKEN")
    admin_basic_username: str | None = Field(default=None, alias="ADMIN_BASIC_USERNAME")
    admin_basic_password: str | None = Field(default=None, alias="ADMIN_BASIC_PASSWORD")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
