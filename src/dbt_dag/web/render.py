from html import escape

from dbt_dag.graph.models import ProjectSummary
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.tasks.models import NodeTaskDTO


def render_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>dbt DAG Visualizer</title>
  <script type="module" src="/static/js/graph.ts"></script>
  <script type="module" src="/static/js/search.ts"></script>
  <script type="module" src="/static/js/inspectors.ts"></script>
  <link rel="stylesheet" href="/static/css/tailwind.css">
</head>
<body class="h-screen overflow-hidden bg-zinc-950 text-zinc-100">
  <main class="grid h-screen grid-cols-[1fr_360px]">
    <section class="relative min-w-0 border-r border-zinc-800">
      <div class="absolute left-4 top-4 z-10 flex items-center gap-2">
        <input id="graph-search" class="w-80 rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-cyan-500" placeholder="/ search">
        <button class="btn" data-filter="upstream">Upstream</button>
        <button class="btn" data-filter="downstream">Downstream</button>
        <button class="btn" data-filter="reset">Reset</button>
      </div>
      <div id="search-popup" class="absolute left-4 top-16 z-20 hidden w-80 rounded border border-zinc-700 bg-zinc-900 shadow-xl"></div>
      <div id="graph-root" class="h-full w-full"></div>
    </section>
    <aside id="inspector" class="overflow-auto bg-zinc-900 p-5" hx-get="/inspector/project" hx-trigger="load">
    </aside>
  </main>
</body>
</html>
"""


def render_project_inspector(project: ProjectSummary) -> str:
    return f"""
<section class="space-y-5">
  <header>
    <h1 class="text-lg font-semibold">Project</h1>
    <p class="text-sm text-zinc-400">Current dbt manifest summary</p>
  </header>
  <dl class="grid grid-cols-3 gap-3">
    <div class="rounded border border-zinc-800 p-3">
      <dt class="text-xs text-zinc-500">Models</dt>
      <dd class="text-xl font-semibold">{project.models_count}</dd>
    </div>
    <div class="rounded border border-zinc-800 p-3">
      <dt class="text-xs text-zinc-500">Sources</dt>
      <dd class="text-xl font-semibold">{project.sources_count}</dd>
    </div>
    <div class="rounded border border-zinc-800 p-3">
      <dt class="text-xs text-zinc-500">Tests</dt>
      <dd class="text-xl font-semibold">{project.tests_count}</dd>
    </div>
  </dl>
</section>
"""


def render_node_inspector(node: DbtManifestNode, tasks_html: str) -> str:
    return f"""
<section class="space-y-5">
  <header>
    <p class="text-xs uppercase tracking-wide text-cyan-400">{escape(node.resource_type)}</p>
    <h1 class="text-lg font-semibold">{escape(node.name)}</h1>
    <p class="break-all text-xs text-zinc-500">{escape(node.unique_id)}</p>
  </header>
  <section class="space-y-2">
    <h2 class="text-sm font-medium">Description</h2>
    <p class="text-sm leading-6 text-zinc-300">{escape(node.description or "No description.")}</p>
  </section>
  <section class="space-y-3">
    <h2 class="text-sm font-medium">Actions</h2>
    <button class="btn" hx-post="/actions/node/{escape(node.unique_id)}/build" hx-target="#node-tasks" hx-swap="outerHTML">Run build</button>
  </section>
  {tasks_html}
</section>
"""


def render_tasks(tasks: list[NodeTaskDTO]) -> str:
    items = "\n".join(_render_task(task) for task in tasks)
    if not items:
        items = '<p class="text-sm text-zinc-500">No tasks yet.</p>'
    return f"""
<section id="node-tasks" class="space-y-3" hx-get="/tasks/node/{{node_id}}" hx-trigger="every 3s">
  <h2 class="text-sm font-medium">Tasks</h2>
  <div class="space-y-2">{items}</div>
</section>
"""


def render_node_tasks(node_id: str, tasks: list[NodeTaskDTO]) -> str:
    return render_tasks(tasks).replace("/tasks/node/{node_id}", f"/tasks/node/{escape(node_id)}")


def _render_task(task: NodeTaskDTO) -> str:
    return f"""
<article class="rounded border border-zinc-800 p-3 text-sm">
  <div class="flex items-center justify-between gap-3">
    <span class="font-medium">{escape(task.status.value)}</span>
    <span class="text-xs text-zinc-500">#{task.task_id}</span>
  </div>
  <p class="mt-2 break-all text-xs text-zinc-400">{escape(task.command)}</p>
</article>
"""
