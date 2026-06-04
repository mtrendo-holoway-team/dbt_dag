from datetime import date
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from dbt_dag.db.session import create_db_engine
from dbt_dag.db.session import create_session_factory
from dbt_dag.db.session import init_db
from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.dbt_runtime.types import DbtProjectPaths
from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.dbt_runtime.types import DbtTarget
from dbt_dag.dbt_runtime.types import QueryResult
from dbt_dag.partitions.models import PartitionFillLevel
from dbt_dag.partitions.models import PartitionSnapshotRow
from dbt_dag.partitions.models import PartitionSyncStatus
from dbt_dag.partitions.repository import ModelPartitionRepository
from dbt_dag.partitions.service import ModelPartitionService
from dbt_dag.partitions.warehouse import BigQueryPartitionWarehouseReader
from dbt_dag.shared.time import MSK


def test_partition_warehouse_reader_returns_latest_rows_by_partition(tmp_path: Path) -> None:
    adapter = Mock()
    adapter.adapter_kind = AdapterKind.BIGQUERY
    adapter.run_query.return_value = QueryResult(
        columns=["partition", "partition_date", "row_count", "inserted_at"],
        rows=[
            {
                "partition": "2026-06-01",
                "partition_date": date(2026, 6, 1),
                "row_count": 20,
                "inserted_at": datetime(2026, 6, 4, 12, tzinfo=MSK),
            }
        ],
    )

    reader = BigQueryPartitionWarehouseReader(adapter, _runtime_profile(tmp_path))
    rows = reader.fetch_latest_partition_snapshot("model.demo.stg_orders")

    assert rows == [
        PartitionSnapshotRow(
            partition_key="2026-06-01",
            partition_date=date(2026, 6, 1),
            row_count=20,
            source_inserted_at=datetime(2026, 6, 4, 12, tzinfo=MSK),
        )
    ]
    assert "stg__dbt_run_partition_info" in adapter.run_query.call_args.args[0]
    assert "model.demo.stg_orders" in adapter.run_query.call_args.args[0]


def test_partition_warehouse_reader_falls_back_to_partition_key_for_date(tmp_path: Path) -> None:
    adapter = Mock()
    adapter.adapter_kind = AdapterKind.BIGQUERY
    adapter.run_query.return_value = QueryResult(
        columns=["partition", "partition_date", "row_count", "inserted_at"],
        rows=[
            {
                "partition": "2026-06-01",
                "partition_date": None,
                "row_count": 20,
                "inserted_at": datetime(2026, 6, 4, 12, tzinfo=MSK),
            }
        ],
    )

    reader = BigQueryPartitionWarehouseReader(adapter, _runtime_profile(tmp_path))
    rows = reader.fetch_latest_partition_snapshot("model.demo.stg_orders")

    assert rows == [
        PartitionSnapshotRow(
            partition_key="2026-06-01",
            partition_date=date(2026, 6, 1),
            row_count=20,
            source_inserted_at=datetime(2026, 6, 4, 12, tzinfo=MSK),
        )
    ]


def test_partition_warehouse_reader_accepts_partition_date_string(tmp_path: Path) -> None:
    adapter = Mock()
    adapter.adapter_kind = AdapterKind.BIGQUERY
    adapter.run_query.return_value = QueryResult(
        columns=["partition", "partition_date", "row_count", "inserted_at"],
        rows=[
            {
                "partition": "p20260601",
                "partition_date": "2026-06-01",
                "row_count": 20,
                "inserted_at": datetime(2026, 6, 4, 12, tzinfo=MSK),
            }
        ],
    )

    reader = BigQueryPartitionWarehouseReader(adapter, _runtime_profile(tmp_path))
    rows = reader.fetch_latest_partition_snapshot("model.demo.stg_orders")

    assert rows == [
        PartitionSnapshotRow(
            partition_key="p20260601",
            partition_date=date(2026, 6, 1),
            row_count=20,
            source_inserted_at=datetime(2026, 6, 4, 12, tzinfo=MSK),
        )
    ]


