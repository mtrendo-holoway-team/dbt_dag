from typing import Any

from dbt_dag.inspectors.dto import NodeInspectorContextDTO
from dbt_dag.inspectors.utils import block_id
from dbt_dag.tasks.models import NodeAction

TEMPLATE_NAME = "inspectors/blocks/actions.html"


def build_template_context(inspector: NodeInspectorContextDTO) -> dict[str, Any]:
    return {
        "inspector": inspector,
        "block_id": block_id("actions", inspector.selection_token),
        "tasks_block_id": block_id("tasks", inspector.selection_token),
        "actions": _build_actions(inspector),
    }


def _build_actions(inspector: NodeInspectorContextDTO) -> list[dict[str, str]]:
    if inspector.node.resource_type != "model":
        return []
    return [
        _action(inspector, NodeAction.BUILD, "Build", "ab", "play-circle"),
        _action(inspector, NodeAction.RUN, "Run", "ar", "play"),
        _action(inspector, NodeAction.TEST, "Test", "at", "check-circle"),
        _action(inspector, NodeAction.COMPILE, "Compile", "ac", "clipboard-document"),
    ]


def _action(
    inspector: NodeInspectorContextDTO,
    action: NodeAction,
    label: str,
    shortcut: str,
    icon: str,
) -> dict[str, str]:
    return {
        "action": action.value,
        "icon": icon,
        "label": label,
        "shortcut": shortcut,
        "url": f"/actions/node/{inspector.node.unique_id}/execute/{action.value}",
    }
