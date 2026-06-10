from datetime import date
from pathlib import Path
import pytest
from typing import cast
from unittest.mock import Mock

from litestar import Litestar
from litestar.datastructures import State
from litestar.testing import TestClient

from dbt_dag.db.session import create_db_engine
from dbt_dag.db.session import create_session_factory
from dbt_dag.db.session import init_db
from dbt_dag.metadata.artifacts import RunResultsArtifactReader
from dbt_dag.metadata.service import RuntimeMetadataService
from dbt_dag.metadata.warehouse import WarehouseMetadataReader
from dbt_dag.metadata.watcher import MetadataWatcher
from dbt_dag.partitions.models import ModelPartitionCalendarDTO
from dbt_dag.partitions.models import PartitionMonthDTO
from dbt_dag.partitions.models import PartitionSyncStatus
from dbt_dag.settings import Settings
from dbt_dag.tasks.repository import NodeTaskRepository
from dbt_dag.tests.service import ModelTestService
from dbt_dag.web.controllers import pages
from dbt_dag.web.controllers.pages import PagesController
from dbt_dag.web.graph_state import GraphStateStore
from dbt_dag.web.state import AppState
from dbt_dag.web.template_config import create_template_config


def test_graph_endpoint_returns_documented_shape(dbt_project: Path, tmp_path: Path) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/api/graph")

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["models_count"] == 2
    assert body["project"]["sources_count"] == 1
    assert body["project"]["tests_count"] == 1
    assert len(body["nodes"]) == 3
    assert {node["package_name"] for node in body["nodes"]} == {"demo"}
    assert {node["id"]: node["type_badge"] for node in body["nodes"]} == {
        "source.demo.raw.orders": "S",
        "model.demo.stg_orders": "V",
        "model.demo.fct_orders": "T",
    }
    assert body["nodes"][0]["runtime"]["border_width_px"] == 1
    assert body["nodes"][0]["test_indicator"]["status"] == "missing"


def test_node_inspector_returns_shell_with_tokenized_blocks(
    dbt_project: Path,
    tmp_path: Path,
) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/inspector/node/model.demo.stg_orders?selection_token=token123")

    assert response.status_code == 200
    assert "stg_orders" in response.text
    assert "Staged orders" in response.text
    assert 'id="inspector-block-last-update-token123"' in response.text
    assert 'id="inspector-block-tests-token123"' in response.text
    assert (
        "/inspector/node/model.demo.stg_orders/last-update?selection_token=token123"
        in response.text
    )
    assert "/inspector/node/model.demo.stg_orders/tests?selection_token=token123" in response.text


def test_project_inspector_returns_when_no_selection(dbt_project: Path, tmp_path: Path) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/inspector/project")

    assert response.status_code == 200
    assert "Моделей" in response.text


def test_last_update_block_returns_runtime_panel(dbt_project: Path, tmp_path: Path) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/inspector/node/model.demo.stg_orders/last-update?selection_token=abc")

    assert response.status_code == 200
    assert "Обновлено" in response.text
    assert "Время расчета" in response.text


def test_metadata_revision_endpoint_returns_revision(dbt_project: Path, tmp_path: Path) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/api/metadata/revision")

    assert response.status_code == 200
    assert response.json()["revision"] == 1


def test_search_endpoint_returns_highlight_positions_for_exact_name_match(
    dbt_project: Path, tmp_path: Path
) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/search?q=stg")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == "model.demo.stg_orders"
    assert body[0]["label"] == "stg_orders"
    assert body[0]["label_matches"] == [0, 1, 2]
    assert body[0]["type_matches"] == []


def test_search_endpoint_supports_fuzzy_resource_type_matches(
    dbt_project: Path, tmp_path: Path
) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/search?q=src")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == "source.demo.raw.orders"
    assert body[0]["type"] == "source"
    assert body[0]["type_matches"] == [0, 3, 4]


def test_tests_block_returns_model_test_list(dbt_project: Path, tmp_path: Path) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/inspector/node/model.demo.fct_orders/tests?selection_token=abc")

    assert response.status_code == 200
    assert "Тесты" in response.text
    assert "not_null_orders_id" in response.text


def test_tests_block_renders_missing_state_for_model_without_tests(
    dbt_project: Path,
    tmp_path: Path,
) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/inspector/node/model.demo.stg_orders/tests?selection_token=abc")

    assert response.status_code == 200
    assert "нет тестов" in response.text
    assert "status-dot-missing" in response.text


def test_model_action_endpoint_streams_ndjson(dbt_project: Path, tmp_path: Path) -> None:
    task_runner = Mock()
    task_runner.supports_action.return_value = True
    task_runner.stream_action.return_value = iter(
        [
            '{"event":"start","command":"dbt run --select stg_orders"}\n',
            '{"event":"finish","ok":true,"exit_code":0}\n',
        ]
    )
    client = _client(dbt_project, tmp_path, task_runner=task_runner)

    response = client.post("/actions/node/model.demo.stg_orders/execute/run")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert '"event":"start"' in response.text
    task_runner.stream_action.assert_called_once()


def test_model_action_endpoint_rejects_non_model_nodes(dbt_project: Path, tmp_path: Path) -> None:
    task_runner = Mock()
    client = _client(dbt_project, tmp_path, task_runner=task_runner)

    response = client.post("/actions/node/source.demo.raw.orders/execute/build")

    assert response.status_code == 404
    task_runner.stream_action.assert_not_called()


