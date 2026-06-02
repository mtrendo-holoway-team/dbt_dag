from dataclasses import dataclass
from pathlib import Path

from dbt_dag.db.session import create_db_engine
from dbt_dag.db.session import create_session_factory
from dbt_dag.db.session import init_db
from dbt_dag.dbt_runtime.adapter import create_warehouse_adapter
from dbt_dag.dbt_runtime.profiles import resolve_runtime_profile
from dbt_dag.dbt_runtime.project import resolve_project_paths
from dbt_dag.graph.builder import build_graph
from dbt_dag.graph.models import GraphPayload
from dbt_dag.manifest.models import DbtManifest
from dbt_dag.manifest.parser import load_manifest
from dbt_dag.settings import Settings
from dbt_dag.tasks.repository import NodeTaskRepository
from dbt_dag.tasks.runner import DbtTaskRunner


@dataclass(frozen=True)
class AppState:
    settings: Settings
    manifest: DbtManifest
    graph: GraphPayload
    task_repository: NodeTaskRepository
    task_runner: DbtTaskRunner


def build_app_state(settings: Settings, start_dir: Path | None = None) -> AppState:
    paths = resolve_project_paths(settings, start_dir=start_dir)
    runtime_profile = resolve_runtime_profile(paths, settings.dbt_target)
    create_warehouse_adapter(runtime_profile).validate_connection()
    manifest = load_manifest(paths.manifest_path)
    engine = create_db_engine(settings.sqlite_path)
    init_db(engine)
    session_factory = create_session_factory(engine)
    task_repository = NodeTaskRepository(session_factory)
    return AppState(
        settings=settings,
        manifest=manifest,
        graph=build_graph(manifest),
        task_repository=task_repository,
        task_runner=DbtTaskRunner(task_repository, runtime_profile),
    )
