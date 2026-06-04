from datetime import datetime
import json
from pathlib import Path
import pytest
import threading
from typing import cast

from dbt_dag.manifest.models import DbtManifest
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.manifest.parser import load_manifest
from dbt_dag.metadata import service
from dbt_dag.metadata.artifacts import RunResultsArtifactReader
from dbt_dag.metadata.models import PartialRuntimeMetadata
from dbt_dag.metadata.models import RuntimeDataSource
from dbt_dag.metadata.models import RuntimeFreshness
from dbt_dag.metadata.service import RuntimeMetadataService
from dbt_dag.metadata.warehouse import _relations_by_node
from dbt_dag.metadata.warehouse import WarehouseMetadataReader
from dbt_dag.metadata.watcher import MetadataWatcher
from dbt_dag.shared.time import MSK
from dbt_dag.web.graph_state import GraphStateStore


def test_run_results_reader_parses_execution_time_and_execute_completion(
    dbt_project: Path,
) -> None:
    _write_run_results(dbt_project, execution_time=12.5, completed_at="2026-06-03T08:10:00Z")

    metadata = RunResultsArtifactReader(dbt_project).read()

    assert metadata["model.demo.stg_orders"].execution_time_seconds == 12.5
    assert metadata["model.demo.stg_orders"].execution_time_source == RuntimeDataSource.RUN_RESULTS
    assert metadata["model.demo.stg_orders"].last_updated_at == datetime(
        2026,
        6,
        3,
        11,
        10,
        tzinfo=MSK,
    )


def test_run_results_reader_handles_missing_artifact(tmp_path: Path) -> None:
    assert RunResultsArtifactReader(tmp_path).read() == {}


def test_runtime_service_prefers_warehouse_over_artifact(
    dbt_project: Path,
) -> None:
    manifest = load_manifest(dbt_project / "target" / "manifest.json")
    artifact_reader = _FakeArtifactReader(
        {
            "model.demo.stg_orders": PartialRuntimeMetadata(
                execution_time_seconds=10,
                execution_time_source=RuntimeDataSource.RUN_RESULTS,
                last_updated_at=datetime(2026, 6, 1, 12, tzinfo=MSK),
                last_updated_source=RuntimeDataSource.RUN_RESULTS,
            )
        }
    )
    warehouse_reader = _FakeWarehouseReader(
        {
            "model.demo.stg_orders": PartialRuntimeMetadata(
                execution_time_seconds=20,
                execution_time_source=RuntimeDataSource.WAREHOUSE,
                last_updated_at=datetime(2026, 6, 3, 11, tzinfo=MSK),
                last_updated_source=RuntimeDataSource.WAREHOUSE,
            )
        }
    )

    metadata = RuntimeMetadataService(
        cast(RunResultsArtifactReader, artifact_reader),
        cast(WarehouseMetadataReader, warehouse_reader),
    ).load(manifest)

    assert metadata["model.demo.stg_orders"].execution_time_seconds == 20
    assert metadata["model.demo.stg_orders"].execution_time_source == RuntimeDataSource.WAREHOUSE
    assert metadata["model.demo.stg_orders"].last_updated_source == RuntimeDataSource.WAREHOUSE


