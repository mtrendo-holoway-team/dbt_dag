from datetime import datetime
import logging
from typing import Any

from dbt_dag.adapters.protocols import WarehouseAdapterProtocol
from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.dbt_runtime.types import WarehouseQueryError
from dbt_dag.shared.time import normalize_to_msk
from dbt_dag.tests.models import LatestTestRunDTO

logger = logging.getLogger(__name__)
_TEST_RUNS_TABLE = "stg__dbt_test_runs"
_RUN_STARTED_AT_COLUMN = "run_started_at"


class WarehouseTestRunsReader:
    def __init__(
        self,
        adapter: WarehouseAdapterProtocol,
        runtime_profile: DbtRuntimeProfile,
    ) -> None:
        self._adapter = adapter
        self._runtime_profile = runtime_profile

    def read_latest_runs(self) -> dict[str, LatestTestRunDTO]:
        if self._adapter.adapter_kind != AdapterKind.BIGQUERY:
            return {}
        sql = self._latest_runs_sql()
        try:
            rows = self._adapter.run_query(sql).rows
        except (ValueError, WarehouseQueryError):
            logger.exception("failed to read dbt test run metadata from warehouse")
            return {}
        results = {}
        for row in rows:
            result = _parse_result(row)
            if result is None:
                continue
            results[result.test_unique_id] = result
        return results

    def _latest_runs_sql(self) -> str:
        project = _required_target_value(self._runtime_profile, "project")
        dataset = _required_target_value(self._runtime_profile, "dataset")
        return f"""
select
  test_unique_id,
  model_unique_id,
  status,
  executed_at
from (
  select
    test_unique_id,
    model_unique_id,
    status,
    {_RUN_STARTED_AT_COLUMN} as executed_at,
    row_number() over(
      partition by test_unique_id
      order by {_RUN_STARTED_AT_COLUMN} desc
    ) as row_number
  from `{project}.{dataset}.{_TEST_RUNS_TABLE}`
  where
    model_unique_id is not null
    and test_unique_id is not null
    and status is not null
    and {_RUN_STARTED_AT_COLUMN} is not null
)
where row_number = 1
"""


def _required_target_value(runtime_profile: DbtRuntimeProfile, key: str) -> str:
    value = runtime_profile.target.raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"BigQuery target must define {key}")
    return value


def _parse_result(row: dict[str, Any]) -> LatestTestRunDTO | None:
    test_unique_id = row.get("test_unique_id")
    model_unique_id = row.get("model_unique_id")
    status = row.get("status")
    executed_at = row.get("executed_at")
    if (
        not isinstance(test_unique_id, str)
        or not test_unique_id
        or not isinstance(model_unique_id, str)
        or not model_unique_id
        or not isinstance(status, str)
        or not status
        or not isinstance(executed_at, datetime)
    ):
        return None
    return LatestTestRunDTO(
        test_unique_id=test_unique_id,
        model_unique_id=model_unique_id,
        status=status,
        executed_at=normalize_to_msk(executed_at),
    )
