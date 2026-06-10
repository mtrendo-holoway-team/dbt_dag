from datetime import date
from datetime import datetime
import logging
from typing import Any

from dbt_dag.adapters.protocols import WarehouseAdapterProtocol
from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.dbt_runtime.types import WarehouseQueryError
from dbt_dag.manifest.models import DbtManifestNode
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

    def fetch_latest_partition_snapshot(self, node: DbtManifestNode) -> list[PartitionSnapshotRow]:
        if not self.supports_partitions():
            return []
        model_unique_id = node.unique_id
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
        snapshot_rows = [
            _partition_snapshot_row(row) for row in rows if _is_partition_snapshot_row(row)
        ]
        return _attach_partition_updated_at(
            snapshot_rows,
            self._partition_updated_at_by_date(node),
        )

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

    def _partition_updated_at_by_date(self, node: DbtManifestNode) -> dict[date, datetime]:
        relation = _relation_for_node(node)
        partition_field = _partition_field_for_node(node)
        if relation is None or not partition_field:
            return {}
        project, dataset, identifier = relation
        if not self._has_dbt_updated_at_column(project, dataset, identifier):
            return {}
        sql = f"""
select
  date({_quote_identifier(partition_field)}) as partition_date,
  min(_dbt_updated_at) as partition_updated_at
from {_quoted_relation(project, dataset, identifier)}
where {_quote_identifier(partition_field)} is not null
group by 1
"""
        try:
            rows = self._adapter.run_query(sql).rows
        except WarehouseQueryError:
            logger.exception(
                "failed to read partition update timestamps from model table",
                extra={"model_unique_id": node.unique_id},
            )
            return {}
        return _partition_updated_at_by_date(rows)

    def _has_dbt_updated_at_column(self, project: str, dataset: str, identifier: str) -> bool:
        sql = f"""
select 1
from `{project}.{dataset}.INFORMATION_SCHEMA.COLUMNS`
where table_name = {_quote_sql_string(identifier)}
  and column_name = '_dbt_updated_at'
limit 1
"""
        try:
            rows = self._adapter.run_query(sql).rows
        except WarehouseQueryError:
            logger.exception(
                "failed to inspect model columns for partition freshness",
                extra={"project": project, "dataset": dataset, "identifier": identifier},
            )
            return False
        return bool(rows)


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


def _relation_for_node(node: DbtManifestNode) -> tuple[str, str, str] | None:
    database = _raw_str(node.raw.get("database"))
    schema = _raw_str(node.raw.get("schema"))
    identifier = (
        _raw_str(node.raw.get("identifier"))
        or _raw_str(node.raw.get("alias"))
        or _raw_str(node.raw.get("name"))
    )
    if not database or not schema or not identifier:
        return None
    return database, schema, identifier


def _partition_field_for_node(node: DbtManifestNode) -> str:
    config = node.raw.get("config")
    if not isinstance(config, dict):
        return ""
    partition_by = config.get("partition_by")
    if not isinstance(partition_by, dict):
        return ""
    return _raw_str(partition_by.get("field"))


def _quoted_relation(project: str, dataset: str, identifier: str) -> str:
    return f"`{project}.{dataset}.{identifier}`"


def _quote_identifier(value: str) -> str:
    return "`" + value.replace("`", "") + "`"


def _quote_sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _raw_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


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


def _partition_updated_at_by_date(rows: list[dict[str, Any]]) -> dict[date, datetime]:
    result: dict[date, datetime] = {}
    for row in rows:
        partition_date = _as_date(row.get("partition_date"))
        partition_updated_at = _as_datetime(row.get("partition_updated_at"))
        if partition_date is None or partition_updated_at is None:
            continue
        result[partition_date] = partition_updated_at
    return result


def _attach_partition_updated_at(
    snapshot_rows: list[PartitionSnapshotRow],
    updated_at_by_date: dict[date, datetime],
) -> list[PartitionSnapshotRow]:
    if not updated_at_by_date:
        return snapshot_rows
    return [
        PartitionSnapshotRow(
            partition_key=row.partition_key,
            partition_date=row.partition_date,
            row_count=row.row_count,
            source_inserted_at=row.source_inserted_at,
            partition_updated_at=updated_at_by_date.get(row.partition_date),
        )
        for row in snapshot_rows
    ]
