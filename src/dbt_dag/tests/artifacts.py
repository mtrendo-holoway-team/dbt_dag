from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any

from dbt_dag.shared.time import normalize_to_msk
from dbt_dag.tests.models import LatestTestRunDTO

logger = logging.getLogger(__name__)


class RunResultsTestReader:
    def __init__(self, project_dir: Path) -> None:
        self._path = project_dir / "target" / "run_results.json"

    def read_latest_runs(self) -> dict[str, LatestTestRunDTO]:
        raw = self._load_raw()
        if not isinstance(raw, dict):
            return {}
        generated_at = _parse_datetime(_mapping(raw.get("metadata")).get("generated_at"))
        return _results_from_items(raw.get("results", []), generated_at)

    def _load_raw(self) -> Any:
        if not self._path.exists():
            return {}
        try:
            with self._path.open(encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            logger.exception("failed to read dbt run results artifact for tests")
            return {}


def _parse_result(
    item: dict[str, Any],
    generated_at: datetime | None,
) -> LatestTestRunDTO | None:
    unique_id = item.get("unique_id")
    if not isinstance(unique_id, str) or not unique_id.startswith("test."):
        return None
    executed_at = _execution_completed_at(item) or generated_at
    status = item.get("status")
    if executed_at is None or not isinstance(status, str) or not status:
        return None
    return LatestTestRunDTO(
        test_unique_id=unique_id,
        model_unique_id="",
        status=status,
        executed_at=executed_at,
    )


def _results_from_items(
    items: Any,
    generated_at: datetime | None,
) -> dict[str, LatestTestRunDTO]:
    results = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        result = _parse_result(item, generated_at)
        if result is None:
            continue
        results[result.test_unique_id] = result
    return results


def _execution_completed_at(item: dict[str, Any]) -> datetime | None:
    timings = [timing for timing in item.get("timing", []) if isinstance(timing, dict)]
    completed_times = [
        value
        for value in (_parse_datetime(timing.get("completed_at")) for timing in timings)
        if value is not None
    ]
    if not completed_times:
        return None
    return max(completed_times)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return normalize_to_msk(parsed)
