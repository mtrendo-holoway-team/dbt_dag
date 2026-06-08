from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ModelTestStatus(StrEnum):
    PASSED = "passed"
    STALE = "stale"
    FAILED = "failed"
    MISSING = "missing"


@dataclass(frozen=True)
class LatestTestRunDTO:
    test_unique_id: str
    model_unique_id: str
    status: str
    executed_at: datetime


@dataclass(frozen=True)
class ModelTestResultDTO:
    test_unique_id: str
    test_name: str
    status: ModelTestStatus
    executed_at: datetime | None


@dataclass(frozen=True)
class ModelTestSummaryDTO:
    model_unique_id: str
    status: ModelTestStatus
    tests: list[ModelTestResultDTO]
