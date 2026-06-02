import logging
import subprocess
import threading

from dbt_dag.dbt_runtime.types import DbtRuntimeProfile
from dbt_dag.tasks.models import NodeTaskDTO
from dbt_dag.tasks.repository import NodeTaskRepository

logger = logging.getLogger(__name__)


class DbtTaskRunner:
    def __init__(self, repository: NodeTaskRepository, runtime_profile: DbtRuntimeProfile) -> None:
        self._repository = repository
        self._runtime_profile = runtime_profile

    def start_build(self, node_id: str) -> NodeTaskDTO:
        command = [
            "dbt",
            "build",
            "--select",
            node_id,
            "--project-dir",
            str(self._runtime_profile.paths.project_dir),
            "--profiles-dir",
            str(self._runtime_profile.paths.profiles_dir),
            "--target",
            self._runtime_profile.target.name,
        ]
        task = self._repository.create(node_id=node_id, command=" ".join(command))
        thread = threading.Thread(
            target=self._run_command,
            args=(task.task_id, command),
            name=f"dbt-task-{task.task_id}",
            daemon=True,
        )
        thread.start()
        return task

    def _run_command(self, task_id: int, command: list[str]) -> None:
        self._repository.mark_running(task_id)
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                cwd=self._runtime_profile.paths.project_dir,
            )
        except OSError as exc:
            logger.exception("dbt command failed to start")
            self._repository.mark_finished(task_id, exit_code=127, logs_excerpt=str(exc))
            return

        logs = "\n".join([completed.stdout, completed.stderr]).strip()
        self._repository.mark_finished(task_id, exit_code=completed.returncode, logs_excerpt=logs)
