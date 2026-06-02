from litestar import Litestar
from litestar.datastructures import State
import uvicorn

from dbt_dag.logging_config import configure_logging
from dbt_dag.settings import load_settings
from dbt_dag.web.controllers.pages import PagesController
from dbt_dag.web.state import build_app_state


def create_app() -> Litestar:
    configure_logging()
    settings = load_settings()
    app_state = build_app_state(settings)
    return Litestar(route_handlers=[PagesController], state=State({"app_state": app_state}))


def run() -> None:
    settings = load_settings()
    uvicorn.run(
        "dbt_dag.app:create_app", host=settings.app_host, port=settings.app_port, factory=True
    )
