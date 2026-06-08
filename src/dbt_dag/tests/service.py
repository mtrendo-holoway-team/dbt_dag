from datetime import timedelta
import threading

from dbt_dag.manifest.models import DbtManifest
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.shared.time import now_msk
from dbt_dag.tests.artifacts import RunResultsTestReader
from dbt_dag.tests.models import LatestTestRunDTO
from dbt_dag.tests.models import ModelTestResultDTO
from dbt_dag.tests.models import ModelTestStatus
from dbt_dag.tests.models import ModelTestSummaryDTO
from dbt_dag.tests.warehouse import WarehouseTestRunsReader

_STALE_THRESHOLD = timedelta(hours=24)


class ModelTestService:
    def __init__(
        self,
        artifact_reader: RunResultsTestReader,
        warehouse_reader: WarehouseTestRunsReader,
    ) -> None:
        self._artifact_reader = artifact_reader
        self._warehouse_reader = warehouse_reader
        self._lock = threading.Lock()
        self._warehouse_cache: dict[str, LatestTestRunDTO] = {}

    def load(
        self,
        manifest: DbtManifest,
        include_warehouse: bool = True,
    ) -> dict[str, ModelTestSummaryDTO]:
        latest_runs = self._artifact_reader.read_latest_runs()
        latest_runs.update(self._load_warehouse_runs(include_warehouse))
        test_nodes_by_model = _manifest_test_nodes_by_model(manifest)
        test_names_by_id = _manifest_test_names_by_id(manifest)
        graph_node_ids = set(manifest.graph_nodes())
        return {
            model_unique_id: _build_summary(
                model_unique_id,
                test_node_ids,
                latest_runs,
                test_names_by_id,
            )
            for model_unique_id, test_node_ids in test_nodes_by_model.items()
            if model_unique_id in graph_node_ids
        }

    def _load_warehouse_runs(self, include_warehouse: bool) -> dict[str, LatestTestRunDTO]:
        with self._lock:
            if include_warehouse:
                self._warehouse_cache = self._warehouse_reader.read_latest_runs()
            return dict(self._warehouse_cache)


def _manifest_test_nodes_by_model(manifest: DbtManifest) -> dict[str, list[str]]:
    tests_by_model = _empty_manifest_test_nodes_by_model(manifest)
    for test_node in _manifest_test_nodes(manifest):
        _attach_test_node_to_models(test_node.unique_id, test_node.depends_on, tests_by_model)
    return {
        model_unique_id: sorted(test_ids) for model_unique_id, test_ids in tests_by_model.items()
    }


def _empty_manifest_test_nodes_by_model(manifest: DbtManifest) -> dict[str, list[str]]:
    return {
        node_id: [] for node_id, node in manifest.nodes.items() if node.resource_type == "model"
    }


def _manifest_test_nodes(manifest: DbtManifest) -> list[DbtManifestNode]:
    return [node for node in manifest.nodes.values() if node.resource_type == "test"]


def _attach_test_node_to_models(
    test_unique_id: str,
    dependencies: list[str],
    tests_by_model: dict[str, list[str]],
) -> None:
    for dependency in dependencies:
        if dependency in tests_by_model:
            tests_by_model[dependency].append(test_unique_id)


def _build_summary(
    model_unique_id: str,
    test_node_ids: list[str],
    latest_runs: dict[str, LatestTestRunDTO],
    test_names_by_id: dict[str, str],
) -> ModelTestSummaryDTO:
    if not test_node_ids:
        return ModelTestSummaryDTO(
            model_unique_id=model_unique_id,
            status=ModelTestStatus.MISSING,
            tests=[],
        )
    tests = [
        _build_test_result(
            test_node_id,
            latest_runs.get(test_node_id),
            test_names_by_id.get(test_node_id, test_node_id),
        )
        for test_node_id in test_node_ids
    ]
    return ModelTestSummaryDTO(
        model_unique_id=model_unique_id,
        status=_summary_status(tests),
        tests=tests,
    )


def _build_test_result(
    test_unique_id: str,
    latest_run: LatestTestRunDTO | None,
    test_name: str,
) -> ModelTestResultDTO:
    return ModelTestResultDTO(
        test_unique_id=test_unique_id,
        test_name=test_name,
        status=_test_status(latest_run),
        executed_at=latest_run.executed_at if latest_run is not None else None,
    )


def _manifest_test_names_by_id(manifest: DbtManifest) -> dict[str, str]:
    return {node.unique_id: node.name for node in _manifest_test_nodes(manifest) if node.name}


def _test_status(latest_run: LatestTestRunDTO | None) -> ModelTestStatus:
    if latest_run is None:
        return ModelTestStatus.STALE
    if latest_run.status.lower() not in {"pass", "passed", "success", "ok"}:
        return ModelTestStatus.FAILED
    age = now_msk() - latest_run.executed_at
    if age > _STALE_THRESHOLD:
        return ModelTestStatus.STALE
    return ModelTestStatus.PASSED


def _summary_status(tests: list[ModelTestResultDTO]) -> ModelTestStatus:
    if any(test.status == ModelTestStatus.FAILED for test in tests):
        return ModelTestStatus.FAILED
    if any(test.status == ModelTestStatus.STALE for test in tests):
        return ModelTestStatus.STALE
    return ModelTestStatus.PASSED
