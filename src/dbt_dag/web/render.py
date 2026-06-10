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
  <main class="grid h-screen grid-cols-[3fr_1fr]">
    <section class="relative min-w-0 border-r border-zinc-800">
      <div class="absolute left-4 right-4 bottom-4 z-10 flex flex-col items-start gap-2">
        <div id="package-filters" class="flex min-w-0 flex-wrap items-center gap-2 text-xs text-zinc-300"></div>
        <div id="tag-filters" class="flex min-w-0 flex-wrap items-center gap-2 text-xs text-zinc-300"></div>
      </div>
      <div
        id="graph-search-overlay"
        class="pointer-events-none absolute inset-0 z-20 hidden items-start justify-center bg-zinc-950/20 px-4 pt-16"
      >
        <section
          class="pointer-events-auto w-full max-w-2xl overflow-hidden rounded-2xl border border-zinc-700 bg-zinc-900/95 shadow-2xl backdrop-blur"
        >
          <div class="border-b border-zinc-800 px-4 py-3">
            <input
              id="graph-search-input"
              class="w-full bg-transparent text-sm text-zinc-100 outline-none placeholder:text-zinc-500"
              placeholder="Search models, sources, exposures"
              autocomplete="off"
              spellcheck="false"
            >
          </div>
          <div id="graph-search-popup" class="max-h-96 overflow-y-auto p-2"></div>
        </section>
      </div>
      <div id="graph-root" class="h-full w-full overflow-hidden"></div>
    </section>
    <aside id="inspector" class="overflow-auto bg-zinc-900 py-5" hx-get="/inspector/project" hx-trigger="load">
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
