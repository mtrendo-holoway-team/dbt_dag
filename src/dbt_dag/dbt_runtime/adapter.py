import logging
from typing import Any, cast

from dbt_dag.adapters.protocols import WarehouseAdapterProtocol
from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.dbt_runtime.types import ConnectionCheck
from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.dbt_runtime.types import QueryResult
from dbt_dag.dbt_runtime.types import WarehouseQueryError

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

    def run_query(self, sql: str) -> QueryResult:
        from google.api_core.exceptions import GoogleAPIError
        from google.auth.exceptions import GoogleAuthError
        from google.cloud import bigquery
        from google.oauth2 import service_account

        try:
            target = self._runtime_profile.target.raw
            project = _target_str(target, "project")
            location = _target_optional_str(target, "location")
            credentials = None
            method = _target_optional_str(target, "method")
            if method == "service-account":
                keyfile = _target_str(target, "keyfile")
                credentials = cast(
                    Any,
                    service_account.Credentials,
                ).from_service_account_file(keyfile)
            elif method == "service-account-json":
                keyfile_json = target.get("keyfile_json")
                if not isinstance(keyfile_json, dict):
                    raise ValueError(
                        "BigQuery service-account-json target must define keyfile_json"
                    )
                credentials = cast(
                    Any,
                    service_account.Credentials,
                ).from_service_account_info(keyfile_json)

            client = bigquery.Client(project=project, credentials=credentials, location=location)
            rows = [dict(row.items()) for row in client.query(sql).result()]
        except (GoogleAPIError, GoogleAuthError, OSError, ValueError) as exc:
            raise WarehouseQueryError(str(exc)) from exc
        columns = list(rows[0].keys()) if rows else []
        return QueryResult(columns=columns, rows=rows)


def create_warehouse_adapter(runtime_profile: DbtRuntimeProfile) -> WarehouseAdapterProtocol:
    if runtime_profile.adapter_kind == AdapterKind.BIGQUERY:
        return BigQueryWarehouseAdapter(runtime_profile)
    return DbtAdapterRuntime(runtime_profile)


def _target_str(target: dict[str, Any], key: str) -> str:
    value = target.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"BigQuery target must define {key}")
    return value


def _target_optional_str(target: dict[str, Any], key: str) -> str | None:
    value = target.get(key)
    return value if isinstance(value, str) and value else None
