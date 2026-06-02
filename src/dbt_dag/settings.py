from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_host: str
    app_port: int
    sqlite_path: Path
    dbt_project_dir: Path | None
    dbt_profiles_dir: Path | None
    dbt_target: str | None


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser().resolve()


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        app_host=os.getenv("APP_HOST", "127.0.0.1"),
        app_port=int(os.getenv("APP_PORT", "5678")),
        sqlite_path=Path(os.getenv("SQLITE_PATH", ".dbt_dag.sqlite")).expanduser(),
        dbt_project_dir=_optional_path(os.getenv("DBT_PROJECT_DIR")),
        dbt_profiles_dir=_optional_path(os.getenv("DBT_PROFILES_DIR")),
        dbt_target=os.getenv("DBT_TARGET") or None,
    )
