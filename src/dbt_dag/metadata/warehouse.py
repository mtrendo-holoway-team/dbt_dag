from datetime import datetime
import logging
from typing import Any

from dbt_dag.adapters.protocols import WarehouseAdapterProtocol
from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.dbt_runtime.types import WarehouseQueryError
from dbt_dag.manifest.models import DbtManifest
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.metadata.models import PartialRuntimeMetadata
from dbt_dag.metadata.models import RuntimeDataSource
from dbt_dag.shared.time import normalize_to_msk

logger = logging.getLogger(__name__)


class WarehouseMetadataReader:
    def __init__(
        self,
        adapter: WarehouseAdapterProtocol,
        runtime_profile: DbtRuntimeProfile,
    ) -> None:
        self._adapter = adapter
        self._runtime_profile = runtime_profile

    def read(self, manifest: DbtManifest) -> dict[str, PartialRuntimeMetadata]:
        if self._adapter.adapter_kind != AdapterKind.BIGQUERY:
            return {}
        duration_by_node = self._read_durations()
        updated_by_node = self._read_table_updates(manifest)
        node_ids = set(duration_by_node) | set(updated_by_node)
        return {
            node_id: PartialRuntimeMetadata(
                execution_time_seconds=duration_by_node.get(node_id),
                execution_time_source=(
                    RuntimeDataSource.WAREHOUSE
                    if node_id in duration_by_node
                    else RuntimeDataSource.NONE
                ),
                last_updated_at=updated_by_node.get(node_id),
                last_updated_source=(
                    RuntimeDataSource.WAREHOUSE
                    if node_id in updated_by_node
                    else RuntimeDataSource.NONE
                ),
            )
            for node_id in node_ids
        }

    def _read_durations(self) -> dict[str, float]:
        project = _required_target_value(self._runtime_profile, "project")
        dataset = _required_target_value(self._runtime_profile, "dataset")
        sql = f"""
select
  model_unique_id,
  median_execution_time
from (
  select
    model_unique_id,
    percentile_cont(execution_time, 0.5) over(partition by model_unique_id)
      as median_execution_time,
    row_number() over(partition by model_unique_id order by model_unique_id) as row_number
  from `{project}.{dataset}.stg__dbt_run_results`
  where model_unique_id is not null and execution_time is not null
)
where row_number = 1
"""
        try:
            rows = self._adapter.run_query(sql).rows
        except (ValueError, WarehouseQueryError):
            logger.exception("failed to read dbt run duration metadata from warehouse")
            return {}
        return {
            str(row["model_unique_id"]): float(row["median_execution_time"])
            for row in rows
            if row.get("model_unique_id") is not None
            and row.get("median_execution_time") is not None
        }

    def _read_table_updates(self, manifest: DbtManifest) -> dict[str, datetime]:
        relation_by_node = _relations_by_node(manifest)
        result: dict[str, datetime] = {}
        for group in _group_relations(relation_by_node):
            result.update(self._read_table_update_group(group))
        return result

    def _read_table_update_group(self, group: "_RelationGroup") -> dict[str, datetime]:
        names = ", ".join(_quote_sql_string(name) for name in sorted(group.node_id_by_name))
        sql = f"""
select table_id, timestamp_millis(last_modified_time) as last_updated_at
from `{group.project}.{group.dataset}.__TABLES__`
where table_id in ({names})
"""
        try:
            rows = self._adapter.run_query(sql).rows
        except WarehouseQueryError:
            logger.exception(
                "failed to read BigQuery table update metadata",
                extra={"project": group.project, "dataset": group.dataset},
            )
            return {}
        result = {}
        for row in rows:
            table_id = row.get("table_id")
            last_updated_at = _as_datetime(row.get("last_updated_at"))
            node_id = group.node_id_by_name.get(str(table_id))
            if node_id is not None and last_updated_at is not None:
                result[node_id] = last_updated_at
        return result


class _RelationGroup:
    def __init__(self, project: str, dataset: str) -> None:
        self.project = project
        self.dataset = dataset
        self.node_id_by_name: dict[str, str] = {}


def _relations_by_node(manifest: DbtManifest) -> dict[str, tuple[str, str, str]]:
    relations = {}
    for node in manifest.graph_nodes().values():
        if not _belongs_to_current_project(node, manifest.project_name):
            continue
        relation = _relation_for_node(node)
        if relation is not None:
            relations[node.unique_id] = relation
    return relations


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


def _belongs_to_current_project(node: DbtManifestNode, project_name: str) -> bool:
    if not project_name:
        return True
    return node.package_name == project_name


def _group_relations(
    relation_by_node: dict[str, tuple[str, str, str]],
) -> list[_RelationGroup]:
    groups: dict[tuple[str, str], _RelationGroup] = {}
    for node_id, (project, dataset, table_name) in relation_by_node.items():
        group = groups.setdefault((project, dataset), _RelationGroup(project, dataset))
        group.node_id_by_name[table_name] = node_id
    return list(groups.values())


def _required_target_value(runtime_profile: DbtRuntimeProfile, key: str) -> str:
    value = runtime_profile.target.raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"BigQuery target must define {key}")
    return value


def _raw_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _quote_sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return normalize_to_msk(value)
    return None
