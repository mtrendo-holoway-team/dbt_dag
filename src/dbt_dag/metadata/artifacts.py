from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any

from dbt_dag.metadata.models import empty_partial_metadata
from dbt_dag.metadata.models import PartialRuntimeMetadata
from dbt_dag.metadata.models import RuntimeDataSource
from dbt_dag.shared.time import normalize_to_msk

logger = logging.getLogger(__name__)


class RunResultsArtifactReader:
    def __init__(self, project_dir: Path) -> None:
        self._path = project_dir / "target" / "run_results.json"

    def read(self) -> dict[str, PartialRuntimeMetadata]:
        if not self._path.exists():
            return {}
        try:
            with self._path.open(encoding="utf-8") as file:
                raw = json.load(file)
        except (OSError, json.JSONDecodeError):
            logger.exception("failed to read dbt run results artifact")
            return {}
        if not isinstance(raw, dict):
            return {}
        return self._read_results(raw)

    def fingerprint(self) -> str:
        try:
            stat = self._path.stat()
        except OSError:
            return "missing"
        return f"{stat.st_mtime_ns}:{stat.st_size}"

    def _read_results(self, raw: dict[str, Any]) -> dict[str, PartialRuntimeMetadata]:
        generated_at = _parse_datetime(_mapping(raw.get("metadata")).get("generated_at"))
        result: dict[str, PartialRuntimeMetadata] = {}
        for item in raw.get("results", []):
            if not isinstance(item, dict):
                continue
            unique_id = item.get("unique_id")
            if not isinstance(unique_id, str) or not unique_id.startswith("model."):
                continue
            result[unique_id] = self._metadata_for_result(item, generated_at)
        return result

    def _metadata_for_result(
        self,
        item: dict[str, Any],
        generated_at: datetime | None,
    ) -> PartialRuntimeMetadata:
        execution_time = _as_float(item.get("execution_time"))
        last_updated_at = _execution_completed_at(item) or generated_at
        metadata = empty_partial_metadata()
        return PartialRuntimeMetadata(
            execution_time_seconds=execution_time,
            execution_time_source=(
                RuntimeDataSource.RUN_RESULTS
                if execution_time is not None
                else metadata.execution_time_source
            ),
            last_updated_at=last_updated_at,
            last_updated_source=(
                RuntimeDataSource.RUN_RESULTS
                if last_updated_at is not None
                else metadata.last_updated_source
            ),
        )


def _execution_completed_at(item: dict[str, Any]) -> datetime | None:
    timings = [timing for timing in item.get("timing", []) if isinstance(timing, dict)]
    execute_timing = next(
        (timing for timing in timings if timing.get("name") == "execute"),
        None,
    )
    if execute_timing:
        completed_at = _parse_datetime(execute_timing.get("completed_at"))
        if completed_at is not None:
            return completed_at
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


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
