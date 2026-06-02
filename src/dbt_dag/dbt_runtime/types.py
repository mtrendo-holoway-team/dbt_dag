from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class AdapterKind(StrEnum):
    BIGQUERY = "bigquery"
    CLICKHOUSE = "clickhouse"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DbtProjectPaths:
    project_dir: Path
    manifest_path: Path
    profiles_dir: Path


@dataclass(frozen=True)
class DbtTarget:
    name: str
    target_type: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class DbtRuntimeProfile:
    profile_name: str
    target: DbtTarget
    adapter_kind: AdapterKind
    paths: DbtProjectPaths


@dataclass(frozen=True)
class ConnectionCheck:
    ok: bool
    message: str


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
