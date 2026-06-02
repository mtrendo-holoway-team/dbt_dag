from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from dbt_dag.dbt_runtime.adapter import create_warehouse_adapter
from dbt_dag.dbt_runtime.profiles import resolve_runtime_profile
from dbt_dag.dbt_runtime.project import resolve_project_paths
from dbt_dag.dbt_runtime.types import AdapterKind
from dbt_dag.settings import Settings


def test_project_discovery_uses_current_dbt_project(
    dbt_project: Path,
    profiles_dir: Path,
    tmp_path: Path,
) -> None:
    settings = Settings(
        app_host="127.0.0.1",
        app_port=5678,
        sqlite_path=tmp_path / "app.sqlite",
        dbt_project_dir=None,
        dbt_profiles_dir=profiles_dir,
        dbt_target=None,
    )

    paths = resolve_project_paths(settings, start_dir=dbt_project / "models")

    assert paths.project_dir == dbt_project
    assert paths.manifest_path == dbt_project / "target" / "manifest.json"
    assert paths.profiles_dir == profiles_dir


def test_profile_resolver_returns_default_target(
    dbt_project: Path,
    profiles_dir: Path,
    tmp_path: Path,
) -> None:
    settings = Settings(
        app_host="127.0.0.1",
        app_port=5678,
        sqlite_path=tmp_path / "app.sqlite",
        dbt_project_dir=dbt_project,
        dbt_profiles_dir=profiles_dir,
        dbt_target=None,
    )
    paths = resolve_project_paths(settings)

    runtime_profile = resolve_runtime_profile(paths, target_override=None)

    assert runtime_profile.profile_name == "demo_profile"
    assert runtime_profile.target.name == "dev"
    assert runtime_profile.adapter_kind == AdapterKind.BIGQUERY


def test_adapter_validation_loads_plugin_before_lookup(
    dbt_project: Path,
    profiles_dir: Path,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    settings = Settings(
        app_host="127.0.0.1",
        app_port=5678,
        sqlite_path=tmp_path / "app.sqlite",
        dbt_project_dir=dbt_project,
        dbt_profiles_dir=profiles_dir,
        dbt_target=None,
    )
    paths = resolve_project_paths(settings)
    runtime_profile = resolve_runtime_profile(paths, target_override=None)
    calls: list[tuple[str, str]] = []

    def fake_load_plugin(name: str) -> None:
        calls.append(("load", name))

    def fake_get_adapter_class_by_name(name: str) -> type[object]:
        calls.append(("lookup", name))
        return object

    monkeypatch.setattr("dbt.adapters.factory.load_plugin", fake_load_plugin)
    monkeypatch.setattr(
        "dbt.adapters.factory.get_adapter_class_by_name",
        fake_get_adapter_class_by_name,
    )

    check = create_warehouse_adapter(runtime_profile).validate_connection()

    assert check.ok is True
    assert calls == [("load", "bigquery"), ("lookup", "bigquery")]
