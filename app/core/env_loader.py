import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ENV = "local"
SUPPORTED_ENVS = {"local", "cloud"}


def get_runtime_env() -> str:
    env = os.getenv("ENV", DEFAULT_ENV).strip().lower()
    return env if env in SUPPORTED_ENVS else DEFAULT_ENV


def resolve_env_file() -> str:
    explicit_env_file = os.getenv("ENV_FILE")
    if explicit_env_file:
        explicit_path = Path(explicit_env_file)
        if not explicit_path.is_absolute():
            explicit_path = ROOT_DIR / explicit_path
        return str(explicit_path)

    return str(ROOT_DIR / f".env.{get_runtime_env()}")


def load_environment() -> str:
    env_file = resolve_env_file()
    load_dotenv(env_file, override=False)
    return env_file
