from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.env_loader import resolve_env_file

class Settings(BaseSettings):
    app_name: str
    env: str

    db_user: str
    db_password: str
    db_host: str
    db_port: int
    db_name: str

    secret_key: str
    access_token_expire_minutes: int

    model_config = SettingsConfigDict(
        env_file=resolve_env_file(),
        env_file_encoding="utf-8",
    )

settings = Settings()