def test_partition_repository_replaces_snapshot_and_sync_state(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    repository.replace_snapshot(
        "model.demo.stg_orders",
        [
            PartitionSnapshotRow(
                partition_key="2026-06-01",
                partition_date=date(2026, 6, 1),
                row_count=10,
                source_inserted_at=datetime(2026, 6, 4, 10, tzinfo=MSK),
            )
        ],
    )

    snapshot = repository.list_snapshot("model.demo.stg_orders")
    sync_state = repository.get_sync_state("model.demo.stg_orders")

    assert len(snapshot) == 1
    assert snapshot[0].row_count == 10
    assert sync_state is not None
    assert sync_state.sync_status == PartitionSyncStatus.SUCCEEDED
    assert sync_state.last_source_inserted_at == datetime(2026, 6, 4, 10, tzinfo=MSK)


def test_partition_service_marks_missing_cache_as_stale(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    warehouse_reader = Mock()
    warehouse_reader.supports_partitions.return_value = True
    warehouse_reader.fetch_latest_model_run_at.return_value = None
    service = ModelPartitionService(repository, warehouse_reader)

    calendar = service.build_calendar("model.demo.stg_orders", None)

    assert calendar.is_stale is True
    assert calendar.months == []


def test_partition_service_uses_runtime_or_run_results_for_stale_check(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.replace_snapshot(
        "model.demo.stg_orders",
        [
            PartitionSnapshotRow(
                partition_key="2026-06-01",
                partition_date=date(2026, 6, 1),
                row_count=5,
                source_inserted_at=datetime(2026, 6, 4, 9, tzinfo=MSK),
            )
        ],
    )
    warehouse_reader = Mock()
    warehouse_reader.supports_partitions.return_value = True
    warehouse_reader.fetch_latest_model_run_at.return_value = datetime(2026, 6, 4, 11, tzinfo=MSK)
    service = ModelPartitionService(repository, warehouse_reader)

    calendar = service.build_calendar(
        "model.demo.stg_orders",
        datetime(2026, 6, 4, 10, tzinfo=MSK),
    )

    assert calendar.is_stale is True


def test_partition_service_builds_median_fill_levels(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.replace_snapshot(
        "model.demo.stg_orders",
        [
            PartitionSnapshotRow(
                partition_key="2026-06-01",
                partition_date=date(2026, 6, 1),
                row_count=10,
                source_inserted_at=datetime(2026, 6, 4, 10, tzinfo=MSK),
            ),
            PartitionSnapshotRow(
                partition_key="2026-06-02",
                partition_date=date(2026, 6, 2),
                row_count=30,
                source_inserted_at=datetime(2026, 6, 4, 10, tzinfo=MSK),
            ),
        ],
    )
    warehouse_reader = Mock()
    warehouse_reader.supports_partitions.return_value = True
    warehouse_reader.fetch_latest_model_run_at.return_value = None
    service = ModelPartitionService(repository, warehouse_reader)

    calendar = service.build_calendar("model.demo.stg_orders", None)
    days = calendar.months[0].days[:2]

    assert calendar.median_row_count == 20.0
    assert calendar.months[0].month_label == "Июнь"
    assert days[0].fill_level == PartitionFillLevel.HALF
    assert days[1].fill_level == PartitionFillLevel.FULL


def _repository(tmp_path: Path) -> ModelPartitionRepository:
    engine = create_db_engine(tmp_path / "partitions.sqlite")
    init_db(engine)
    return ModelPartitionRepository(create_session_factory(engine))


def _runtime_profile(tmp_path: Path) -> DbtRuntimeProfile:
    return DbtRuntimeProfile(
        profile_name="demo",
        target=DbtTarget(
            name="dev",
            target_type="bigquery",
            raw={"project": "demo", "dataset": "analytics"},
        ),
        adapter_kind=AdapterKind.BIGQUERY,
        paths=DbtProjectPaths(
            project_dir=tmp_path,
            manifest_path=tmp_path / "manifest.json",
            profiles_dir=tmp_path,
        ),
    )
