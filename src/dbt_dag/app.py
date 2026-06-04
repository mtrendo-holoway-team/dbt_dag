import logging
from time import perf_counter

from litestar import Litestar
from litestar.datastructures import State
import uvicorn

from dbt_dag.logging_config import configure_logging
from dbt_dag.settings import load_settings
from dbt_dag.web.controllers.pages import PagesController
from dbt_dag.web.state import AppState
from dbt_dag.web.state import build_app_state

logger = logging.getLogger(__name__)
STARTUP_TOTAL_STEPS = 9


def create_app() -> Litestar:
    configure_logging()
    progress = StartupProgressReporter(total_steps=STARTUP_TOTAL_STEPS)
    try:
        progress.advance("Loading settings")
        settings = load_settings()
        app_state = build_app_state(settings, progress=progress.advance)
    except Exception:
        progress.fail()
        raise
    progress.finish()
    return Litestar(
        route_handlers=[PagesController],
        state=State({"app_state": app_state}),
        on_startup=[_start_metadata_watcher],
        on_shutdown=[_stop_metadata_watcher],
    )


def run() -> None:
    settings = load_settings()
    uvicorn.run(
        "dbt_dag.app:create_app", host=settings.app_host, port=settings.app_port, factory=True
    )


def _app_state(app: Litestar) -> AppState:
    return app.state["app_state"]  # type: ignore[no-any-return]


def _start_metadata_watcher(app: Litestar) -> None:
    _app_state(app).metadata_watcher.start()


def _stop_metadata_watcher(app: Litestar) -> None:
    _app_state(app).metadata_watcher.stop()


class StartupProgressReporter:
    def __init__(self, total_steps: int) -> None:
        self._total_steps = total_steps
        self._current_step = 0
        self._started_at = perf_counter()
        self._step_started_at = self._started_at
        self._current_message = ""

    def advance(self, message: str) -> None:
        now = perf_counter()
        if self._current_step > 0:
            logger.info(
                "startup %s %d/%d completed %s in %.1fs (%.1fs total)",
                self._render_bar(),
                self._current_step,
                self._total_steps,
                self._current_message,
                now - self._step_started_at,
                now - self._started_at,
            )
        self._current_step = min(self._current_step + 1, self._total_steps)
        self._current_message = message
        self._step_started_at = now
        logger.info(
            "startup %s %d/%d starting %s (%.1fs total)",
            self._render_bar(),
            self._current_step,
            self._total_steps,
            message,
            now - self._started_at,
        )

    def finish(self) -> None:
        now = perf_counter()
        if self._current_step > 0:
            logger.info(
                "startup %s %d/%d completed %s in %.1fs (%.1fs total)",
                self._render_bar(),
                self._current_step,
                self._total_steps,
                self._current_message,
                now - self._step_started_at,
                now - self._started_at,
            )
        logger.info(
            "startup [####################] ready in %.1fs",
            now - self._started_at,
        )

    def fail(self) -> None:
        logger.error(
            "startup %s failed after %.1fs",
            self._render_bar(),
            perf_counter() - self._started_at,
        )

    def _render_bar(self) -> str:
        width = 20
        filled = round(width * (self._current_step / max(self._total_steps, 1)))
        return "[" + "#" * filled + "-" * (width - filled) + "]"
