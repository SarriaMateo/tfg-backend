from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

from app.core.env_loader import resolve_env_file

class Settings(BaseSettings):
    app_name: str
    env: str
    gcs_bucket: Optional[str] = None

    db_user: str
    db_password: str
    db_host: str
    db_port: int = 3306
    db_name: str

    secret_key: str
    access_token_expire_minutes: int

    model_config = SettingsConfigDict(
        env_file=resolve_env_file(),
        env_file_encoding="utf-8",
    )

    @property
    def is_cloudsql_socket(self) -> bool:
        return self.db_host.startswith("/cloudsql/")

    @property
    def database_url(self) -> str:
        if self.is_cloudsql_socket:
            return (
                f"mysql+pymysql://{self.db_user}:{self.db_password}@/"
                f"{self.db_name}?unix_socket={self.db_host}"
            )

        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

settings = Settings()
