from datetime import date
import json
from pathlib import Path
import pytest

from dbt_dag.partitions.models import ModelPartitionCalendarDTO
from dbt_dag.partitions.models import PartitionDayCellDTO
from dbt_dag.partitions.models import PartitionFillLevel
from dbt_dag.partitions.models import PartitionMonthDTO
from dbt_dag.partitions.models import PartitionSyncStatus
from dbt_dag.web import render


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


def test_render_partition_calendar_contains_fill_states() -> None:
    html = render.render_partition_calendar(
        "model.demo.stg_orders",
        ModelPartitionCalendarDTO(
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
        ),
    )

    assert "Refresh partition data" in html
    assert "partition-day-half" in html
    assert "partition-day-full" in html
    assert "2026-06-01 - No data" in html
    assert ">2026<" in html


def test_render_partition_calendar_keeps_current_month_first() -> None:
    html = render.render_partition_calendar(
        "model.demo.stg_orders",
        ModelPartitionCalendarDTO(
            model_unique_id="model.demo.stg_orders",
            range_start=None,
            range_end=date(2026, 6, 4),
            median_row_count=None,
            months=[
                PartitionMonthDTO(year=2026, month_label="Июнь", leading_empty_days=0, days=[]),
                PartitionMonthDTO(year=2026, month_label="Май", leading_empty_days=0, days=[]),
                PartitionMonthDTO(year=2026, month_label="Апрель", leading_empty_days=0, days=[]),
                PartitionMonthDTO(year=2025, month_label="Декабрь", leading_empty_days=0, days=[]),
            ],
            is_stale=False,
            is_refreshing=False,
            last_synced_at=None,
            sync_status=PartitionSyncStatus.IDLE,
            last_error="",
        ),
    )

    assert html.index("Июнь") < html.index("Май") < html.index("Апрель")
    assert html.index(">2026<") < html.index(">2025<")
