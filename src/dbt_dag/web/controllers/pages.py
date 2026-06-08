from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from litestar import Controller
from litestar import get
from litestar import post
from litestar import Request
from litestar.enums import MediaType
from litestar.response import Response
from litestar.response import Stream
from litestar.response import Template

from dbt_dag.inspectors import actions as actions_inspector
from dbt_dag.inspectors import last_update as last_update_inspector
from dbt_dag.inspectors import NodeInspectorContextFactory
from dbt_dag.inspectors import partition as partition_inspector
from dbt_dag.inspectors import tasks as tasks_inspector
from dbt_dag.inspectors import tests as tests_inspector
from dbt_dag.inspectors.utils import block_id
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.metadata.models import empty_node_runtime_metadata
from dbt_dag.tasks.models import NodeAction
from dbt_dag.web.node_status import resolve_node_status_icon
from dbt_dag.web.render import render_page
from dbt_dag.web.state import AppState

STATIC_ROOT = Path(__file__).parents[1] / "static"
_context_factory = NodeInspectorContextFactory()


def _state(request: Request[Any, Any, Any]) -> AppState:
    return cast(AppState, request.app.state["app_state"])


def _html(content: str) -> Response[str]:
    return Response(content=content, media_type=MediaType.HTML)


@dataclass(frozen=True)
class _SearchFieldMatch:
    positions: list[int]
    score: tuple[int, int, int]


@dataclass(frozen=True)
class _SearchCandidate:
    node_id: str
    label: str
    resource_type: str
    subtitle: str
    label_matches: list[int]
    type_matches: list[int]
    subtitle_matches: list[int]
    score: tuple[int, int, int, str]


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
    async def project_inspector(self, request: Request[Any, Any, Any]) -> Template:
        return Template(
            template_name="inspectors/project.html",
            context={"project": _state(request).graph_store.snapshot().graph.project},
        )

    @get("/inspector/node/{node_id:str}")
    async def node_inspector(
        self,
        request: Request[Any, Any, Any],
        node_id: str,
        selection_token: str = "initial",
    ) -> Template:
        state = _state(request)
        snapshot = state.graph_store.snapshot()
        node = snapshot.manifest.graph_nodes()[node_id]
        runtime_metadata = snapshot.runtime_metadata.get(node_id, empty_node_runtime_metadata())
        return Template(
            template_name="inspectors/shell.html",
            context={
                "node": node,
                "status_icon": resolve_node_status_icon(
                    runtime_metadata.last_updated_at,
                    reference_time=snapshot.refreshed_at,
                ),
                "selection_token": selection_token,
                "last_update_block_id": block_id("last-update", selection_token),
                "tests_block_id": block_id("tests", selection_token),
                "partition_block_id": block_id("partition", selection_token),
                "actions_block_id": block_id("actions", selection_token),
                "tasks_block_id": block_id("tasks", selection_token),
            },
        )

    @get("/inspector/node/{node_id:str}/last-update")
    async def node_last_update_inspector(
        self,
        request: Request[Any, Any, Any],
        node_id: str,
        selection_token: str = "initial",
    ) -> Template:
        inspector = _context_factory.build(_state(request), node_id, selection_token)
        return Template(
            template_name=last_update_inspector.TEMPLATE_NAME,
            context=last_update_inspector.build_template_context(inspector),
        )

    @get("/inspector/node/{node_id:str}/partition")
    async def node_partition_inspector(
        self,
        request: Request[Any, Any, Any],
        node_id: str,
        selection_token: str = "initial",
    ) -> Template:
        inspector = _context_factory.build(
            _state(request),
            node_id,
            selection_token,
            include_partition_calendar=True,
        )
        return Template(
            template_name=partition_inspector.TEMPLATE_NAME,
            context=partition_inspector.build_template_context(inspector),
        )

    @get("/inspector/node/{node_id:str}/tests")
    async def node_tests_inspector(
        self,
        request: Request[Any, Any, Any],
        node_id: str,
        selection_token: str = "initial",
        include_warehouse: bool = False,
    ) -> Template:
        inspector = _context_factory.build(
            _state(request),
            node_id,
            selection_token,
            include_tests=True,
            include_test_warehouse=include_warehouse,
        )
        return Template(
            template_name=tests_inspector.TEMPLATE_NAME,
            context=tests_inspector.build_template_context(inspector),
        )

    @get("/inspector/node/{node_id:str}/actions")
    async def node_actions_inspector(
        self,
        request: Request[Any, Any, Any],
        node_id: str,
        selection_token: str = "initial",
    ) -> Template:
        inspector = _context_factory.build(_state(request), node_id, selection_token)
        return Template(
            template_name=actions_inspector.TEMPLATE_NAME,
            context=actions_inspector.build_template_context(inspector),
        )

    @post("/actions/node/{node_id:str}/execute/{action_name:str}", status_code=200)
    async def execute_node_action(
        self,
        request: Request[Any, Any, Any],
        node_id: str,
        action_name: str,
    ) -> Response[str] | Stream:
        state = _state(request)
        node = _model_node_for_action(state, node_id)
        if node is None:
            return Response(content="", media_type="text/plain", status_code=404)
        action = _parse_action(action_name)
        if action is None or not state.task_runner.supports_action(node, action):
            return Response(content="", media_type="text/plain", status_code=400)
        return Stream(
            state.task_runner.stream_action(node, action),
            media_type="application/x-ndjson",
        )

    @post("/actions/node/{node_id:str}/refresh-partitions", status_code=200)
    async def refresh_node_partitions(
        self,
        request: Request[Any, Any, Any],
        node_id: str,
        selection_token: str = "initial",
    ) -> Response[str] | Template:
        state = _state(request)
        snapshot = state.graph_store.snapshot()
        node = snapshot.manifest.graph_nodes().get(node_id)
        if node is None:
            return Response(content="", media_type=MediaType.HTML, status_code=404)
        state.partition_runner.start_refresh(node_id)
        inspector = _context_factory.build(
            state,
            node_id,
            selection_token,
            include_partition_calendar=True,
        )
        return Template(
            template_name=partition_inspector.TEMPLATE_NAME,
            context=partition_inspector.build_template_context(inspector),
        )

    @get("/inspector/node/{node_id:str}/tasks")
    async def node_tasks(
        self,
        request: Request[Any, Any, Any],
        node_id: str,
        selection_token: str = "initial",
    ) -> Template:
        inspector = _context_factory.build(
            _state(request),
            node_id,
            selection_token,
            include_tasks=True,
        )
        return Template(
            template_name=tasks_inspector.TEMPLATE_NAME,
            context=tasks_inspector.build_template_context(inspector),
        )

    @get("/search")
    async def search(self, request: Request[Any, Any, Any], q: str = "") -> list[dict[str, Any]]:
        query = q.removeprefix("/").lower()
        if not query:
            return []
        matches: list[_SearchCandidate] = []
        for node in _state(request).graph_store.snapshot().manifest.graph_nodes().values():
            candidate = _build_search_candidate(node, query)
            if candidate is not None:
                matches.append(candidate)
        matches.sort(key=lambda candidate: candidate.score)
        return [
            {
                "id": candidate.node_id,
                "label": candidate.label,
                "type": candidate.resource_type,
                "subtitle": candidate.subtitle,
                "label_matches": candidate.label_matches,
                "type_matches": candidate.type_matches,
                "subtitle_matches": candidate.subtitle_matches,
            }
            for candidate in matches[:20]
        ]

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
                "type_badge": node.type_badge,
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
                "test_indicator": {
                    "status": node.test_indicator.status.value,
                },
            }
            for node in graph.nodes
        ],
        "edges": [
            {"id": edge.edge_id, "source": edge.source, "target": edge.target}
            for edge in graph.edges
        ],
        "groups": [
            {"id": group.group_id, "label": group.label, "node_ids": group.node_ids}
            for group in graph.groups
        ],
        "project": {
            "models_count": graph.project.models_count,
            "sources_count": graph.project.sources_count,
            "tests_count": graph.project.tests_count,
        },
    }


