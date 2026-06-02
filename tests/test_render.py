import json
from pathlib import Path
import pytest

from dbt_dag.web import render


def test_render_page_uses_vite_manifest_assets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "dist" / ".vite" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "src/dbt_dag/web/static/css/tailwind.css": {
                    "file": "assets/styles.css",
                },
                "src/dbt_dag/web/static/js/graph.ts": {
                    "file": "assets/graph.js",
                },
                "src/dbt_dag/web/static/js/search.ts": {
                    "file": "assets/search.js",
                },
                "src/dbt_dag/web/static/js/inspectors.ts": {
                    "file": "assets/inspectors.js",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(render, "VITE_MANIFEST_PATH", manifest_path)

    html = render.render_page()

    assert "/static/dist/assets/graph.js" in html
    assert "/static/dist/assets/search.js" in html
    assert "/static/dist/assets/inspectors.js" in html
    assert "/static/dist/assets/styles.css" in html
    assert "/static/js/graph.ts" not in html
