from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.dbt_runtime.types import QueryResult
from dbt_dag.tests.warehouse import WarehouseTestRunsReader


def test_warehouse_reader_uses_run_started_at_column() -> None:
    adapter = Mock()
    adapter.adapter_kind = AdapterKind.BIGQUERY
    adapter.run_query.return_value = QueryResult(
        columns=["test_unique_id", "model_unique_id", "status", "executed_at"],
        rows=[
            {
                "test_unique_id": "test.demo.not_null_orders_id",
                "model_unique_id": "model.demo.fct_orders",
                "status": "pass",
                "executed_at": datetime(2026, 6, 8, 12, 0, 0),
            }
        ],
    )
    reader = WarehouseTestRunsReader(adapter, _runtime_profile())

    result = reader.read_latest_runs()

    assert adapter.run_query.call_count == 1
    sql = adapter.run_query.call_args.args[0]
    assert "run_started_at as executed_at" in sql
    assert "order by run_started_at desc" in sql
    assert "and run_started_at is not null" in sql
    assert "test.demo.not_null_orders_id" in result


def _runtime_profile() -> Any:
    return SimpleNamespace(
        target=SimpleNamespace(
            raw={
                "project": "demo",
                "dataset": "analytics",
            }
        )
    )
