from typing import Protocol

from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.dbt_runtime.types import ConnectionCheck
from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.dbt_runtime.types import QueryResult


class WarehouseAdapterProtocol(Protocol):
    adapter_kind: AdapterKind

    def load_runtime_profile(self) -> DbtRuntimeProfile: ...

    def run_query(self, sql: str) -> QueryResult: ...

    def validate_connection(self) -> ConnectionCheck: ...
