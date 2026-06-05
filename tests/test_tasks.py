from pathlib import Path
import pytest
from unittest.mock import Mock

from dbt_dag.db.session import create_db_engine
from dbt_dag.db.session import create_session_factory
from dbt_dag.db.session import init_db
from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.dbt_runtime.types import DbtProjectPaths
from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.dbt_runtime.types import DbtTarget
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.tasks.models import NodeAction
from dbt_dag.tasks.models import TaskStatus
from dbt_dag.tasks.repository import NodeTaskRepository
from dbt_dag.tasks.runner import DbtTaskRunner


def test_task_repository_persists_state_transitions(tmp_path: Path) -> None:
    engine = create_db_engine(tmp_path / "tasks.sqlite")
    init_db(engine)
    repository = NodeTaskRepository(create_session_factory(engine))

    task = repository.create("model.demo.stg_orders", "dbt build --select model.demo.stg_orders")
    repository.mark_running(task.task_id)
    repository.mark_finished(task.task_id, exit_code=0, logs_excerpt="done")

    tasks = repository.list_for_node("model.demo.stg_orders")

    assert len(tasks) == 1
    assert tasks[0].status == TaskStatus.SUCCEEDED
    assert tasks[0].exit_code == 0
    assert tasks[0].logs_excerpt == "done"


def test_stream_action_yields_chunks_and_refreshes_metadata(
    dbt_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    profiles_dir: Path,
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    on_finished = Mock()
    runner = DbtTaskRunner(repository, _runtime_profile(dbt_project, profiles_dir), on_finished)
    node = _model_node()

    monkeypatch.setattr(
        "dbt_dag.tasks.runner.subprocess.Popen",
        lambda *args, **kwargs: _FakeProcess(["hello\n", "world\n"], 0),
    )

    events = list(runner.stream_action(node, NodeAction.RUN))
    tasks = repository.list_for_node(node.unique_id)

    assert '"event": "start"' in events[0]
    assert '"event": "chunk"' in events[1]
    assert '"event": "finish"' in events[-1]
    assert tasks[0].status == TaskStatus.SUCCEEDED
    assert tasks[0].logs_excerpt == "hello\nworld"
    on_finished.assert_called_once_with()


def test_compile_action_returns_compiled_sql_without_refresh(
    dbt_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    profiles_dir: Path,
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    on_finished = Mock()
    compiled_path = (
        dbt_project / "target" / "compiled" / "demo" / "models" / "stg" / "stg_orders.sql"
    )
    compiled_path.parent.mkdir(parents=True)
    compiled_path.write_text("select 1", encoding="utf-8")
    node = _model_node(compiled_path="target/compiled/demo/models/stg/stg_orders.sql")
    runner = DbtTaskRunner(repository, _runtime_profile(dbt_project, profiles_dir), on_finished)

    monkeypatch.setattr(
        "dbt_dag.tasks.runner.subprocess.Popen",
        lambda *args, **kwargs: _FakeProcess(["compiled\n"], 0),
    )

    events = list(runner.stream_action(node, NodeAction.COMPILE))

    assert '"compiled_sql": "select 1"' in events[-1]
    on_finished.assert_not_called()


def _repository(tmp_path: Path) -> NodeTaskRepository:
    engine = create_db_engine(tmp_path / "tasks.sqlite")
    init_db(engine)
    return NodeTaskRepository(create_session_factory(engine))


def _runtime_profile(dbt_project: Path, profiles_dir: Path) -> DbtRuntimeProfile:
    return DbtRuntimeProfile(
        profile_name="demo_profile",
        target=DbtTarget(name="dev", target_type="bigquery", raw={}),
        adapter_kind=AdapterKind.BIGQUERY,
        paths=DbtProjectPaths(
            project_dir=dbt_project,
            manifest_path=dbt_project / "target" / "manifest.json",
            profiles_dir=profiles_dir,
        ),
    )


def _model_node(compiled_path: str | None = None) -> DbtManifestNode:
    raw = {}
    if compiled_path is not None:
        raw["compiled_path"] = compiled_path
    return DbtManifestNode(
        unique_id="model.demo.stg_orders",
        name="stg_orders",
        resource_type="model",
        description="Staged orders",
        depends_on=[],
        package_name="demo",
        path="models/stg/stg_orders.sql",
        fqn=["demo", "stg", "stg_orders"],
        raw=raw,
    )


class _FakeProcess:
    def __init__(self, lines: list[str], exit_code: int) -> None:
        self.stdout = iter(lines)
        self._exit_code = exit_code

    def wait(self) -> int:
        return self._exit_code
