from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NodeAction(StrEnum):
    BUILD = "build"
    RUN = "run"
    TEST = "test"
    COMPILE = "compile"


class TaskStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class NodeTaskDTO:
    task_id: int
    node_id: str
    command: str
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    exit_code: int | None
    logs_excerpt: str
