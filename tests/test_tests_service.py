from datetime import datetime
from pathlib import Path
import pytest
from typing import Any, cast

from dbt_dag.manifest.models import DbtManifest
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.manifest.parser import load_manifest
from dbt_dag.shared.time import MSK
from dbt_dag.tests import service as tests_service
from dbt_dag.tests.models import LatestTestRunDTO
from dbt_dag.tests.models import ModelTestStatus
from dbt_dag.tests.service import ModelTestService


def test_model_without_manifest_tests_is_missing(dbt_project: Path) -> None:
    service = _service({}, {})
    manifest = load_manifest(dbt_project / "target" / "manifest.json")

    summaries = service.load(manifest, include_warehouse=False)

    assert summaries["model.demo.stg_orders"].status == ModelTestStatus.MISSING


def test_all_fresh_passes_are_green(
    dbt_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tests_service,
        "now_msk",
        lambda: datetime(2026, 6, 8, 12, tzinfo=MSK),
    )
    manifest = load_manifest(dbt_project / "target" / "manifest.json")
    service = _service(
        {},
        {
            "test.demo.not_null_orders_id": LatestTestRunDTO(
                test_unique_id="test.demo.not_null_orders_id",
                model_unique_id="model.demo.fct_orders",
                status="pass",
                executed_at=datetime(2026, 6, 8, 10, tzinfo=MSK),
            )
        },
    )

    summaries = service.load(manifest)

    assert summaries["model.demo.fct_orders"].status == ModelTestStatus.PASSED


def test_old_success_run_is_stale(dbt_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tests_service,
        "now_msk",
        lambda: datetime(2026, 6, 8, 12, tzinfo=MSK),
    )
    manifest = load_manifest(dbt_project / "target" / "manifest.json")
    service = _service(
        {},
        {
            "test.demo.not_null_orders_id": LatestTestRunDTO(
                test_unique_id="test.demo.not_null_orders_id",
                model_unique_id="model.demo.fct_orders",
                status="pass",
                executed_at=datetime(2026, 6, 7, 10, tzinfo=MSK),
            )
        },
    )

    summaries = service.load(manifest)

    assert summaries["model.demo.fct_orders"].status == ModelTestStatus.STALE


def test_failed_run_turns_model_red(dbt_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tests_service,
        "now_msk",
        lambda: datetime(2026, 6, 8, 12, tzinfo=MSK),
    )
    manifest = load_manifest(dbt_project / "target" / "manifest.json")
    service = _service(
        {},
        {
            "test.demo.not_null_orders_id": LatestTestRunDTO(
                test_unique_id="test.demo.not_null_orders_id",
                model_unique_id="model.demo.fct_orders",
                status="fail",
                executed_at=datetime(2026, 6, 8, 11, tzinfo=MSK),
            )
        },
    )

    summaries = service.load(manifest)

    assert summaries["model.demo.fct_orders"].status == ModelTestStatus.FAILED


def test_artifact_data_is_used_before_warehouse(
    dbt_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        tests_service,
        "now_msk",
        lambda: datetime(2026, 6, 8, 12, tzinfo=MSK),
    )
    manifest = load_manifest(dbt_project / "target" / "manifest.json")
    service = _service(
        {
            "test.demo.not_null_orders_id": LatestTestRunDTO(
                test_unique_id="test.demo.not_null_orders_id",
                model_unique_id="",
                status="pass",
                executed_at=datetime(2026, 6, 8, 11, tzinfo=MSK),
            )
        },
        {
            "test.demo.not_null_orders_id": LatestTestRunDTO(
                test_unique_id="test.demo.not_null_orders_id",
                model_unique_id="model.demo.fct_orders",
                status="fail",
                executed_at=datetime(2026, 6, 8, 9, tzinfo=MSK),
            )
        },
    )

    initial = service.load(manifest, include_warehouse=False)
    enriched = service.load(manifest, include_warehouse=True)

    assert initial["model.demo.fct_orders"].status == ModelTestStatus.PASSED
    assert enriched["model.demo.fct_orders"].status == ModelTestStatus.FAILED


def test_test_name_comes_from_manifest_not_unique_id() -> None:
    manifest = DbtManifest(
        project_name="demo",
        nodes={
            "model.demo.orders": DbtManifestNode(
                unique_id="model.demo.orders",
                name="orders",
                resource_type="model",
                description="",
                depends_on=[],
                package_name="demo",
                path="models/orders.sql",
                fqn=["demo", "orders"],
                raw={},
            ),
            "test.demo.orders__custom_hash": DbtManifestNode(
                unique_id="test.demo.orders__custom_hash",
                name="accepted_values_orders_status",
                resource_type="test",
                description="",
                depends_on=["model.demo.orders"],
                package_name="demo",
                path="models/schema.yml",
                fqn=["demo", "orders", "accepted_values_orders_status"],
                raw={},
            ),
        },
        sources={},
        exposures={},
    )

    summary = _service({}, {}).load(manifest, include_warehouse=False)["model.demo.orders"]

    assert summary.tests[0].test_name == "accepted_values_orders_status"


class _Reader:
    def __init__(self, results: dict[str, LatestTestRunDTO]) -> None:
        self._results = results

    def read_latest_runs(self) -> dict[str, LatestTestRunDTO]:
        return dict(self._results)


def _service(
    artifact_results: dict[str, LatestTestRunDTO],
    warehouse_results: dict[str, LatestTestRunDTO],
) -> ModelTestService:
    return ModelTestService(
        cast(Any, _Reader(artifact_results)),
        cast(Any, _Reader(warehouse_results)),
    )
