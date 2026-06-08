from datetime import timedelta
import math
import threading

from dbt_dag.manifest.models import DbtManifest
from dbt_dag.metadata.artifacts import RunResultsArtifactReader
from dbt_dag.metadata.models import empty_node_runtime_metadata
from dbt_dag.metadata.models import empty_partial_metadata
from dbt_dag.metadata.models import MODEL_BORDER_COLOR
from dbt_dag.metadata.models import NodeRuntimeMetadata
from dbt_dag.metadata.models import PartialRuntimeMetadata
from dbt_dag.metadata.models import RuntimeDataSource
from dbt_dag.metadata.models import RuntimeFreshness
from dbt_dag.metadata.warehouse import WarehouseMetadataReader
from dbt_dag.shared.time import now_msk


class RuntimeMetadataService:
    def __init__(
        self,
        artifact_reader: RunResultsArtifactReader,
        warehouse_reader: WarehouseMetadataReader,
    ) -> None:
        self._artifact_reader = artifact_reader
        self._warehouse_reader = warehouse_reader
        self._lock = threading.Lock()
        self._warehouse_cache: dict[str, PartialRuntimeMetadata] = {}

    def load(
        self,
        manifest: DbtManifest,
        include_warehouse: bool = True,
    ) -> dict[str, NodeRuntimeMetadata]:
        artifact_metadata = self._artifact_reader.read()
        warehouse_metadata = self._load_warehouse_metadata(manifest, include_warehouse)
        merged = {
            node_id: _merge_metadata(
                artifact_metadata.get(node_id, empty_partial_metadata()),
                warehouse_metadata.get(node_id, empty_partial_metadata()),
            )
            for node_id in manifest.graph_nodes()
        }
        return _decorate_metadata(merged)

    def artifact_fingerprint(self) -> str:
        return self._artifact_reader.fingerprint()

    def _load_warehouse_metadata(
        self,
        manifest: DbtManifest,
        include_warehouse: bool,
    ) -> dict[str, PartialRuntimeMetadata]:
        with self._lock:
            if include_warehouse:
                self._warehouse_cache = self._warehouse_reader.read(manifest)
            return dict(self._warehouse_cache)


def _merge_metadata(
    artifact: PartialRuntimeMetadata,
    warehouse: PartialRuntimeMetadata,
) -> PartialRuntimeMetadata:
    execution_time = warehouse.execution_time_seconds
    execution_source = warehouse.execution_time_source
    if execution_time is None:
        execution_time = artifact.execution_time_seconds
        execution_source = artifact.execution_time_source

    last_updated_at = warehouse.last_updated_at
    last_updated_source = warehouse.last_updated_source
    if last_updated_at is None:
        last_updated_at = artifact.last_updated_at
        last_updated_source = artifact.last_updated_source

    return PartialRuntimeMetadata(
        execution_time_seconds=execution_time,
        execution_time_source=execution_source,
        last_updated_at=last_updated_at,
        last_updated_source=last_updated_source,
    )


def _decorate_metadata(
    partial_by_node: dict[str, PartialRuntimeMetadata],
) -> dict[str, NodeRuntimeMetadata]:
    max_duration = max(
        (
            metadata.execution_time_seconds
            for metadata in partial_by_node.values()
            if metadata.execution_time_seconds is not None and metadata.execution_time_seconds > 0
        ),
        default=0,
    )
    return {
        node_id: _decorate_single_metadata(metadata, max_duration)
        for node_id, metadata in partial_by_node.items()
    }


def _decorate_single_metadata(
    metadata: PartialRuntimeMetadata,
    max_duration: float,
) -> NodeRuntimeMetadata:
    empty = empty_node_runtime_metadata()
    freshness = _freshness(metadata)
    return (
        NodeRuntimeMetadata(
            execution_time_seconds=metadata.execution_time_seconds,
            execution_time_source=metadata.execution_time_source,
            last_updated_at=metadata.last_updated_at,
            last_updated_source=metadata.last_updated_source,
            freshness=freshness,
            border_width_px=_border_width(metadata.execution_time_seconds, max_duration),
            border_color=MODEL_BORDER_COLOR,
        )
        if metadata != empty_partial_metadata()
        else empty
    )


def _freshness(metadata: PartialRuntimeMetadata) -> RuntimeFreshness:
    if metadata.last_updated_at is None or metadata.last_updated_source == RuntimeDataSource.NONE:
        return RuntimeFreshness.UNKNOWN
    age = now_msk() - metadata.last_updated_at
    if age <= timedelta(hours=2):
        return RuntimeFreshness.LAST_2H
    if age <= timedelta(hours=24):
        return RuntimeFreshness.LAST_24H
    if age <= timedelta(hours=48):
        return RuntimeFreshness.LAST_48H
    return RuntimeFreshness.STALE


def _border_width(duration: float | None, max_duration: float) -> float:
    if duration is None or duration <= 0 or max_duration <= 0:
        return 1
    width = 1 + 5 * math.log1p(duration) / math.log1p(max_duration)
    return min(max(width, 1), 6)
