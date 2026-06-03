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
- Status: active
- Context: The DAG view needs stable left-to-right dependency layout, labeled rectangular nodes, and fewer edge crossings than the Sigma force-style renderer provides.
- Decision: Use ELK.js layered layout to order DAG nodes, then render the result with first-party SVG and HTML.
- Consequences: Frontend graph rendering depends on `elkjs`; the backend graph payload remains the source of node and edge data, and visual swimlanes are derived in the browser.
