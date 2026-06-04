from pathlib import Path

from litestar.plugins.jinja import JinjaTemplateEngine
from litestar.template.config import TemplateConfig

TEMPLATES_DIRECTORY = Path(__file__).parent / "templates"


def create_template_config() -> TemplateConfig[JinjaTemplateEngine]:
    return TemplateConfig(
        engine=JinjaTemplateEngine,
        directory=TEMPLATES_DIRECTORY,
    )
