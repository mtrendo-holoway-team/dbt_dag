from pathlib import Path
import pytest
from unittest.mock import Mock

from litestar import Litestar
from litestar.datastructures import State
from litestar.testing import TestClient

from dbt_dag.db.session import create_db_engine
from dbt_dag.db.session import create_session_factory
from dbt_dag.db.session import init_db
from dbt_dag.graph.builder import build_graph
from dbt_dag.manifest.parser import load_manifest
from dbt_dag.settings import Settings
from dbt_dag.tasks.repository import NodeTaskRepository
from dbt_dag.web.controllers import pages
from dbt_dag.web.controllers.pages import PagesController
from dbt_dag.web.state import AppState


def test_graph_endpoint_returns_documented_shape(dbt_project: Path, tmp_path: Path) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/api/graph")

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["models_count"] == 2
    assert body["project"]["sources_count"] == 1
    assert body["project"]["tests_count"] == 1
    assert len(body["nodes"]) == 3
    assert {node["package_name"] for node in body["nodes"]} == {"demo"}


def test_node_inspector_returns_name_and_description(dbt_project: Path, tmp_path: Path) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.get("/inspector/node/model.demo.stg_orders")

    assert response.status_code == 200
    assert "stg_orders" in response.text
    assert "Staged orders" in response.text


def test_build_action_creates_task(dbt_project: Path, tmp_path: Path) -> None:
    client = _client(dbt_project, tmp_path)

    response = client.post("/actions/node/model.demo.stg_orders/build")

    assert response.status_code == 200
    assert "dbt build --select model.demo.stg_orders" in response.text


def test_static_file_serves_built_assets(
    dbt_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    static_root = tmp_path / "static"
    asset_path = static_root / "dist" / "assets" / "graph.js"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_text("function graph() {}", encoding="utf-8")
    monkeypatch.setattr(pages, "STATIC_ROOT", static_root)
    client = _client(dbt_project, tmp_path)

    response = client.get("/static/dist/assets/graph.js")

    assert response.status_code == 200
    assert "function" in response.text


def _client(dbt_project: Path, tmp_path: Path) -> TestClient[Litestar]:
    manifest = load_manifest(dbt_project / "target" / "manifest.json")
    engine = create_db_engine(tmp_path / "app.sqlite")
    init_db(engine)
    repository = NodeTaskRepository(create_session_factory(engine))
    task_runner = Mock()
    task_runner.start_build.side_effect = lambda node_id: repository.create(
        node_id, f"dbt build --select {node_id}"
    )
    state = AppState(
        settings=Settings(
            app_host="127.0.0.1",
            app_port=5678,
            sqlite_path=tmp_path / "app.sqlite",
            dbt_project_dir=dbt_project,
            dbt_profiles_dir=None,
            dbt_target=None,
        ),
        manifest=manifest,
        graph=build_graph(manifest),
        task_repository=repository,
        task_runner=task_runner,
    )
    return TestClient(Litestar(route_handlers=[PagesController], state=State({"app_state": state})))
