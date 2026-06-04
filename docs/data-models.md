# Data Models

## DTOs

- `DbtProjectPaths`: resolved dbt project directory, derived `target/manifest.json` path, and profiles directory.
- `DbtRuntimeProfile`: resolved dbt profile name, active target, adapter kind, and project paths.
- `DbtManifestNode`: normalized dbt resource used by the graph and inspectors.
- `NodeRuntimeMetadata`: per-node runtime metadata with execution time, update timestamp, source labels, freshness, border width, and border color.
- `GraphPayload`: graph nodes, including package name, runtime metadata, graph edges, columns, and project summary.
- `GraphStateSnapshot`: thread-safe in-memory graph, manifest, runtime metadata, revision, and refresh timestamp.
- `NodeTaskDTO`: persisted dbt action task state for a node.

## Database Tables

### `node_tasks`

Stores subprocess tasks started from node actions.

- `id`: integer primary key.
- `node_id`: manifest unique id.
- `command`: full dbt command.
- `status`: `created`, `running`, `succeeded`, or `failed`.
- `created_at`, `started_at`, `finished_at`: MSK-normalized timestamps.
- `exit_code`: subprocess exit code when finished.
- `logs_excerpt`: bounded stdout/stderr excerpt.

### `manifest_source_state`

Stores the last ingested manifest source state.

- `id`: integer primary key.
- `manifest_path`: resolved manifest path.
- `checksum`: manifest checksum.
- `last_ingested_at`: MSK-normalized timestamp.
