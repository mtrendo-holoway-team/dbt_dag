from datetime import date
import json
from pathlib import Path
import pytest

from litestar.plugins.jinja import JinjaTemplateEngine

from dbt_dag.inspectors import actions as actions_inspector
from dbt_dag.inspectors import partition as partition_inspector
from dbt_dag.inspectors import tests as tests_inspector
from dbt_dag.inspectors.dto import NodeInspectorContextDTO
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.metadata.models import empty_node_runtime_metadata
from dbt_dag.partitions.models import ModelPartitionCalendarDTO
from dbt_dag.partitions.models import PartitionDayCellDTO
from dbt_dag.partitions.models import PartitionFillLevel
from dbt_dag.partitions.models import PartitionMonthDTO
from dbt_dag.partitions.models import PartitionSyncStatus
from dbt_dag.tests.models import ModelTestResultDTO
from dbt_dag.tests.models import ModelTestStatus
from dbt_dag.tests.models import ModelTestSummaryDTO
from dbt_dag.web import render
from dbt_dag.web.node_status import resolve_node_status_icon
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
            status_icon=resolve_node_status_icon(None),
            last_update_block_id="inspector-block-last-update-token123",
            tests_block_id="inspector-block-tests-token123",
            partition_block_id="inspector-block-partition-token123",
            actions_block_id="inspector-block-actions-token123",
            tasks_block_id="inspector-block-tasks-token123",
        )
    )

    assert "Staged orders" in html
    assert 'id="inspector-block-last-update-token123"' in html
    assert 'id="inspector-block-tests-token123"' in html
    assert "/inspector/node/model.demo.stg_orders/last-update?selection_token=token123" in html
    assert 'id="inspector-block-tasks-token123"' in html
    assert "/inspector/node/model.demo.stg_orders/tasks?selection_token=token123" in html
    assert "/inspector/node/model.demo.stg_orders/tests?selection_token=token123" in html


def test_actions_template_renders_model_actions_with_shortcuts() -> None:
    inspector = _inspector_context(resource_type="model")

    html = (
        _template_engine()
        .get_template(actions_inspector.TEMPLATE_NAME)
        .render(**actions_inspector.build_template_context(inspector))
    )

    assert "Build" in html
    assert "Run" in html
    assert "Test" in html
    assert "Compile" in html
    assert "ab" in html
    assert "/actions/node/model.demo.stg_orders/execute/compile" in html


def test_actions_template_hides_dbt_buttons_for_non_model_nodes() -> None:
    inspector = _inspector_context(resource_type="source")

    html = (
        _template_engine()
        .get_template(actions_inspector.TEMPLATE_NAME)
        .render(**actions_inspector.build_template_context(inspector))
    )

    assert html.strip() == "</section>"
    assert 'data-command-action="' not in html


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
        tests=None,
        tests_loading=False,
        supports_partitions=True,
    )

    html = (
        _template_engine()
        .get_template(partition_inspector.TEMPLATE_NAME)
        .render(**partition_inspector.build_template_context(inspector))
    )

    assert "Обновить" in html
    assert "partition-day-no-data" in html
    assert "partition-day-normal" in html
    assert "2026-06-01 - Нет данных" in html
    assert ">2026<" in html


def test_partition_template_hides_empty_current_day_marker() -> None:
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
                        date=date(2026, 6, 3),
                        row_count=None,
                        fill_level=PartitionFillLevel.EMPTY,
                    ),
                    PartitionDayCellDTO(
                        date=date(2026, 6, 4),
                        row_count=None,
                        fill_level=PartitionFillLevel.EMPTY,
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
        tests=None,
        tests_loading=False,
        supports_partitions=True,
    )

    context = partition_inspector.build_template_context(inspector)

    assert (
        context["month_groups"][0]["months"][0]["days"][0]["color_class"] == "partition-day-no-data"
    )
    assert context["month_groups"][0]["months"][0]["days"][1]["color_class"] == ""


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
        tests=None,
        tests_loading=False,
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
        tests=None,
        tests_loading=False,
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
        partition_inspector._partition_day_color_class(None, 10.0, False, is_current_day=True) == ""
    )
    assert (
        partition_inspector._partition_day_color_class(2, 10.0, False) == "partition-day-critical"
    )
    assert partition_inspector._partition_day_color_class(7, 10.0, False) == "partition-day-low"
    assert partition_inspector._partition_day_color_class(10, 10.0, False) == "partition-day-normal"
    assert partition_inspector._partition_day_color_class(13, 10.0, False) == "partition-day-high"
    assert partition_inspector._partition_day_color_class(2, 10.0, True) == "partition-day-normal"


def test_tests_template_renders_missing_state() -> None:
    inspector = _inspector_context(
        resource_type="model", tests=_missing_tests(), tests_loading=True
    )

    html = (
        _template_engine()
        .get_template(tests_inspector.TEMPLATE_NAME)
        .render(**tests_inspector.build_template_context(inspector))
    )

    assert "нет тестов" in html
    assert "status-dot-missing" in html
    assert "status-dot-loading" in html


def test_tests_template_renders_test_list() -> None:
    inspector = _inspector_context(
        resource_type="model",
        tests=ModelTestSummaryDTO(
            model_unique_id="model.demo.stg_orders",
            status=ModelTestStatus.FAILED,
            tests=[
                ModelTestResultDTO(
                    test_unique_id="test.demo.not_null_orders_id",
                    test_name="not_null_orders_id",
                    status=ModelTestStatus.FAILED,
                    executed_at=None,
                )
            ],
        ),
    )

    html = (
        _template_engine()
        .get_template(tests_inspector.TEMPLATE_NAME)
        .render(**tests_inspector.build_template_context(inspector))
    )

    assert "not_null_orders_id" in html
    assert "status-dot-failed" in html


def _template_engine() -> JinjaTemplateEngine:
    return JinjaTemplateEngine(directory=TEMPLATES_DIRECTORY)


def _inspector_context(
    resource_type: str,
    tests: ModelTestSummaryDTO | None = None,
    tests_loading: bool = False,
) -> NodeInspectorContextDTO:
    return NodeInspectorContextDTO(
        selection_token="token123",
        node=DbtManifestNode(
            unique_id="model.demo.stg_orders",
            name="stg_orders",
            resource_type=resource_type,
            description="Staged orders",
            depends_on=[],
            package_name="demo",
            path="models/stg/stg_orders.sql",
            fqn=["demo", "stg", "stg_orders"],
            raw={},
        ),
        runtime=empty_node_runtime_metadata(),
        tasks=[],
        partition_calendar=None,
        tests=tests,
        tests_loading=tests_loading,
        supports_partitions=resource_type == "model",
    )


def _missing_tests() -> ModelTestSummaryDTO:
    return ModelTestSummaryDTO(
        model_unique_id="model.demo.stg_orders",
        status=ModelTestStatus.MISSING,
        tests=[],
    )