def test_runtime_service_decorates_freshness_and_logarithmic_width(
    dbt_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = load_manifest(dbt_project / "target" / "manifest.json")
    monkeypatch.setattr(
        service,
        "now_msk",
        lambda: datetime(2026, 6, 3, 12, tzinfo=MSK),
    )
    artifact_reader = _FakeArtifactReader(
        {
            "model.demo.stg_orders": PartialRuntimeMetadata(
                execution_time_seconds=10,
                execution_time_source=RuntimeDataSource.RUN_RESULTS,
                last_updated_at=datetime(2026, 6, 3, 11, tzinfo=MSK),
                last_updated_source=RuntimeDataSource.RUN_RESULTS,
            ),
            "model.demo.fct_orders": PartialRuntimeMetadata(
                execution_time_seconds=100,
                execution_time_source=RuntimeDataSource.RUN_RESULTS,
                last_updated_at=datetime(2026, 6, 2, 13, tzinfo=MSK),
                last_updated_source=RuntimeDataSource.RUN_RESULTS,
            ),
        }
    )
    warehouse_reader = _FakeWarehouseReader({})

    metadata = RuntimeMetadataService(
        cast(RunResultsArtifactReader, artifact_reader),
        cast(WarehouseMetadataReader, warehouse_reader),
    ).load(manifest)

    assert metadata["model.demo.stg_orders"].freshness == RuntimeFreshness.LAST_2H
    assert metadata["model.demo.fct_orders"].freshness == RuntimeFreshness.LAST_24H
    assert metadata["model.demo.fct_orders"].border_width_px == 6
    assert 1 < metadata["model.demo.stg_orders"].border_width_px < 6
    assert metadata["source.demo.raw.orders"].border_width_px == 1
    assert metadata["source.demo.raw.orders"].freshness == RuntimeFreshness.UNKNOWN


def test_graph_state_store_skips_warehouse_load_on_init_when_disabled(
    dbt_project: Path,
) -> None:
    manifest_path = dbt_project / "target" / "manifest.json"
    metadata_service = _MetadataServiceSpy()

    GraphStateStore(
        manifest_path,
        cast(RuntimeMetadataService, metadata_service),
        include_warehouse_on_init=False,
    )

    assert metadata_service.calls == [False]


def test_warehouse_relations_include_only_current_project_nodes() -> None:
    manifest = DbtManifest(
        project_name="demo",
        nodes={
            "model.demo.orders": _manifest_node(
                unique_id="model.demo.orders",
                resource_type="model",
                package_name="demo",
                database="demo_project",
                schema="analytics",
                identifier="orders",
            ),
            "model.package.other_orders": _manifest_node(
                unique_id="model.package.other_orders",
                resource_type="model",
                package_name="package",
                database="foreign_project",
                schema="system",
                identifier="other_orders",
            ),
        },
        sources={
            "source.package.system.tables": _manifest_node(
                unique_id="source.package.system.tables",
                resource_type="source",
                package_name="package",
                database="foreign_project",
                schema="system",
                identifier="tables",
            )
        },
        exposures={},
    )

    relations = _relations_by_node(manifest)

    assert relations == {
        "model.demo.orders": ("demo_project", "analytics", "orders"),
    }


def test_metadata_watcher_stop_does_not_block_on_running_thread(
    dbt_project: Path,
) -> None:
    graph_store = GraphStateStore(
        dbt_project / "target" / "manifest.json",
        _empty_metadata_service(),
    )
    watcher = MetadataWatcher(graph_store, stop_join_timeout_seconds=0)
    blocker = threading.Event()
    watcher._thread = threading.Thread(target=blocker.wait, daemon=True)
    watcher._thread.start()

    watcher.stop()

    assert watcher._thread.is_alive()
    blocker.set()


class _FakeArtifactReader:
    def __init__(self, metadata: dict[str, PartialRuntimeMetadata]) -> None:
        self._metadata = metadata

    def read(self) -> dict[str, PartialRuntimeMetadata]:
        return self._metadata

    def fingerprint(self) -> str:
        return "fake"


class _FakeWarehouseReader:
    def __init__(self, metadata: dict[str, PartialRuntimeMetadata]) -> None:
        self._metadata = metadata

    def read(self, manifest: DbtManifest) -> dict[str, PartialRuntimeMetadata]:
        return self._metadata


class _MetadataServiceSpy:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    def load(
        self,
        manifest: DbtManifest,
        include_warehouse: bool = True,
    ) -> dict[str, PartialRuntimeMetadata]:
        self.calls.append(include_warehouse)
        return {}

    def artifact_fingerprint(self) -> str:
        return "fake"


def _empty_metadata_service() -> RuntimeMetadataService:
    artifact_reader = _FakeArtifactReader({})
    warehouse_reader = _FakeWarehouseReader({})
    return RuntimeMetadataService(
        cast(RunResultsArtifactReader, artifact_reader),
        cast(WarehouseMetadataReader, warehouse_reader),
    )


def _write_run_results(
    dbt_project: Path,
    execution_time: float,
    completed_at: str,
) -> None:
    run_results = {
        "metadata": {"generated_at": "2026-06-03T08:20:00Z"},
        "results": [
            {
                "unique_id": "model.demo.stg_orders",
                "execution_time": execution_time,
                "timing": [
                    {
                        "name": "execute",
                        "started_at": "2026-06-03T08:00:00Z",
                        "completed_at": completed_at,
                    }
                ],
            }
        ],
    }
    (dbt_project / "target" / "run_results.json").write_text(
        json.dumps(run_results),
        encoding="utf-8",
    )


def _manifest_node(
    unique_id: str,
    resource_type: str,
    package_name: str,
    database: str,
    schema: str,
    identifier: str,
) -> DbtManifestNode:
    return DbtManifestNode(
        unique_id=unique_id,
        name=identifier,
        resource_type=resource_type,
        description="",
        depends_on=[],
        package_name=package_name,
        path="",
        fqn=[],
        raw={
            "database": database,
            "schema": schema,
            "identifier": identifier,
        },
    )
