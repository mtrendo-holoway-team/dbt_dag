from pathlib import Path

from dbt_dag.dbt_runtime.types import DbtProjectPaths
from dbt_dag.settings import Settings


def discover_project_dir(start_dir: Path, configured_dir: Path | None) -> Path:
    if configured_dir is not None:
        return configured_dir

    current = start_dir.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "dbt_project.yml").exists():
            return candidate

    raise FileNotFoundError("dbt_project.yml was not found; set DBT_PROJECT_DIR")


def discover_manifest_path(project_dir: Path) -> Path:
    manifest_path = project_dir / "target" / "manifest.json"
    if manifest_path.exists():
        return manifest_path

    raise FileNotFoundError("target/manifest.json was not found under DBT_PROJECT_DIR")


def discover_profiles_dir(configured_dir: Path | None) -> Path:
    if configured_dir is not None:
        return configured_dir
    return Path.home() / ".dbt"


def resolve_project_paths(settings: Settings, start_dir: Path | None = None) -> DbtProjectPaths:
    project_dir = discover_project_dir(start_dir or Path.cwd(), settings.dbt_project_dir)
    return DbtProjectPaths(
        project_dir=project_dir,
        manifest_path=discover_manifest_path(project_dir),
        profiles_dir=discover_profiles_dir(settings.dbt_profiles_dir),
    )
