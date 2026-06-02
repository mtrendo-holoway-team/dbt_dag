from pathlib import Path
from typing import Any

import yaml

from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.dbt_runtime.types import DbtProjectPaths
from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.dbt_runtime.types import DbtTarget


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _adapter_kind(target_type: str) -> AdapterKind:
    if target_type == AdapterKind.BIGQUERY.value:
        return AdapterKind.BIGQUERY
    if target_type == AdapterKind.CLICKHOUSE.value:
        return AdapterKind.CLICKHOUSE
    return AdapterKind.UNKNOWN


def resolve_profile_name(project_dir: Path) -> str:
    project_config = _load_yaml(project_dir / "dbt_project.yml")
    profile_name = project_config.get("profile")
    if not isinstance(profile_name, str) or not profile_name:
        raise ValueError("dbt_project.yml must define a non-empty profile")
    return profile_name


def resolve_runtime_profile(
    paths: DbtProjectPaths, target_override: str | None
) -> DbtRuntimeProfile:
    profile_name = resolve_profile_name(paths.project_dir)
    profile = _resolve_profile(paths.profiles_dir, profile_name)
    target_name = _resolve_target_name(profile, profile_name, target_override)
    raw_target = _resolve_raw_target(profile, profile_name, target_name)
    target_type = _resolve_target_type(raw_target, target_name)
    target = DbtTarget(name=target_name, target_type=target_type, raw=raw_target)
    return DbtRuntimeProfile(
        profile_name=profile_name,
        target=target,
        adapter_kind=_adapter_kind(target_type),
        paths=paths,
    )


def _resolve_profile(profiles_dir: Path, profile_name: str) -> dict[str, Any]:
    profiles = _load_yaml(profiles_dir / "profiles.yml")
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        raise ValueError(f"profile {profile_name!r} was not found in profiles.yml")
    return profile


def _resolve_target_name(
    profile: dict[str, Any],
    profile_name: str,
    target_override: str | None,
) -> str:
    target_name = target_override or profile.get("target")
    if not isinstance(target_name, str) or not target_name:
        raise ValueError(f"profile {profile_name!r} must define a target")
    return target_name


def _resolve_raw_target(
    profile: dict[str, Any],
    profile_name: str,
    target_name: str,
) -> dict[str, Any]:
    outputs = profile.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError(f"profile {profile_name!r} must define outputs")

    raw_target = outputs.get(target_name)
    if not isinstance(raw_target, dict):
        raise ValueError(f"target {target_name!r} was not found in profile {profile_name!r}")
    return raw_target


def _resolve_target_type(raw_target: dict[str, Any], target_name: str) -> str:
    target_type = raw_target.get("type")
    if not isinstance(target_type, str) or not target_type:
        raise ValueError(f"target {target_name!r} must define type")
    return target_type
