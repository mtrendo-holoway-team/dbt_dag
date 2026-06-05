# Decisions

## ADR-0001 Local Litestar Server

- Created: 2026-06-02
- Status: active
- Context: The visualizer is a local developer tool.
- Decision: Run a Litestar service without authorization on port `5678`.
- Consequences: Security controls are out of scope for v1; the app must not be exposed as a public service by default.

## ADR-0002 Python Tooling

- Created: 2026-06-02
- Status: active
- Context: The project needs repeatable Python dependencies and quality commands.
- Decision: Use Poetry for Python dependency and script management.
- Consequences: Local commands are documented through `poetry run`.

## ADR-0003 Frontend Tooling

- Created: 2026-06-02
- Status: active
- Context: Sigma.js, Graphology, htmx, and Tailwind 4 need a small asset pipeline.
- Decision: Use Vite for frontend builds.
- Consequences: Static source assets live under `src/dbt_dag/web/static`; built assets go to `static/dist`.

## ADR-0004 Local Persistence

- Created: 2026-06-02
- Status: active
- Context: The app needs local task and source-state persistence.
- Decision: Use SQLite with SQLAlchemy and Alembic.
- Consequences: Alembic revisions must use short identifiers, no longer than 32 characters.

## ADR-0005 dbt Project Discovery

- Created: 2026-06-02
- Status: superseded
- Superseded by: ADR-0012
- Context: The visualizer should work from inside a dbt project without extra setup.
- Decision: Search current directory and parents for `dbt_project.yml`; use `.env` fallback values only when needed.
- Consequences: `.env` may define dbt paths but not warehouse credentials.

## ADR-0006 Adapter Roadmap

- Created: 2026-06-02
- Status: active
- Context: BigQuery is needed first, ClickHouse later.
- Decision: Implement BigQuery-ready behavior first and keep ClickHouse behind the same adapter protocol.
- Consequences: ClickHouse-specific implementation is out of scope for v1.

## ADR-0007 Node Build Action

- Created: 2026-06-02
- Status: active
- Context: The first node action must be useful, not a UI stub.
- Decision: Run real `dbt build --select <node>` subprocesses.
- Consequences: Task status must be persisted and exposed to the node inspector.

## ADR-0008 Test Run Ingestion

- Created: 2026-06-02
- Status: active
- Context: `stg__dbt_test_runs` will enrich indicators later.
- Decision: Architect ingestion through warehouse adapters but do not implement full ingestion in the baseline visualizer.
- Consequences: v1 graph and inspectors rely on `manifest.json`.

## ADR-0009 dbt Profile Source Of Truth

- Created: 2026-06-02
- Status: active
- Context: dbt already defines warehouse connection settings in `profiles.yml`.
- Decision: Use dbt profile and active target as the source of truth for warehouse connection settings.
- Consequences: The app must not duplicate BigQuery or ClickHouse credentials in `.env`.

## ADR-0010 dbt Adapter Isolation

- Created: 2026-06-02
- Status: active
- Context: dbt adapter internals can change across versions.
- Decision: Isolate direct dbt adapter internals behind `src/dbt_dag/dbt_runtime`.
- Consequences: Other modules must not import `dbt.adapters.*` directly.

## ADR-0011 Adapter Protocol Boundary

- Created: 2026-06-02
- Status: active
- Context: App behavior should not depend directly on dbt adapter classes.
- Decision: Application modules depend on `WarehouseAdapterProtocol`.
- Consequences: BigQuery and ClickHouse implementations expose the same application-level contract.

## ADR-0012 dbt Project Directory Manifest Resolution

- Created: 2026-06-02
- Status: active
- Supersedes: ADR-0005
- Context: Configuring concrete generated artifact paths in `.env` makes local setup more brittle.
- Decision: Configure only the dbt project directory in `.env`; derive manifest path as `target/manifest.json` under that project.
- Consequences: The app no longer supports `DBT_MANIFEST_PATH`; custom manifest locations require a future documented decision.

## ADR-0013 ELK DAG Layout Engine

- Created: 2026-06-03
- Status: superseded
- Superseded_by: ADR-0018
- Context: The DAG view needs stable left-to-right dependency layout, labeled rectangular nodes, and fewer edge crossings than the Sigma force-style renderer provides.
- Decision: Use ELK.js layered layout to order DAG nodes, then render the result with first-party SVG and HTML.
- Consequences: Frontend graph rendering depends on `elkjs`; the backend graph payload remains the source of node and edge data, and visual swimlanes are derived in the browser.

## ADR-0014 Runtime Metadata Refresh

- Created: 2026-06-03
- Status: active
- Context: Node styling and inspectors need execution duration and table update metadata that may change after the initial page load.
- Decision: Keep runtime metadata in a centralized thread-safe graph state store, refresh it in a daemon watcher, and prefer warehouse metadata over local dbt artifacts.
- Consequences: Graph and inspector endpoints read a consistent snapshot; frontend clients poll a lightweight revision endpoint and reload graph data only when the revision changes.

## ADR-0015 Local Partition Snapshot Cache

- Created: 2026-06-04
- Status: active
- Context: Partition row-count calendars need warehouse data from `stg__dbt_run_partition_info`, but querying BigQuery on every inspector repaint would be slower and less stable than serving a local snapshot.
- Decision: Keep one current partition snapshot per model in SQLite, refresh it in background threads, and treat the local cache as stale when its newest warehouse `inserted_at` is older than the model update time from runtime metadata or `stg__dbt_run_results`.
- Consequences: BigQuery model inspectors can render immediately from local state, stale calendars trigger background sync, and manual refresh uses the same replacement-based cache flow instead of storing snapshot history.

## ADR-0016 Inspector Shell And HTMX Blocks

- Created: 2026-06-04
- Status: active
- Context: The inspector sidebar had grown into a single server-rendered HTML string, and switching nodes could stall the sidebar while one response assembled every section.
- Decision: Render a fast inspector shell first, then load inspector sections as separate tokenized HTMX blocks backed by a shared server-side inspector DTO and Jinja templates.
- Consequences: Inspector presentation is modularized under `src/dbt_dag/inspectors`, stale block responses are isolated by selection token, and long-running or polling sections such as partitions and tasks can refresh independently without blocking node selection.

## ADR-0017 Metadata-Driven Inspector Refresh

- Created: 2026-06-04
- Status: active
- Context: Polling individual inspector blocks caused visible blinking and refreshed static controls that did not depend on changing metadata.
- Decision: Keep the inspector shell stable after node selection, reload only metadata-dependent blocks when the shared metadata revision changes, and leave static blocks such as actions out of automatic refresh.
- Consequences: Inspector updates no longer swap the whole sidebar during background refresh, metadata-driven blocks can show lightweight in-place loading state, and block refresh responsibility stays centralized in the graph client instead of block-level polling.

## ADR-0018 Cytoscape fCoSE DAG Renderer

- Created: 2026-06-05
- Status: active
- Supersedes: ADR-0013
- Context: The DAG view needs directed arrows, compound source/product grouping, and interactive browser-native pan/zoom without maintaining a custom SVG renderer.
- Decision: Use Cytoscape.js with the fCoSE compound layout and constrained left-to-right placement bias for the graph view.
- Consequences: Frontend graph rendering depends on `cytoscape`, `cytoscape-fcose`, and `cytoscape-layout-utilities`; source and product compounds continue to come from backend `GraphPayload.groups`, and the layout favors DAG flow without requiring exact layered ordering.
