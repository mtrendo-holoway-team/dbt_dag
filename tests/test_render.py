from datetime import date
import json
from pathlib import Path
import pytest

from litestar.plugins.jinja import JinjaTemplateEngine

from dbt_dag.inspectors import partition as partition_inspector
from dbt_dag.inspectors.dto import NodeInspectorContextDTO
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.metadata.models import empty_node_runtime_metadata
from dbt_dag.partitions.models import ModelPartitionCalendarDTO
from dbt_dag.partitions.models import PartitionDayCellDTO
from dbt_dag.partitions.models import PartitionFillLevel
from dbt_dag.partitions.models import PartitionMonthDTO
from dbt_dag.partitions.models import PartitionSyncStatus
from dbt_dag.web import render
from dbt_dag.web.template_config import TEMPLATES_DIRECTORY


def test_render_page_uses_vite_manifest_assets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "dist" / ".vite" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "src/dbt_dag/web/static/css/tailwind.css": {
                    "file": "assets/styles.css",
                },
                "src/dbt_dag/web/static/js/graph.ts": {
                    "file": "assets/graph.js",
                },
                "src/dbt_dag/web/static/js/search.ts": {
                    "file": "assets/search.js",
                },
                "src/dbt_dag/web/static/js/inspectors.ts": {
                    "file": "assets/inspectors.js",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(render, "VITE_MANIFEST_PATH", manifest_path)

    html = render.render_page()

    assert "/static/dist/assets/graph.js" in html
    assert "/static/dist/assets/search.js" in html
    assert "/static/dist/assets/inspectors.js" in html
    assert "/static/dist/assets/styles.css" in html
    assert "/static/js/graph.ts" not in html


def test_shell_template_renders_tokenized_block_ids() -> None:
    html = (
        _template_engine()
        .get_template("inspectors/shell.html")
        .render(
            node=DbtManifestNode(
                unique_id="model.demo.stg_orders",
                name="stg_orders",
                resource_type="model",
                description="Staged orders",
                depends_on=[],
                package_name="demo",
                path="models/stg/stg_orders.sql",
                fqn=["demo", "stg", "stg_orders"],
                raw={},
            ),
            selection_token="token123",
            model_info_block_id="inspector-block-model-info-token123",
            description_block_id="inspector-block-description-token123",
            last_update_block_id="inspector-block-last-update-token123",
            partition_block_id="inspector-block-partition-token123",
            actions_block_id="inspector-block-actions-token123",
            tasks_block_id="inspector-block-tasks-token123",
        )
    )

    assert 'id="inspector-block-model-info-token123"' in html
    assert "/inspector/node/model.demo.stg_orders/model-info?selection_token=token123" in html
    assert 'id="inspector-block-tasks-token123"' in html
    assert "/inspector/node/model.demo.stg_orders/tasks?selection_token=token123" in html


def test_partition_template_contains_fill_states() -> None:
    calendar = ModelPartitionCalendarDTO(
        model_unique_id="model.demo.stg_orders",
        range_start=None,
        range_end=date(2026, 6, 4),
        median_row_count=10.0,
        months=[
            PartitionMonthDTO(
                year=2026,
                month_label="Июнь",
                leading_empty_days=0,
                days=[
                    PartitionDayCellDTO(
                        date=date(2026, 6, 1),
                        row_count=None,
                        fill_level=PartitionFillLevel.EMPTY,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 2),
                        row_count=5,
                        fill_level=PartitionFillLevel.HALF,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 3),
                        row_count=10,
                        fill_level=PartitionFillLevel.FULL,
                    ),
                ],
            )
        ],
        is_stale=False,
        is_refreshing=False,
        last_synced_at=None,
        sync_status=PartitionSyncStatus.IDLE,
        last_error="",
    )
    inspector = NodeInspectorContextDTO(
        selection_token="token123",
        node=DbtManifestNode(
            unique_id="model.demo.stg_orders",
            name="stg_orders",
            resource_type="model",
            description="Staged orders",
            depends_on=[],
            package_name="demo",
            path="models/stg/stg_orders.sql",
            fqn=["demo", "stg", "stg_orders"],
            raw={},
        ),
        runtime=empty_node_runtime_metadata(),
        tasks=[],
        partition_calendar=calendar,
        supports_partitions=True,
    )

    html = (
        _template_engine()
        .get_template(partition_inspector.TEMPLATE_NAME)
        .render(**partition_inspector.build_template_context(inspector))
    )

    assert "Refresh partition data" in html
    assert "partition-day-no-data" in html
    assert "partition-day-normal" in html
    assert "2026-06-01 - No data" in html
    assert ">2026<" in html


