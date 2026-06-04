from typing import Any

from dbt_dag.inspectors.dto import NodeInspectorContextDTO
from dbt_dag.inspectors.utils import block_id

TEMPLATE_NAME = "inspectors/blocks/actions.html"


def build_template_context(inspector: NodeInspectorContextDTO) -> dict[str, Any]:
    return {
        "inspector": inspector,
        "block_id": block_id("actions", inspector.selection_token),
        "tasks_block_id": block_id("tasks", inspector.selection_token),
    }
