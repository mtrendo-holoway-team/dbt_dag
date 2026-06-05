from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from dbt_dag.shared.time import now_msk


@dataclass(frozen=True)
class NodeStatusIcon:
    icon_name: str
    color_class: str
    color_hex: str


_STATUS_WITHIN_1H = NodeStatusIcon(
    icon_name="check-circle",
    color_class="text-green-500",
    color_hex="#22c55e",
)
_STATUS_WITHIN_3H = NodeStatusIcon(
    icon_name="check-circle",
    color_class="text-cyan-400",
    color_hex="#22d3ee",
)
_STATUS_WITHIN_24H = NodeStatusIcon(
    icon_name="check",
    color_class="text-sky-400",
    color_hex="#38bdf8",
)
_STATUS_WITHIN_48H = NodeStatusIcon(
    icon_name="check",
    color_class="text-amber-400",
    color_hex="#fbbf24",
)
_STATUS_STALE = NodeStatusIcon(
    icon_name="exclamation-triangle",
    color_class="text-red-500",
    color_hex="#ef4444",
)
_STATUS_UNKNOWN = NodeStatusIcon(
    icon_name="x-mark",
    color_class="text-red-700",
    color_hex="#b91c1c",
)


def resolve_node_status_icon(
    last_updated_at: datetime | None,
    reference_time: datetime | None = None,
) -> NodeStatusIcon:
    if last_updated_at is None:
        return _STATUS_UNKNOWN

    current_time = reference_time or now_msk()
    age = current_time - last_updated_at
    if age <= timedelta(hours=1):
        return _STATUS_WITHIN_1H
    if age <= timedelta(hours=3):
        return _STATUS_WITHIN_3H
    if age <= timedelta(hours=24):
        return _STATUS_WITHIN_24H
    if age <= timedelta(hours=48):
        return _STATUS_WITHIN_48H
    return _STATUS_STALE
