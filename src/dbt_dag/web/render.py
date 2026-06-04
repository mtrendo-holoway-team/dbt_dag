import json
from pathlib import Path
from typing import Any

STATIC_ROOT = Path(__file__).parent / "static"
VITE_MANIFEST_PATH = STATIC_ROOT / "dist" / ".vite" / "manifest.json"

_SCRIPT_ENTRIES = [
    "src/dbt_dag/web/static/js/graph.ts",
    "src/dbt_dag/web/static/js/search.ts",
    "src/dbt_dag/web/static/js/inspectors.ts",
]
_STYLE_ENTRY = "src/dbt_dag/web/static/css/tailwind.css"


def render_page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>dbt DAG Visualizer</title>
  {_render_asset_tags()}
</head>
<body class="h-screen overflow-hidden bg-zinc-950 text-zinc-100">
  <main class="grid h-screen grid-cols-[1fr_360px]">
    <section class="relative min-w-0 border-r border-zinc-800">
      <div class="absolute left-4 right-4 top-4 z-10 flex flex-wrap items-center gap-2">
        <input id="graph-search" class="w-80 rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-cyan-500" placeholder="/ search">
        <button class="btn" data-filter="upstream">Upstream</button>
        <button class="btn" data-filter="downstream">Downstream</button>
        <button class="btn" data-filter="reset">Reset</button>
        <div id="package-filters" class="flex min-w-0 flex-wrap items-center gap-2 text-xs text-zinc-300"></div>
      </div>
      <div id="search-popup" class="absolute left-4 top-28 z-20 hidden w-80 rounded border border-zinc-700 bg-zinc-900 shadow-xl"></div>
      <div id="graph-root" class="h-full w-full overflow-hidden"></div>
    </section>
    <aside id="inspector" class="overflow-auto bg-zinc-900 p-5" hx-get="/inspector/project" hx-trigger="load">
    </aside>
  </main>
</body>
</html>
"""


def _render_asset_tags() -> str:
    manifest = _load_vite_manifest()
    if not manifest:
        return """
  <script type="module" src="/static/js/graph.ts"></script>
  <script type="module" src="/static/js/search.ts"></script>
  <script type="module" src="/static/js/inspectors.ts"></script>
  <link rel="stylesheet" href="/static/css/tailwind.css">""".strip()

    scripts = "\n  ".join(
        f'<script type="module" src="{_static_dist_url(manifest[entry]["file"])}"></script>'
        for entry in _SCRIPT_ENTRIES
        if entry in manifest and "file" in manifest[entry]
    )
    style = ""
    if _STYLE_ENTRY in manifest and "file" in manifest[_STYLE_ENTRY]:
        style = f'<link rel="stylesheet" href="{_static_dist_url(manifest[_STYLE_ENTRY]["file"])}">'
    return "\n  ".join(tag for tag in [scripts, style] if tag)


def _load_vite_manifest() -> dict[str, dict[str, Any]]:
    if not VITE_MANIFEST_PATH.exists():
        return {}
    with VITE_MANIFEST_PATH.open(encoding="utf-8") as file:
        manifest = json.load(file)
    if not isinstance(manifest, dict):
        return {}
    return {str(entry): value for entry, value in manifest.items() if isinstance(value, dict)}


def _static_dist_url(file_path: Any) -> str:
    return f"/static/dist/{str(file_path)}"
