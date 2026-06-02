import logging

from dbt_dag.adapters.protocols import WarehouseAdapterProtocol
from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.dbt_runtime.types import ConnectionCheck
from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.dbt_runtime.types import QueryResult

logger = logging.getLogger(__name__)


class DbtAdapterRuntime(WarehouseAdapterProtocol):
    def __init__(self, runtime_profile: DbtRuntimeProfile) -> None:
        self._runtime_profile = runtime_profile
        self.adapter_kind = runtime_profile.adapter_kind

    def load_runtime_profile(self) -> DbtRuntimeProfile:
        return self._runtime_profile

    def validate_connection(self) -> ConnectionCheck:
        try:
            # Keep dbt internals isolated in this module. The concrete adapter lifecycle
            # will be expanded when test-run ingestion needs live warehouse queries.
            from dbt.adapters.factory import get_adapter_class_by_name
            from dbt.adapters.factory import load_plugin

            load_plugin(self._runtime_profile.target.target_type)
            get_adapter_class_by_name(self._runtime_profile.target.target_type)
        except (ImportError, RuntimeError, ValueError) as exc:
            logger.exception("dbt adapter validation failed")
            return ConnectionCheck(ok=False, message=str(exc))
        return ConnectionCheck(ok=True, message="dbt adapter is importable")

    def run_query(self, sql: str) -> QueryResult:
        raise NotImplementedError(
            "Warehouse queries are not implemented in the baseline visualizer"
        )


class BigQueryWarehouseAdapter(DbtAdapterRuntime):
    def __init__(self, runtime_profile: DbtRuntimeProfile) -> None:
        super().__init__(runtime_profile)
        self.adapter_kind = AdapterKind.BIGQUERY


def create_warehouse_adapter(runtime_profile: DbtRuntimeProfile) -> WarehouseAdapterProtocol:
    if runtime_profile.adapter_kind == AdapterKind.BIGQUERY:
        return BigQueryWarehouseAdapter(runtime_profile)
    return DbtAdapterRuntime(runtime_profile)
