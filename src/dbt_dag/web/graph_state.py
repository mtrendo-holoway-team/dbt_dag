from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import threading

from dbt_dag.graph.builder import build_graph
from dbt_dag.graph.models import GraphPayload
from dbt_dag.manifest.models import DbtManifest
from dbt_dag.manifest.parser import load_manifest
from dbt_dag.metadata.models import NodeRuntimeMetadata
from dbt_dag.metadata.service import RuntimeMetadataService
from dbt_dag.shared.time import now_msk
from dbt_dag.tests.models import ModelTestSummaryDTO
from dbt_dag.tests.service import ModelTestService


@dataclass(frozen=True)
class GraphStateSnapshot:
    manifest: DbtManifest
    graph: GraphPayload
    runtime_metadata: dict[str, NodeRuntimeMetadata]
    test_summaries: dict[str, ModelTestSummaryDTO]
    revision: int
    refreshed_at: datetime


class GraphStateStore:
    def __init__(
        self,
        manifest_path: Path,
        metadata_service: RuntimeMetadataService,
        test_service: ModelTestService,
        include_warehouse_on_init: bool = True,
    ) -> None:
        self._manifest_path = manifest_path
        self._metadata_service = metadata_service
        self._test_service = test_service
        self._lock = threading.Lock()
        manifest = load_manifest(manifest_path)
        runtime_metadata = metadata_service.load(
            manifest,
            include_warehouse=include_warehouse_on_init,
        )
        test_summaries = test_service.load(
            manifest,
            include_warehouse=include_warehouse_on_init,
        )
        self._snapshot = GraphStateSnapshot(
            manifest=manifest,
            graph=build_graph(manifest, runtime_metadata, test_summaries),
            runtime_metadata=runtime_metadata,
            test_summaries=test_summaries,
            revision=1,
            refreshed_at=now_msk(),
        )
        self._manifest_fingerprint = self.manifest_fingerprint()

    def snapshot(self) -> GraphStateSnapshot:
        with self._lock:
            return self._snapshot

    def manifest_fingerprint(self) -> str:
        try:
            stat = self._manifest_path.stat()
        except OSError:
            return "missing"
        return f"{stat.st_mtime_ns}:{stat.st_size}"

    def artifact_fingerprint(self) -> str:
        return self._metadata_service.artifact_fingerprint()

    def refresh(self, include_warehouse: bool = True) -> bool:
        manifest = load_manifest(self._manifest_path)
        runtime_metadata = self._metadata_service.load(
            manifest,
            include_warehouse=include_warehouse,
        )
        test_summaries = self._test_service.load(
            manifest,
            include_warehouse=include_warehouse,
        )
        graph = build_graph(manifest, runtime_metadata, test_summaries)
        with self._lock:
            changed = (
                manifest != self._snapshot.manifest
                or runtime_metadata != self._snapshot.runtime_metadata
                or test_summaries != self._snapshot.test_summaries
            )
            if not changed:
                return False
            self._snapshot = GraphStateSnapshot(
                manifest=manifest,
                graph=graph,
                runtime_metadata=runtime_metadata,
                test_summaries=test_summaries,
                revision=self._snapshot.revision + 1,
                refreshed_at=now_msk(),
            )
            self._manifest_fingerprint = self.manifest_fingerprint()
            return True
