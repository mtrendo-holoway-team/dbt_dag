from pathlib import Path
from typing import Any, cast

from litestar import Controller
from litestar import get
from litestar import post
from litestar import Request
from litestar.enums import MediaType
from litestar.response import Response

from dbt_dag.web.render import render_node_inspector
from dbt_dag.web.render import render_node_tasks
from dbt_dag.web.render import render_page
from dbt_dag.web.render import render_project_inspector
from dbt_dag.web.state import AppState

STATIC_ROOT = Path(__file__).parents[1] / "static"


def _state(request: Request[Any, Any, Any]) -> AppState:
    return cast(AppState, request.app.state["app_state"])


def _html(content: str) -> Response[str]:
    return Response(content=content, media_type=MediaType.HTML)


class PagesController(Controller):
    @get("/")
    async def index(self) -> Response[str]:
        return _html(render_page())

    @get("/api/graph")
    async def graph(self, request: Request[Any, Any, Any]) -> dict[str, Any]:
        return _graph_payload(_state(request).graph_store.snapshot().graph)

    @get("/api/metadata/revision")
    async def metadata_revision(self, request: Request[Any, Any, Any]) -> dict[str, Any]:
        snapshot = _state(request).graph_store.snapshot()
        return {
            "revision": snapshot.revision,
            "refreshed_at": snapshot.refreshed_at.isoformat(),
        }

    @get("/inspector/project")
    async def project_inspector(self, request: Request[Any, Any, Any]) -> Response[str]:
        return _html(render_project_inspector(_state(request).graph_store.snapshot().graph.project))

    @get("/inspector/node/{node_id:str}")
    async def node_inspector(self, request: Request[Any, Any, Any], node_id: str) -> Response[str]:
        state = _state(request)
        snapshot = state.graph_store.snapshot()
        node = snapshot.manifest.graph_nodes()[node_id]
        runtime = snapshot.runtime_metadata.get(node_id)
        tasks = state.task_repository.list_for_node(node_id)
        return _html(render_node_inspector(node, runtime, render_node_tasks(node_id, tasks)))

    @post("/actions/node/{node_id:str}/build", status_code=200)
    async def build_node(self, request: Request[Any, Any, Any], node_id: str) -> Response[str]:
        state = _state(request)
        if node_id not in state.graph_store.snapshot().manifest.graph_nodes():
            return _html(render_node_tasks(node_id, []))
        state.task_runner.start_build(node_id)
        return _html(render_node_tasks(node_id, state.task_repository.list_for_node(node_id)))

    @get("/tasks/node/{node_id:str}")
    async def node_tasks(self, request: Request[Any, Any, Any], node_id: str) -> Response[str]:
        state = _state(request)
        return _html(render_node_tasks(node_id, state.task_repository.list_for_node(node_id)))

    @get("/search")
    async def search(self, request: Request[Any, Any, Any], q: str = "") -> list[dict[str, str]]:
        query = q.removeprefix("/").lower()
        if not query:
            return []
        matches = []
        for node in _state(request).graph_store.snapshot().manifest.graph_nodes().values():
            if query in node.name.lower() or query in node.unique_id.lower():
                matches.append(
                    {"id": node.unique_id, "label": node.name, "type": node.resource_type}
                )
            if len(matches) >= 20:
                break
        return matches

    @get("/static/{file_path:path}")
    async def static_file(self, file_path: str) -> Response[str]:
        static_root = STATIC_ROOT.resolve()
        requested = (static_root / file_path.lstrip("/")).resolve()
        if requested != static_root and static_root not in requested.parents:
            return Response(content="", status_code=404)
        if not requested.exists() or not requested.is_file():
            return Response(content="", status_code=404)
        media_type = MediaType.CSS if requested.suffix == ".css" else "application/javascript"
        return Response(content=requested.read_text(encoding="utf-8"), media_type=media_type)


def _graph_payload(graph: Any) -> dict[str, Any]:
    return {
        "columns": graph.columns,
        "nodes": [
            {
                "id": node.node_id,
                "label": node.label,
                "column": node.column,
                "resource_type": node.resource_type,
                "package_name": node.package_name,
                "description": node.description,
                "indicators": node.indicators,
                "runtime": {
                    "execution_time_seconds": node.runtime.execution_time_seconds,
                    "execution_time_source": node.runtime.execution_time_source.value,
                    "last_updated_at": (
                        node.runtime.last_updated_at.isoformat()
                        if node.runtime.last_updated_at is not None
                        else None
                    ),
                    "last_updated_source": node.runtime.last_updated_source.value,
                    "freshness": node.runtime.freshness.value,
                    "border_width_px": node.runtime.border_width_px,
                    "border_color": node.runtime.border_color,
                },
            }
            for node in graph.nodes
        ],
        "edges": [
            {"id": edge.edge_id, "source": edge.source, "target": edge.target}
            for edge in graph.edges
        ],
        "project": {
            "models_count": graph.project.models_count,
            "sources_count": graph.project.sources_count,
            "tests_count": graph.project.tests_count,
        },
    }
