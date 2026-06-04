import logging
import threading

from dbt_dag.partitions.repository import ModelPartitionRepository
from dbt_dag.partitions.warehouse import BigQueryPartitionWarehouseReader

logger = logging.getLogger(__name__)


class ModelPartitionSyncRunner:
    def __init__(
        self,
        repository: ModelPartitionRepository,
        warehouse_reader: BigQueryPartitionWarehouseReader,
    ) -> None:
        self._repository = repository
        self._warehouse_reader = warehouse_reader
        self._active_models: set[str] = set()
        self._lock = threading.Lock()

    def start_refresh(self, model_unique_id: str) -> bool:
        with self._lock:
            if model_unique_id in self._active_models:
                return False
            self._active_models.add(model_unique_id)
            self._repository.mark_running(model_unique_id)
        thread = threading.Thread(
            target=self._run_refresh,
            name=f"partition-sync-{model_unique_id}",
            args=(model_unique_id,),
            daemon=True,
        )
        thread.start()
        return True

    def is_refreshing(self, model_unique_id: str) -> bool:
        with self._lock:
            return model_unique_id in self._active_models

    def _run_refresh(self, model_unique_id: str) -> None:
        try:
            snapshot = self._warehouse_reader.fetch_latest_partition_snapshot(model_unique_id)
            self._repository.replace_snapshot(model_unique_id, snapshot)
        except (OSError, RuntimeError, ValueError) as exc:
            logger.exception(
                "model partition refresh failed",
                extra={"model_unique_id": model_unique_id},
            )
            self._repository.mark_failed(model_unique_id, str(exc))
        finally:
            with self._lock:
                self._active_models.discard(model_unique_id)
