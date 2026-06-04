from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dbt_dag.adapters.protocols import WarehouseAdapterProtocol
from dbt_dag.db.session import create_db_engine
from dbt_dag.db.session import create_session_factory
from dbt_dag.db.session import init_db
from dbt_dag.dbt_runtime.adapter import create_warehouse_adapter
from dbt_dag.dbt_runtime.profiles import resolve_runtime_profile
from dbt_dag.dbt_runtime.project import resolve_project_paths
from dbt_dag.metadata.artifacts import RunResultsArtifactReader
from dbt_dag.metadata.service import RuntimeMetadataService
from dbt_dag.metadata.warehouse import WarehouseMetadataReader
from dbt_dag.metadata.watcher import MetadataWatcher
from dbt_dag.settings import Settings
from dbt_dag.tasks.repository import NodeTaskRepository
from dbt_dag.tasks.runner import DbtTaskRunner
from dbt_dag.web.graph_state import GraphStateStore


@dataclass(frozen=True)
class AppState:
    settings: Settings
    graph_store: GraphStateStore
    task_repository: NodeTaskRepository
    task_runner: DbtTaskRunner
    metadata_watcher: MetadataWatcher
    warehouse_adapter: WarehouseAdapterProtocol


StartupProgressCallback = Callable[[str], None]


def build_app_state(
    settings: Settings,
    start_dir: Path | None = None,
    progress: StartupProgressCallback | None = None,
) -> AppState:
    _report_progress(progress, "Resolving dbt project paths")
    paths = resolve_project_paths(settings, start_dir=start_dir)
    _report_progress(progress, "Resolving active dbt profile")
    runtime_profile = resolve_runtime_profile(paths, settings.dbt_target)
    _report_progress(progress, "Preparing warehouse adapter")
    warehouse_adapter = create_warehouse_adapter(runtime_profile)
    _report_progress(progress, "Validating warehouse adapter")
    warehouse_adapter.validate_connection()
    _report_progress(progress, "Initializing local database")
    engine = create_db_engine(settings.sqlite_path)
    init_db(engine)
    session_factory = create_session_factory(engine)
    task_repository = NodeTaskRepository(session_factory)
    _report_progress(progress, "Preparing runtime metadata services")
    metadata_service = RuntimeMetadataService(
        artifact_reader=RunResultsArtifactReader(paths.project_dir),
        warehouse_reader=WarehouseMetadataReader(warehouse_adapter, runtime_profile),
    )
    _report_progress(progress, "Building graph state")
    graph_store = GraphStateStore(paths.manifest_path, metadata_service)
    _report_progress(progress, "Preparing background watcher")
    metadata_watcher = MetadataWatcher(graph_store)
    return AppState(
        settings=settings,
        graph_store=graph_store,
        task_repository=task_repository,
        task_runner=DbtTaskRunner(
            task_repository,
            runtime_profile,
            on_finished=metadata_watcher.trigger_refresh,
        ),
        metadata_watcher=metadata_watcher,
        warehouse_adapter=warehouse_adapter,
    )


def _report_progress(progress: StartupProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)
