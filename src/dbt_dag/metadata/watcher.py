from dataclasses import dataclass
import logging
import threading
import time

from dbt_dag.web.graph_state import GraphStateStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _WatcherState:
    artifact_fingerprint: str
    manifest_fingerprint: str
    next_warehouse_refresh: float


class MetadataWatcher:
    def __init__(
        self,
        graph_store: GraphStateStore,
        artifact_poll_seconds: float = 5,
        warehouse_poll_seconds: float = 60,
        stop_join_timeout_seconds: float = 0.1,
    ) -> None:
        self._graph_store = graph_store
        self._artifact_poll_seconds = artifact_poll_seconds
        self._warehouse_poll_seconds = warehouse_poll_seconds
        self._stop_join_timeout_seconds = stop_join_timeout_seconds
        self._stop_event = threading.Event()
        self._refresh_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="metadata-watcher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._refresh_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._stop_join_timeout_seconds)
            if self._thread.is_alive():
                logger.warning("metadata watcher is still running during shutdown")

    def trigger_refresh(self) -> None:
        self._refresh_event.set()

    def _run(self) -> None:
        state = _WatcherState(
            artifact_fingerprint=self._graph_store.artifact_fingerprint(),
            manifest_fingerprint=self._graph_store.manifest_fingerprint(),
            next_warehouse_refresh=time.monotonic(),
        )
        while not self._stop_event.is_set():
            state = self._poll_once(state)

    def _poll_once(self, state: _WatcherState) -> _WatcherState:
        if self._wait_for_next_poll():
            return state

        manifest_fingerprint = self._graph_store.manifest_fingerprint()
        artifact_fingerprint = self._graph_store.artifact_fingerprint()
        include_warehouse = time.monotonic() >= state.next_warehouse_refresh
        if not self._should_refresh(
            manifest_fingerprint,
            artifact_fingerprint,
            state.manifest_fingerprint,
            state.artifact_fingerprint,
            include_warehouse,
        ):
            return state
        if not self._refresh_once(include_warehouse):
            return state
        return _WatcherState(
            artifact_fingerprint=artifact_fingerprint,
            manifest_fingerprint=manifest_fingerprint,
            next_warehouse_refresh=_next_warehouse_refresh(
                state.next_warehouse_refresh,
                self._warehouse_poll_seconds,
                include_warehouse,
            ),
        )

    def _wait_for_next_poll(self) -> bool:
        self._refresh_event.wait(timeout=self._artifact_poll_seconds)
        self._refresh_event.clear()
        return self._stop_event.is_set()

    def _should_refresh(
        self,
        manifest_fingerprint: str,
        artifact_fingerprint: str,
        last_manifest_fingerprint: str,
        last_artifact_fingerprint: str,
        include_warehouse: bool,
    ) -> bool:
        metadata_changed = (
            manifest_fingerprint != last_manifest_fingerprint
            or artifact_fingerprint != last_artifact_fingerprint
        )
        return metadata_changed or include_warehouse

    def _refresh_once(self, include_warehouse: bool) -> bool:
        try:
            self._graph_store.refresh(include_warehouse=include_warehouse)
        except (OSError, RuntimeError, ValueError):
            logger.exception("metadata watcher refresh failed")
            return False
        return True


def _next_warehouse_refresh(
    current_value: float,
    warehouse_poll_seconds: float,
    include_warehouse: bool,
) -> float:
    if include_warehouse:
        return time.monotonic() + warehouse_poll_seconds
    return current_value
