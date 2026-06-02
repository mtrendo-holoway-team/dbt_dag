from pathlib import Path
import pytest
from typing import Any

import yaml


@pytest.fixture
def dbt_project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "project"
    target_dir = project_dir / "target"
    target_dir.mkdir(parents=True)
    (project_dir / "dbt_project.yml").write_text(
        yaml.safe_dump({"name": "demo", "profile": "demo_profile"}),
        encoding="utf-8",
    )
    (target_dir / "manifest.json").write_text(
        _manifest_json(),
        encoding="utf-8",
    )
    return project_dir


@pytest.fixture
def profiles_dir(tmp_path: Path) -> Path:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "profiles.yml").write_text(
        yaml.safe_dump(
            {
                "demo_profile": {
                    "target": "dev",
                    "outputs": {
                        "dev": {
                            "type": "bigquery",
                            "method": "oauth",
                            "project": "demo",
                            "dataset": "analytics",
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    return profiles


def _manifest_json() -> str:
    manifest: dict[str, Any] = {
        "nodes": {
            "model.demo.stg_orders": {
                "unique_id": "model.demo.stg_orders",
                "name": "stg_orders",
                "resource_type": "model",
                "description": "Staged orders",
                "depends_on": {"nodes": ["source.demo.raw.orders"]},
                "package_name": "demo",
                "path": "models/stg/stg_orders.sql",
                "fqn": ["demo", "stg", "stg_orders"],
            },
            "model.demo.fct_orders": {
                "unique_id": "model.demo.fct_orders",
                "name": "fct_orders",
                "resource_type": "model",
                "description": "Order fact table",
                "depends_on": {"nodes": ["model.demo.stg_orders"]},
                "package_name": "demo",
                "path": "models/marts/fct_orders.sql",
                "fqn": ["demo", "marts", "fct_orders"],
            },
            "test.demo.not_null_orders_id": {
                "unique_id": "test.demo.not_null_orders_id",
                "name": "not_null_orders_id",
                "resource_type": "test",
                "description": "",
                "depends_on": {"nodes": ["model.demo.fct_orders"]},
                "package_name": "demo",
                "path": "models/schema.yml",
                "fqn": ["demo", "marts", "not_null_orders_id"],
            },
        },
        "sources": {
            "source.demo.raw.orders": {
                "unique_id": "source.demo.raw.orders",
                "name": "orders",
                "resource_type": "source",
                "description": "Raw orders",
                "depends_on": {"nodes": []},
                "package_name": "demo",
                "path": "models/sources.yml",
                "fqn": ["demo", "raw", "orders"],
            }
        },
        "exposures": {},
    }
    import json

    return json.dumps(manifest)
