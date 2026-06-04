import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from dbt_dag.app import StartupProgressReporter
from dbt_dag.settings import Settings
from dbt_dag.web.state import AppState
from dbt_dag.web.state import build_app_state


def test_startup_progress_reporter_logs_progress(caplog: LogCaptureFixture) -> None:
    reporter = StartupProgressReporter(total_steps=3)

    with caplog.at_level(logging.INFO):
        reporter.advance("Loading settings")
        reporter.advance("Building graph")
        reporter.finish()

    assert "startup [#######-------------] 1/3 Loading settings" in caplog.text
    assert "startup [#############-------] 2/3 Building graph" in caplog.text
    assert "startup [####################] ready in" in caplog.text


def test_build_app_state_reports_startup_steps(
    dbt_project: Path,
    profiles_dir: Path,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    settings = Settings(
        app_host="127.0.0.1",
        app_port=5678,
        sqlite_path=tmp_path / "app.sqlite",
        dbt_project_dir=dbt_project,
        dbt_profiles_dir=profiles_dir,
        dbt_target=None,
    )
    steps: list[str] = []
    runtime_profile = Mock()
    runtime_profile.paths.project_dir = dbt_project
    runtime_profile.paths.profiles_dir = profiles_dir
    runtime_profile.target.name = "dev"
    paths = SimpleNamespace(
        project_dir=dbt_project,
        manifest_path=dbt_project / "target" / "manifest.json",
        profiles_dir=profiles_dir,
    )
    adapter = Mock()
    task_repository = Mock()
    graph_store = Mock()
    watcher = Mock()
    task_runner = Mock()

    monkeypatch.setattr("dbt_dag.web.state.resolve_project_paths", Mock(return_value=paths))
    monkeypatch.setattr(
        "dbt_dag.web.state.resolve_runtime_profile", Mock(return_value=runtime_profile)
    )
    monkeypatch.setattr("dbt_dag.web.state.create_warehouse_adapter", Mock(return_value=adapter))
    monkeypatch.setattr("dbt_dag.web.state.create_db_engine", Mock(return_value=Mock()))
    monkeypatch.setattr("dbt_dag.web.state.init_db", Mock())
    monkeypatch.setattr("dbt_dag.web.state.create_session_factory", Mock(return_value=Mock()))
    monkeypatch.setattr("dbt_dag.web.state.NodeTaskRepository", Mock(return_value=task_repository))
    monkeypatch.setattr("dbt_dag.web.state.GraphStateStore", Mock(return_value=graph_store))
    monkeypatch.setattr("dbt_dag.web.state.MetadataWatcher", Mock(return_value=watcher))
    monkeypatch.setattr("dbt_dag.web.state.DbtTaskRunner", Mock(return_value=task_runner))

    state = build_app_state(settings, progress=steps.append)

    assert isinstance(state, AppState)
    assert steps == [
        "Resolving dbt project paths",
        "Resolving active dbt profile",
        "Preparing warehouse adapter",
        "Validating warehouse adapter",
        "Initializing local database",
        "Preparing runtime metadata services",
        "Building graph state",
        "Preparing background watcher",
    ]