def _build_search_candidate(node: DbtManifestNode, query: str) -> _SearchCandidate | None:
    label_match = _match_search_field(query, node.name)
    type_match = _match_search_field(query, node.resource_type)
    subtitle_match = _match_search_field(query, node.unique_id)
    field_matches = [
        match for match in [label_match, type_match, subtitle_match] if match is not None
    ]
    if not field_matches:
        return None
    best_match = min(field_matches, key=lambda match: match.score)
    return _SearchCandidate(
        node_id=node.unique_id,
        label=node.name,
        resource_type=node.resource_type,
        subtitle=node.unique_id,
        label_matches=label_match.positions if label_match is not None else [],
        type_matches=type_match.positions if type_match is not None else [],
        subtitle_matches=subtitle_match.positions if subtitle_match is not None else [],
        score=(*best_match.score, node.unique_id),
    )


def _match_search_field(query: str, value: str) -> _SearchFieldMatch | None:
    normalized = value.lower()
    substring_index = normalized.find(query)
    if substring_index >= 0:
        positions = list(range(substring_index, substring_index + len(query)))
        return _SearchFieldMatch(
            positions=positions,
            score=(0, substring_index, len(value)),
        )
    subsequence_positions = _subsequence_positions(query, normalized)
    if subsequence_positions is None:
        return None
    spread = subsequence_positions[-1] - subsequence_positions[0]
    return _SearchFieldMatch(positions=subsequence_positions, score=(1, spread, len(value)))


def _subsequence_positions(query: str, value: str) -> list[int] | None:
    positions: list[int] = []
    cursor = 0
    for character in query:
        index = value.find(character, cursor)
        if index < 0:
            return None
        positions.append(index)
        cursor = index + 1
    return positions


def _model_node_for_action(state: AppState, node_id: str) -> DbtManifestNode | None:
    node = state.graph_store.snapshot().manifest.graph_nodes().get(node_id)
    if node is None or node.resource_type != "model":
        return None
    return node


def _parse_action(action_name: str) -> NodeAction | None:
    try:
        return NodeAction(action_name)
    except ValueError:
        return None
