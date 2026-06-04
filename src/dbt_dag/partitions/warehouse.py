from datetime import date
from datetime import datetime
import logging
from typing import Any

from dbt_dag.adapters.protocols import WarehouseAdapterProtocol
from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.dbt_runtime.types import WarehouseQueryError
from dbt_dag.partitions.models import PartitionSnapshotRow
from dbt_dag.shared.time import normalize_to_msk

logger = logging.getLogger(__name__)


class BigQueryPartitionWarehouseReader:
    def __init__(
        self,
        adapter: WarehouseAdapterProtocol,
        runtime_profile: DbtRuntimeProfile,
    ) -> None:
        self._adapter = adapter
        self._runtime_profile = runtime_profile

    def supports_partitions(self) -> bool:
        return self._adapter.adapter_kind == AdapterKind.BIGQUERY

    def fetch_latest_partition_snapshot(self, model_unique_id: str) -> list[PartitionSnapshotRow]:
        if not self.supports_partitions():
            return []
        project = _required_target_value(self._runtime_profile, "project")
        dataset = _required_target_value(self._runtime_profile, "dataset")
        sql = f"""
select
  `partition`,
  partition_date,
  row_count,
  inserted_at
from (
  select
    `partition`,
    partition_date,
    row_count,
    inserted_at,
    row_number() over(partition by `partition` order by inserted_at desc) as row_number
  from `{project}.{dataset}.stg__dbt_run_partition_info`
  where model_unique_id = {_quote_sql_string(model_unique_id)}
)
where row_number = 1
order by partition_date, `partition`
"""
        try:
            rows = self._adapter.run_query(sql).rows
        except (ValueError, WarehouseQueryError):
            logger.exception(
                "failed to read model partition snapshot from warehouse",
                extra={"model_unique_id": model_unique_id},
            )
            return []
        return [_partition_snapshot_row(row) for row in rows if _is_partition_snapshot_row(row)]

    def fetch_latest_model_run_at(self, model_unique_id: str) -> datetime | None:
        if not self.supports_partitions():
            return None
        project = _required_target_value(self._runtime_profile, "project")
        dataset = _required_target_value(self._runtime_profile, "dataset")
        sql = f"""
select max(inserted_at) as last_run_at
from `{project}.{dataset}.stg__dbt_run_results`
where model_unique_id = {_quote_sql_string(model_unique_id)}
"""
        try:
            rows = self._adapter.run_query(sql).rows
        except (ValueError, WarehouseQueryError):
            logger.exception(
                "failed to read latest model run timestamp from warehouse",
                extra={"model_unique_id": model_unique_id},
            )
            return None
        if not rows:
            return None
        return _as_datetime(rows[0].get("last_run_at"))


def _partition_snapshot_row(row: dict[str, Any]) -> PartitionSnapshotRow:
    partition_date = _partition_date(row)
    if partition_date is None:
        raise ValueError("partition_date is required")
    return PartitionSnapshotRow(
        partition_key=str(row["partition"]),
        partition_date=partition_date,
        row_count=int(row["row_count"]),
        source_inserted_at=_as_datetime(row.get("inserted_at")),
    )


def _is_partition_snapshot_row(row: dict[str, Any]) -> bool:
    return (
        row.get("partition") is not None
        and row.get("row_count") is not None
        and _partition_date(row) is not None
    )


def _partition_date(row: dict[str, Any]) -> date | None:
    partition_date = _as_date(row.get("partition_date"))
    if partition_date is not None:
        return partition_date
    return _as_date(row.get("partition"))


def _required_target_value(runtime_profile: DbtRuntimeProfile, key: str) -> str:
    value = runtime_profile.target.raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"BigQuery target must define {key}")
    return value


def _quote_sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return normalize_to_msk(value)
    return None


def _as_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return normalize_to_msk(value).date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None
