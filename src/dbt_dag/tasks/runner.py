from collections.abc import Iterator
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import subprocess
from typing import Callable

from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.tasks.models import NodeAction
from dbt_dag.tasks.repository import NodeTaskRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _FinishedAction:
    exit_code: int
    compiled_sql: str | None


class DbtTaskRunner:
    def __init__(
        self,
        repository: NodeTaskRepository,
        runtime_profile: DbtRuntimeProfile,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._runtime_profile = runtime_profile
        self._on_finished = on_finished

    def supports_action(self, node: DbtManifestNode, action: NodeAction) -> bool:
        return node.resource_type == "model"

    def stream_action(self, node: DbtManifestNode, action: NodeAction) -> Iterator[str]:
        command = self._build_command(node, action)
        task = self._repository.create(node_id=node.unique_id, command=" ".join(command))
        self._repository.mark_running(task.task_id)
        yield self._encode_event(
            "start",
            action=action.value,
            command=task.command,
            task_id=task.task_id,
        )

        log_chunks: list[str] = []
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=self._runtime_profile.paths.project_dir,
            )
        except OSError as exc:
            logger.exception("dbt command failed to start")
            message = str(exc)
            self._repository.mark_finished(task.task_id, exit_code=127, logs_excerpt=message)
            yield self._encode_event("error", message=message)
            yield self._encode_event(
                "finish",
                action=action.value,
                exit_code=127,
                ok=False,
                task_id=task.task_id,
            )
            return

        if process.stdout is not None:
            for line in process.stdout:
                log_chunks.append(line)
                yield self._encode_event("chunk", text=line)

        exit_code = process.wait()
        logs_excerpt = "".join(log_chunks).strip()
        compiled_sql = self._resolve_compiled_sql(node) if action == NodeAction.COMPILE else None
        self._repository.mark_finished(task.task_id, exit_code=exit_code, logs_excerpt=logs_excerpt)

        if exit_code == 0 and action != NodeAction.COMPILE and self._on_finished is not None:
            self._on_finished()

        finished = _FinishedAction(exit_code=exit_code, compiled_sql=compiled_sql)
        yield self._encode_event(
            "finish",
            action=action.value,
            exit_code=finished.exit_code,
            ok=finished.exit_code == 0,
            task_id=task.task_id,
            compiled_sql=finished.compiled_sql,
        )

    def _build_command(self, node: DbtManifestNode, action: NodeAction) -> list[str]:
        return [
            "dbt",
            action.value,
            "--select",
            node.name,
            "--profiles-dir",
            str(self._runtime_profile.paths.profiles_dir),
        ]

    def _resolve_compiled_sql(self, node: DbtManifestNode) -> str | None:
        compiled_path = self._compiled_path_from_manifest(node)
        if compiled_path is not None and compiled_path.exists():
            return compiled_path.read_text(encoding="utf-8")

        fallback_path = self._find_compiled_sql_path(node.path)
        if fallback_path is None:
            return None
        return fallback_path.read_text(encoding="utf-8")

    def _compiled_path_from_manifest(self, node: DbtManifestNode) -> Path | None:
        compiled_path = node.raw.get("compiled_path")
        if not isinstance(compiled_path, str) or not compiled_path:
            return None
        path = Path(compiled_path)
        return path if path.is_absolute() else self._runtime_profile.paths.project_dir / path

    def _find_compiled_sql_path(self, node_path: str) -> Path | None:
        compiled_root = self._runtime_profile.paths.project_dir / "target" / "compiled"
        if not compiled_root.exists():
            return None
        matches = list(compiled_root.glob(f"*/{node_path}"))
        if not matches:
            return None
        return matches[0]

    def _encode_event(self, event: str, **payload: object) -> str:
        body = {"event": event, **payload}
        return json.dumps(body) + "\n"
