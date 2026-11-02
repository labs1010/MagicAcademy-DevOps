"""Environment selection is explicit; real .env files are never committed."""

import os
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    app_env: Literal["sandbox", "production"] = "sandbox"
    database_url: str
    jwt_secret: str = Field(min_length=32)
    token_minutes: int = Field(default=60, ge=1, le=1440)
    model_config = SettingsConfigDict(extra="ignore")

    @model_validator(mode="after")
    def validate_environment(self):
        url = make_url(self.database_url)
        if url.drivername != "postgresql+psycopg":
            raise ValueError("Use PostgreSQL with psycopg")
        required = "magic_production" if self.app_env == "production" else "magic_sandbox"
        if url.database not in (
            {required, "magic_test"} if self.app_env == "sandbox" else {required}
        ):
            raise ValueError(f"Wrong database for {self.app_env}")
        if self.jwt_secret.startswith("CHANGE_"):
            raise ValueError("Generate a real JWT secret with scripts/configure.py")
        return self

    @property
    def debug(self):
        return self.app_env == "sandbox"


def load_settings():
    environment = os.getenv("APP_ENV", "sandbox")
    # Real environment variables override values read from this file.
    return Settings(_env_file=f".env.{environment}", _env_file_encoding="utf-8")