def test_model_action_endpoint_returns_400_for_unknown_action(
    dbt_project: Path,
    tmp_path: Path,
) -> None:
    task_runner = Mock()
    client = _client(dbt_project, tmp_path, task_runner=task_runner)

    response = client.post("/actions/node/model.demo.stg_orders/execute/unknown")

    assert response.status_code == 400
    task_runner.stream_action.assert_not_called()


def test_partition_partial_endpoint_returns_calendar(dbt_project: Path, tmp_path: Path) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get(
        "/inspector/node/model.demo.stg_orders/partition?selection_token=token123"
    )

    assert response.status_code == 200
    assert "Данные" in response.text
    assert "Обновить" in response.text
    assert 'id="inspector-block-partition-token123"' in response.text


def test_refresh_partition_action_starts_background_sync(
    dbt_project: Path,
    tmp_path: Path,
) -> None:
    partition_runner = Mock()
    client = _client(dbt_project, tmp_path, partition_runner=partition_runner)

    response = client.post(
        "/actions/node/model.demo.stg_orders/refresh-partitions?selection_token=token123"
    )

    assert response.status_code == 200
    assert partition_runner.start_refresh.call_args.args[0].unique_id == "model.demo.stg_orders"
    assert 'id="inspector-block-partition-token123"' in response.text


def test_tasks_block_polls_with_selection_token(dbt_project: Path, tmp_path: Path) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/inspector/node/model.demo.stg_orders/tasks?selection_token=token123")

    assert response.status_code == 200
    assert 'id="inspector-block-tasks-token123"' in response.text
    assert "/inspector/node/model.demo.stg_orders/tasks?selection_token=token123" in response.text


def test_node_shell_header_does_not_load_partition_or_tasks(
    dbt_project: Path,
    tmp_path: Path,
) -> None:
    partition_service = Mock()
    partition_service.supports_partitions.return_value = True
    partition_service.build_calendar.side_effect = AssertionError(
        "description block should not build partition calendar"
    )
    task_repository = Mock()
    task_repository.list_for_node.side_effect = AssertionError(
        "description block should not load tasks"
    )
    client = _client(
        dbt_project,
        tmp_path,
        partition_service=partition_service,
        task_repository=task_repository,
    )

    response = client.get("/inspector/node/model.demo.stg_orders?selection_token=abc")

    assert response.status_code == 200
    assert "Staged orders" in response.text


def test_static_file_serves_built_assets(
    dbt_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    static_root = tmp_path / "static"
    asset_path = static_root / "dist" / "assets" / "graph.js"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_text("function graph() {}", encoding="utf-8")
    monkeypatch.setattr(pages, "STATIC_ROOT", static_root)
    client = _client(dbt_project, tmp_path)

    response = client.get("/static/dist/assets/graph.js")

    assert response.status_code == 200
    assert "function" in response.text


def _client(
    dbt_project: Path,
    tmp_path: Path,
    partition_runner: Mock | None = None,
    partition_service: Mock | None = None,
    task_repository: Mock | None = None,
    task_runner: Mock | None = None,
) -> TestClient[Litestar]:
    engine = create_db_engine(tmp_path / "app.sqlite")
    init_db(engine)
    repository = task_repository or NodeTaskRepository(create_session_factory(engine))
    task_runner = task_runner or Mock()
    graph_store = GraphStateStore(
        dbt_project / "target" / "manifest.json",
        _empty_metadata_service(),
        _empty_test_service(),
    )
    metadata_watcher = MetadataWatcher(graph_store)
    partition_runner = partition_runner or Mock()
    partition_service = partition_service or _partition_service()
    state = AppState(
        settings=Settings(
            app_host="127.0.0.1",
            app_port=5678,
            sqlite_path=tmp_path / "app.sqlite",
            dbt_project_dir=dbt_project,
            dbt_profiles_dir=None,
            dbt_target=None,
        ),
        graph_store=graph_store,
        task_repository=repository,
        task_runner=task_runner,
        metadata_watcher=metadata_watcher,
        warehouse_adapter=Mock(),
        partition_repository=Mock(),
        partition_service=partition_service,
        partition_runner=partition_runner,
        test_service=_empty_test_service(),
    )
    return TestClient(
        Litestar(
            route_handlers=[PagesController],
            state=State({"app_state": state}),
            template_config=create_template_config(),
        )
    )


def _empty_metadata_service() -> RuntimeMetadataService:
    artifact_reader = Mock()
    artifact_reader.read.return_value = {}
    artifact_reader.fingerprint.return_value = "empty"
    warehouse_reader = Mock()
    warehouse_reader.read.return_value = {}
    return RuntimeMetadataService(
        cast(RunResultsArtifactReader, artifact_reader),
        cast(WarehouseMetadataReader, warehouse_reader),
    )


def _partition_service() -> Mock:
    service = Mock()
    service.supports_partitions.return_value = True
    service.build_calendar.return_value = ModelPartitionCalendarDTO(
        model_unique_id="model.demo.stg_orders",
        range_start=None,
        range_end=date(2026, 6, 4),
        median_row_count=None,
        months=[PartitionMonthDTO(year=2026, month_label="Июнь", leading_empty_days=0, days=[])],
        is_stale=False,
        is_refreshing=False,
        last_synced_at=None,
        sync_status=PartitionSyncStatus.IDLE,
        last_error="",
    )
    return service


def _empty_test_service() -> ModelTestService:
    artifact_reader = Mock()
    artifact_reader.read_latest_runs.return_value = {}
    warehouse_reader = Mock()
    warehouse_reader.read_latest_runs.return_value = {}
    return ModelTestService(artifact_reader, warehouse_reader)