def test_partition_template_uses_green_only_for_small_medians() -> None:
    calendar = ModelPartitionCalendarDTO(
        model_unique_id="model.demo.stg_orders",
        range_start=None,
        range_end=date(2026, 6, 4),
        median_row_count=99.0,
        months=[
            PartitionMonthDTO(
                year=2026,
                month_label="Июнь",
                leading_empty_days=0,
                days=[
                    PartitionDayCellDTO(
                        date=date(2026, 6, 1),
                        row_count=None,
                        fill_level=PartitionFillLevel.EMPTY,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 2),
                        row_count=1,
                        fill_level=PartitionFillLevel.HALF,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 3),
                        row_count=200,
                        fill_level=PartitionFillLevel.FULL,
                    ),
                ],
            )
        ],
        is_stale=False,
        is_refreshing=False,
        last_synced_at=None,
        sync_status=PartitionSyncStatus.IDLE,
        last_error="",
    )
    inspector = NodeInspectorContextDTO(
        selection_token="token123",
        node=DbtManifestNode(
            unique_id="model.demo.stg_orders",
            name="stg_orders",
            resource_type="model",
            description="Staged orders",
            depends_on=[],
            package_name="demo",
            path="models/stg/stg_orders.sql",
            fqn=["demo", "stg", "stg_orders"],
            raw={},
        ),
        runtime=empty_node_runtime_metadata(),
        tasks=[],
        partition_calendar=calendar,
        supports_partitions=True,
    )

    html = (
        _template_engine()
        .get_template(partition_inspector.TEMPLATE_NAME)
        .render(**partition_inspector.build_template_context(inspector))
    )

    assert "partition-day-no-data" in html
    assert "partition-day-normal" in html
    assert "partition-day-low" not in html
    assert "partition-day-critical" not in html
    assert "partition-day-high" not in html


def test_partition_template_uses_future_days_when_history_is_short() -> None:
    calendar = ModelPartitionCalendarDTO(
        model_unique_id="model.demo.stg_orders",
        range_start=None,
        range_end=date(2026, 6, 8),
        median_row_count=10.0,
        months=[
            PartitionMonthDTO(
                year=2026,
                month_label="Июнь",
                leading_empty_days=0,
                days=[
                    PartitionDayCellDTO(
                        date=date(2026, 6, 1),
                        row_count=5,
                        fill_level=PartitionFillLevel.HALF,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 2),
                        row_count=10,
                        fill_level=PartitionFillLevel.FULL,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 3),
                        row_count=10,
                        fill_level=PartitionFillLevel.FULL,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 4),
                        row_count=10,
                        fill_level=PartitionFillLevel.FULL,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 5),
                        row_count=10,
                        fill_level=PartitionFillLevel.FULL,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 6),
                        row_count=10,
                        fill_level=PartitionFillLevel.FULL,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 7),
                        row_count=10,
                        fill_level=PartitionFillLevel.FULL,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 8),
                        row_count=10,
                        fill_level=PartitionFillLevel.FULL,
                    ),
                ],
            )
        ],
        is_stale=False,
        is_refreshing=False,
        last_synced_at=None,
        sync_status=PartitionSyncStatus.IDLE,
        last_error="",
    )
    inspector = NodeInspectorContextDTO(
        selection_token="token123",
        node=DbtManifestNode(
            unique_id="model.demo.stg_orders",
            name="stg_orders",
            resource_type="model",
            description="Staged orders",
            depends_on=[],
            package_name="demo",
            path="models/stg/stg_orders.sql",
            fqn=["demo", "stg", "stg_orders"],
            raw={},
        ),
        runtime=empty_node_runtime_metadata(),
        tasks=[],
        partition_calendar=calendar,
        supports_partitions=True,
    )

    context = partition_inspector.build_template_context(inspector)

    assert (
        context["month_groups"][0]["months"][0]["days"][0]["color_class"] == "partition-day-normal"
    )


def test_partition_day_color_thresholds() -> None:
    assert (
        partition_inspector._partition_day_color_class(None, 10.0, False) == "partition-day-no-data"
    )
    assert (
        partition_inspector._partition_day_color_class(2, 10.0, False) == "partition-day-critical"
    )
    assert partition_inspector._partition_day_color_class(7, 10.0, False) == "partition-day-low"
    assert partition_inspector._partition_day_color_class(10, 10.0, False) == "partition-day-normal"
    assert partition_inspector._partition_day_color_class(13, 10.0, False) == "partition-day-high"
    assert partition_inspector._partition_day_color_class(2, 10.0, True) == "partition-day-normal"


def _template_engine() -> JinjaTemplateEngine:
    return JinjaTemplateEngine(directory=TEMPLATES_DIRECTORY)
